import streamlit as st
import pandas as pd
import zipfile

st.set_page_config(page_title="Analizador Financiero Payin", layout="wide")
st.title("Analizador Financiero Payin")

# ================= UPLOADS =================
archivo = st.file_uploader("Sube tu archivo principal", type=["xlsx", "csv", "zip"])
archivo_extra = st.file_uploader("Sube archivo adicional (base clientes)", type=["xlsx", "csv"], key="extra")

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

# ================= PROCESAR =================
if archivo is not None:

    df = cargar_archivo(archivo)
    df.columns = df.columns.str.lower().str.strip()
    st.success("Archivo principal cargado")

    # Archivo extra
    if archivo_extra is not None:
        df_extra = pd.read_excel(archivo_extra, sheet_name=0)
        df_extra.columns = df_extra.columns.str.lower().str.strip()
        st.success("Archivo adicional cargado")

    # Validación
    columnas_necesarias = ["psp_tin", "tx_currency_code", "tx_amount"]
    faltantes = [c for c in columnas_necesarias if c not in df.columns]
    if faltantes:
        st.error(f"Faltan columnas: {', '.join(faltantes)}")
        st.stop()

    df["tx_currency_code"] = df["tx_currency_code"].astype(str).str.upper()

    if "tx_reference" in df.columns:
        df["tx_reference"] = df["tx_reference"].astype(str).str.upper()

    # ================= FILTRO =================
    if "x_create_date_gmt_peru" in df.columns:
        df["fecha"] = pd.to_datetime(df["x_create_date_gmt_peru"], errors="coerce")
        df["mes"] = df["fecha"].dt.strftime("%Y-%m")
        mes_sel = st.selectbox("Mes", sorted(df["mes"].dropna().unique()))
    else:
        mes_sel = None

    moneda_sel = st.selectbox("Moneda", ["PEN", "USD"])

    if st.button("Aplicar filtro"):

        if mes_sel:
            df = df[(df["mes"] == mes_sel) & (df["tx_currency_code"] == moneda_sel)]
        else:
            df = df[df["tx_currency_code"] == moneda_sel]

        simbolo = "S/" if moneda_sel == "PEN" else "$"

        # ================= COMISIONES =================
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

            # Normalizar claves
            df_extra["referencia de pago"] = df_extra["referencia de pago"].astype(str).str.strip()
            tabla["psp_tin"] = tabla["psp_tin"].astype(str).str.strip()
            df["psp_tin"] = df["psp_tin"].astype(str).str.strip()

            # Fecha transferencia
            df_fecha = df[["psp_tin", "x_create_date_gmt_peru"]].copy()
            df_fecha.rename(columns={"x_create_date_gmt_peru": "fecha de transferencia"}, inplace=True)
            df_fecha["psp_tin"] = df_fecha["psp_tin"].astype(str)

            # Merge
            final = df_extra.merge(tabla, left_on="referencia de pago", right_on="psp_tin", how="left")
            final = final.merge(df_fecha, on="psp_tin", how="left")

            # ================= FORMATO FINAL =================
            salida = pd.DataFrame({
                "FECHA DE REGISTRO": pd.to_datetime(final["fecha de registro"], errors="coerce").dt.strftime("%d/%m/%Y"),
                "EMPRESA": final["empresa"],
                "REFERENCIA DE PAGO": final["referencia de pago"],
                "CLIENTE": final["cliente"],
                "DESCRIPCIÓN": final["descripción"],
                "RECAUDO": pd.to_numeric(final["tx_amount_pago"], errors="coerce").round(2),
                "COMISIÓN KASHIO": pd.to_numeric(final["comision_real"], errors="coerce").round(2),
                "NETO": pd.to_numeric(final["total_neto"], errors="coerce").round(2),
                "MÉTODO DE PAGO": final["método de pago"],
                "OPERACIÓN": final["operación"],
                "FECHA DE TRANSFERENCIA": pd.to_datetime(final["fecha de transferencia"], errors="coerce").dt.strftime("%d/%m/%Y")
            })

            salida = salida.fillna(0)

            st.subheader("📄 Archivo final listo")
            st.dataframe(salida)

            st.download_button(
                "📥 Descargar reporte final",
                exportar_csv(salida),
                "reporte_final.csv"
            )
