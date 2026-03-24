import streamlit as st
import pandas as pd
import zipfile
from io import BytesIO

st.set_page_config(page_title="Analizador Financiero", layout="wide")
st.title("Analizador Financiero de Bases")

archivo = st.file_uploader(
    "Sube tu archivo Excel, CSV o ZIP",
    type=["xlsx", "csv", "zip"]
)

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

# ---------------------------
# PROCESAR
# ---------------------------
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

    df_sin_duplicados = df.drop_duplicates(subset="psp_tin")

    pen_total = df[df["tx_currency_code"] == "PEN"]
    usd_total = df[df["tx_currency_code"] == "USD"]

    pen = df_sin_duplicados[df_sin_duplicados["tx_currency_code"] == "PEN"]
    usd = df_sin_duplicados[df_sin_duplicados["tx_currency_code"] == "USD"]

    # ==================================================
    # BLOQUE BASES
    # ==================================================
    if modo in [
        "📂 Solo preparar y descargar bases",
        "🧩 Completo (descargas + análisis)"
    ]:

        st.subheader("Dashboard financiero")

        c1, c2, c3 = st.columns(3)
        c1.metric("Total registros", len(df))
        c2.metric("Columnas", len(df.columns))
        c3.metric("Registros sin duplicados", len(df_sin_duplicados))

        st.divider()

        st.subheader("Separación por moneda")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("PEN totales (con duplicados)", len(pen_total))
        c2.metric("USD totales (con duplicados)", len(usd_total))
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

    # ==================================================
    # BLOQUE COMISIONES
    # ==================================================
    if modo in [
        "📊 Análisis completo de comisiones",
        "🧩 Completo (descargas + análisis)"
    ]:

        st.divider()
        st.subheader("Comparación de comisiones")

        porcentaje = st.number_input("Porcentaje comisión (%)", value=2.30)
        fee_fijo = st.number_input("Fee fijo (S/)", value=0.90)
        aplicar_igv = st.checkbox("Aplicar IGV (18%)", True)

        if "tx_reference" in df.columns and "tx_amount" in df.columns:

            pagos = df[df["tx_reference"].str.startswith("PY", na=False)]
            fees = df[df["tx_reference"].str.startswith("SF", na=False)]

            pagos = pagos.drop_duplicates(subset="psp_tin")
            fees = fees.drop_duplicates(subset="psp_tin")

            comisiones = pagos.merge(
                fees[["psp_tin", "tx_amount"]],
                on="psp_tin",
                how="left",
                suffixes=("_pago", "_comision")
            )

            comisiones = comisiones.merge(
                pagos[["psp_tin", "tx_currency_code", "tx_create_date_gmt_peru"]],
                on="psp_tin",
                how="left"
            )

            # cálculos
            comisiones["tx_amount_pago"] = pd.to_numeric(comisiones["tx_amount_pago"], errors="coerce")
            comisiones["tx_amount_comision"] = pd.to_numeric(comisiones["tx_amount_comision"], errors="coerce")

            comisiones["comision_real"] = comisiones["tx_amount_comision"].abs()
            comisiones["comision_base"] = (comisiones["tx_amount_pago"] * (porcentaje / 100)) + fee_fijo
            comisiones["igv"] = comisiones["comision_base"] * 0.18

            comisiones["comision_final"] = comisiones["comision_base"] + comisiones["igv"] if aplicar_igv else comisiones["comision_base"]

            for col in ["tx_amount_pago","comision_real","comision_base","igv","comision_final"]:
                comisiones[col] = comisiones[col].round(2)

            comisiones["diferencia"] = (comisiones["comision_real"] - comisiones["comision_final"]).round(2)
            comisiones["total_neto"] = (comisiones["tx_amount_pago"] - comisiones["comision_real"]).round(2)

            tabla = comisiones[
                ["psp_tin","tx_amount_pago","tx_currency_code","comision_real","comision_base","igv","comision_final","diferencia","total_neto","tx_create_date_gmt_peru"]
            ].fillna(0)

            st.dataframe(tabla)

            st.download_button("Descargar", exportar_csv(tabla), "comisiones.csv")

            # ================= RESUMEN =================
            st.subheader("Resumen financiero")

            st.metric("💰 Recaudado", f"S/ {tabla['tx_amount_pago'].sum():,.2f}")
            st.metric("💸 Comisiones", f"S/ {tabla['comision_real'].sum():,.2f}")
            st.metric("🧮 Neto", f"S/ {tabla['total_neto'].sum():,.2f}")

            # ================= FILTRO MES =================
            tabla["fecha"] = pd.to_datetime(tabla["tx_create_date_gmt_peru"], errors="coerce")
            tabla["periodo"] = tabla["fecha"].dt.to_period("M")

            meses = sorted(tabla["periodo"].dropna().astype(str).unique())
            seleccion = st.multiselect("Filtrar meses", meses, default=meses)

            tabla_f = tabla[tabla["periodo"].astype(str).isin(seleccion)]

            # ================= RESUMEN MENSUAL =================
            st.subheader("📊 Resumen mensual")

            for periodo, datos in tabla_f.groupby("periodo"):
                st.markdown(f"### {periodo}")
                st.metric("💰 Recaudado", f"S/ {datos['tx_amount_pago'].sum():,.2f}")
                st.metric("💸 Comisiones", f"S/ {datos['comision_real'].sum():,.2f}")
                st.metric("🧮 Neto", f"S/ {datos['total_neto'].sum():,.2f}")
