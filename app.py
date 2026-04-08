import streamlit as st
import pandas as pd
import zipfile

st.set_page_config(page_title="Analizador Financiero", layout="wide")
st.title("Analizador Financiero de Bases")

archivo = st.file_uploader("Sube tu archivo Excel, CSV o ZIP", type=["xlsx", "csv", "zip"])

modo = st.radio(
    "Modo de uso",
    [
        "📂 Solo preparar y descargar bases",
        "📊 Análisis completo de comisiones",
        "🧩 Completo (descargas + análisis)"
    ]
)

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

    # ================= SESSION STATE =================
    if "filtro_aplicado" not in st.session_state:
        st.session_state.filtro_aplicado = False

    if "mes_sel" not in st.session_state:
        st.session_state.mes_sel = None

    # ================= FILTRO =================
    st.divider()
    st.subheader("📅 Filtro por mes")

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

        if st.button("Aplicar filtro"):
            st.session_state.filtro_aplicado = True

    else:
        st.warning("No se encontró columna de fecha")

    if not st.session_state.filtro_aplicado:
        st.info("Selecciona un mes y haz clic en 'Aplicar filtro'")
        st.stop()

    df = df[df["mes"] == st.session_state.mes_sel]

    # ================= BASES =================
    df_sin_duplicados = df.drop_duplicates(subset="psp_tin")

    pen_total = df[df["tx_currency_code"] == "PEN"]
    usd_total = df[df["tx_currency_code"] == "USD"]

    pen = df_sin_duplicados[df_sin_duplicados["tx_currency_code"] == "PEN"]
    usd = df_sin_duplicados[df_sin_duplicados["tx_currency_code"] == "USD"]

    if modo in ["📂 Solo preparar y descargar bases", "🧩 Completo (descargas + análisis)"]:

        st.subheader("Dashboard financiero")

        c1, c2, c3 = st.columns(3)
        c1.metric("Total registros", len(df))
        c2.metric("Columnas", len(df.columns))
        c3.metric("Registros sin duplicados", len(df_sin_duplicados))

        st.divider()
        st.subheader("Separación por moneda")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("PEN totales", len(pen_total))
        c2.metric("USD totales", len(usd_total))
        c3.metric("PEN sin duplicados", len(pen))
        c4.metric("USD sin duplicados", len(usd))

        st.divider()
        st.subheader("Descargar resultados")

        c1, c2, c3 = st.columns(3)

        with c1:
            st.download_button("Descargar base sin duplicados", exportar_csv(df_sin_duplicados), "base.csv")

        with c2:
            st.download_button("Descargar PEN", exportar_csv(pen), "pen.csv")

        with c3:
            st.download_button("Descargar USD", exportar_csv(usd), "usd.csv")

    # ================= COMISIONES =================
    if modo in ["📊 Análisis completo de comisiones", "🧩 Completo (descargas + análisis)"]:

        st.divider()
        st.subheader("Comparación de comisiones")

        porcentaje = st.number_input("Porcentaje comisión (%)", value=2.30)
        fee_fijo = st.number_input("Fee fijo (S/)", value=0.90)
        aplicar_igv = st.checkbox("Aplicar IGV (18%)", True)

        if "tx_reference" in df.columns and "tx_amount" in df.columns:

            pagos = df[df["tx_reference"].str.startswith("PY", na=False)]
            fees = df[df["tx_reference"].str.startswith("SF", na=False)]

            comisiones = pagos.merge(
                fees[["psp_tin", "tx_amount"]],
                on="psp_tin",
                how="left",
                suffixes=("_pago", "_comision")
            )

            comisiones["tx_amount_pago"] = pd.to_numeric(comisiones["tx_amount_pago"], errors="coerce")
            comisiones["tx_amount_comision"] = pd.to_numeric(comisiones["tx_amount_comision"], errors="coerce")

            comisiones["comision_real"] = comisiones["tx_amount_comision"].abs()
            comisiones["comision_base"] = (comisiones["tx_amount_pago"] * (porcentaje / 100)) + fee_fijo

            # 🔥 CORRECCIÓN CLAVE
            comisiones["igv"] = (comisiones["comision_base"] * 0.18).round(2)

            if aplicar_igv:
                comisiones["comision_final"] = (comisiones["comision_base"] + comisiones["igv"]).round(2)
            else:
                comisiones["comision_final"] = comisiones["comision_base"].round(2)
                comisiones["igv"] = 0

            comisiones["diferencia"] = (comisiones["comision_real"] - comisiones["comision_final"]).round(2)
            comisiones["total_neto"] = (comisiones["tx_amount_pago"] - comisiones["comision_real"]).round(2)

            tabla = comisiones[
                ["psp_tin","tx_amount_pago","comision_real","comision_base","igv",
                 "comision_final","diferencia","total_neto"]
            ].fillna(0)

            st.dataframe(tabla)

            st.download_button("📥 Descargar comparación de comisiones", exportar_csv(tabla), "comisiones.csv")

            # ================= RESUMEN =================
            st.subheader("Resumen financiero")

            total_recaudo = tabla["tx_amount_pago"].sum()
            total_comisiones = tabla["comision_real"].sum()
            total_base = tabla["comision_base"].sum()
            total_igv = tabla["igv"].sum()
            total_final = tabla["comision_final"].sum()
            total_neto = tabla["total_neto"].sum()
            total_diferencia = tabla["diferencia"].sum()

            operaciones = pagos["psp_tin"].nunique()

            c1, c2, c3 = st.columns(3)
            c4, c5, c6 = st.columns(3)

            c1.metric("💰 Total Recaudado", f"S/ {total_recaudo:,.2f}")
            c2.metric("💸 Comisiones Reales", f"S/ {total_comisiones:,.2f}")
            c3.metric("🧾 Comisión Base", f"S/ {total_base:,.2f}")
            c4.metric("🏛 IGV Total", f"S/ {total_igv:,.2f}")
            c5.metric("📑 Comisión Final", f"S/ {total_final:,.2f}")
            c6.metric("⚖️ Diferencia Total", f"S/ {total_diferencia:,.2f}")

            st.metric("🔢 Número de Operaciones", f"{operaciones:,}")
            st.metric("🧮 Total Neto", f"S/ {total_neto:,.2f}")
