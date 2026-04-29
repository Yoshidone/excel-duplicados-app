import streamlit as st
import pandas as pd
import zipfile

st.set_page_config(page_title="Analizador Financiero Payin", layout="wide")
st.title("Analizador Financiero Payin")

# ================= UPLOADS =================
archivo = st.file_uploader("Sube tu archivo Excel, CSV o ZIP", type=["xlsx", "csv", "zip"])
archivo_extra = st.file_uploader("Sube archivo adicional (hoja 1)", type=["xlsx", "csv"], key="extra")

modo = st.radio(
    "Modo de uso",
    [
        "📂 Solo preparar y descargar bases",
        "📊 Análisis completo de comisiones",
        "🧩 Completo (descargas + análisis)"
    ]
)

# ================= FUNCIONES =================
def exportar_csv(df):
    return df.to_csv(index=False).encode("utf-8")

def leer_csv_seguro(f):
    for sep in [",", ";"]:
        try:
            f.seek(0)
            return pd.read_csv(f, sep=sep, decimal=".", encoding="utf-8", low_memory=False)
        except:
            continue
    raise ValueError("No se pudo leer el CSV")

@st.cache_data
def cargar_archivo(file):
    nombre = file.name.lower()

    if nombre.endswith(".csv"):
        return leer_csv_seguro(file)

    elif nombre.endswith(".zip"):
        with zipfile.ZipFile(file) as z:
            for nombre_archivo in z.namelist():
                if nombre_archivo.lower().endswith(".csv"):
                    with z.open(nombre_archivo) as f:
                        return leer_csv_seguro(f)

                if nombre_archivo.lower().endswith((".xlsx", ".xls")):
                    with z.open(nombre_archivo) as f:
                        return pd.read_excel(f, engine="openpyxl")

        raise ValueError("ZIP sin CSV ni Excel")

    else:
        return pd.read_excel(file, engine="openpyxl")

# ================= LIMPIEZA CLAVE =================
def limpiar_id(x):
    return str(x).strip().upper().replace(" ", "")

# ================= PROCESAR =================
if archivo is not None:

    df = cargar_archivo(archivo)
    df.columns = df.columns.str.lower().str.strip()
    st.success("Archivo cargado correctamente")

    if "psp_tin" not in df.columns or "tx_currency_code" not in df.columns:
        st.error("Faltan columnas necesarias")
        st.stop()

    df["tx_currency_code"] = df["tx_currency_code"].astype(str).str.upper()

    if "tx_reference" in df.columns:
        df["tx_reference"] = df["tx_reference"].astype(str).str.upper()

    # ================= SESSION =================
    if "filtro_aplicado" not in st.session_state:
        st.session_state.filtro_aplicado = False

    if "mes_sel" not in st.session_state:
        st.session_state.mes_sel = None

    # ================= FILTRO =================
    st.divider()
    st.subheader("📅 Filtro por mes")

    col1, col2 = st.columns(2)

    with col1:
        if "x_create_date_gmt_peru" in df.columns:
            df["fecha"] = pd.to_datetime(df["x_create_date_gmt_peru"], errors="coerce")
            df["mes"] = df["fecha"].dt.strftime("%Y-%m")

            meses = sorted(df["mes"].dropna().unique())

            mes_sel = st.selectbox(
                "Selecciona un mes",
                meses,
                index=meses.index(st.session_state.mes_sel) if st.session_state.mes_sel in meses else 0
            )

            st.session_state.mes_sel = mes_sel
        else:
            st.warning("No se encontró columna de fecha")

    with col2:
        moneda_sel = st.selectbox("Selecciona moneda", ["PEN", "USD"])

    if st.button("Aplicar filtro"):
        st.session_state.filtro_aplicado = True

    if not st.session_state.filtro_aplicado:
        st.stop()

    # 🔥 FILTRO PRINCIPAL
    df = df[
        (df["mes"] == st.session_state.mes_sel) &
        (df["tx_currency_code"] == moneda_sel)
    ]

    simbolo = "S/" if moneda_sel == "PEN" else "$"

    # ================= BASES =================
    df_sin_duplicados = df.drop_duplicates(subset="psp_tin")

    if modo in ["📂 Solo preparar y descargar bases", "🧩 Completo (descargas + análisis)"]:

        st.subheader("Dashboard financiero")

        c1, c2, c3 = st.columns(3)
        c1.metric("Total registros", len(df))
        c2.metric("Columnas", len(df.columns))
        c3.metric("Registros sin duplicados", len(df_sin_duplicados))

        st.download_button("Descargar base", exportar_csv(df_sin_duplicados), "base.csv")

    # ================= COMISIONES =================
    if modo in ["📊 Análisis completo de comisiones", "🧩 Completo (descargas + análisis)"]:

        porcentaje = st.number_input("Porcentaje (%)", value=2.30)
        fee_fijo = st.number_input("Fee fijo", value=0.90)
        aplicar_igv = st.checkbox("IGV", True)

        pagos = df[df["tx_reference"].str.startswith("PY", na=False)]
        fees = df[df["tx_reference"].str.startswith("SF", na=False)]

        fees = fees.groupby("psp_tin", as_index=False)["tx_amount"].sum()

        comisiones = pagos.merge(fees, on="psp_tin", how="left", suffixes=("_pago", "_comision"))

        comisiones["tx_amount_pago"] = pd.to_numeric(comisiones["tx_amount_pago"], errors="coerce")
        comisiones["comision_real"] = comisiones["tx_amount_comision"].abs()

        comisiones["comision_base"] = (comisiones["tx_amount_pago"] * (porcentaje / 100)) + fee_fijo
        comisiones["igv"] = comisiones["comision_base"] * 0.18

        if aplicar_igv:
            comisiones["comision_final"] = comisiones["comision_base"] + comisiones["igv"]
        else:
            comisiones["comision_final"] = comisiones["comision_base"]
            comisiones["igv"] = 0

        comisiones["diferencia"] = comisiones["comision_real"] - comisiones["comision_final"]
        comisiones["total_neto"] = comisiones["tx_amount_pago"] - comisiones["comision_real"]

        tabla = comisiones.fillna(0)

        st.subheader("📊 Comparación de comisiones")
        st.dataframe(tabla)

        # ================= CRUCE FINAL =================
        if archivo_extra is not None:

            df_extra = pd.read_excel(archivo_extra, sheet_name=0)
            df_extra.columns = df_extra.columns.str.lower().str.strip()

            # 🔥 LIMPIEZA CLAVE
            df_extra["referencia de pago"] = df_extra["referencia de pago"].apply(limpiar_id)
            tabla["psp_tin"] = tabla["psp_tin"].apply(limpiar_id)
            df["psp_tin"] = df["psp_tin"].apply(limpiar_id)

            # 🔥 FILTRO POR MES EN ARCHIVO EXTRA
            if "fecha de registro" in df_extra.columns:
                df_extra["fecha de registro"] = pd.to_datetime(df_extra["fecha de registro"], errors="coerce")
                df_extra["mes"] = df_extra["fecha de registro"].dt.strftime("%Y-%m")
                df_extra = df_extra[df_extra["mes"] == st.session_state.mes_sel]

            # Fecha transferencia
            df_fecha = df[["psp_tin", "x_create_date_gmt_peru"]].copy()
            df_fecha.rename(columns={"x_create_date_gmt_peru": "fecha de transferencia"}, inplace=True)
            df_fecha["psp_tin"] = df_fecha["psp_tin"].apply(limpiar_id)

            # Merge
            final = df_extra.merge(
                tabla[["psp_tin","tx_amount_pago","comision_real","total_neto"]],
                left_on="referencia de pago",
                right_on="psp_tin",
                how="left"
            )

            final = final.merge(df_fecha, on="psp_tin", how="left")

            salida = pd.DataFrame({
                "FECHA DE REGISTRO": final["fecha de registro"],
                "EMPRESA": final["empresa"],
                "REFERENCIA DE PAGO": final["referencia de pago"],
                "CLIENTE": final["cliente"],
                "DESCRIPCIÓN": final["descripción"],
                "RECAUDO": final["tx_amount_pago"],
                "COMISIÓN KASHIO": final["comision_real"],
                "NETO": final["total_neto"],
                "MÉTODO DE PAGO": final["método de pago"],
                "OPERACIÓN": final["operación"],
                "FECHA DE TRANSFERENCIA": final["fecha de transferencia"]
            }).fillna(0)

            st.subheader("📄 Archivo final")
            st.dataframe(salida)

            st.download_button(
                "📥 Descargar archivo final",
                exportar_csv(salida),
                "reporte_final.csv"
            )
