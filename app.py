import streamlit as st
import pandas as pd
import zipfile
from io import BytesIO

# ---------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------

st.set_page_config(page_title="Analizador Financiero", layout="wide")

st.title("💰 Analizador Financiero de Transacciones")
st.markdown("Sube tu base para analizar pagos, comisiones y resultados netos.")

# ---------------------------------------------------
# SUBIR ARCHIVO
# ---------------------------------------------------

archivo = st.file_uploader(
    "Sube tu archivo Excel, CSV o ZIP",
    type=["xlsx", "csv", "zip"]
)

# ---------------------------------------------------
# EXPORTAR CSV
# ---------------------------------------------------

def exportar_csv(df):
    return df.to_csv(index=False).encode("utf-8")

# ---------------------------------------------------
# LEER CSV
# ---------------------------------------------------

def leer_csv_seguro(f):

    for sep in [",", ";"]:
        try:
            f.seek(0)
            return pd.read_csv(f, sep=sep, low_memory=False)
        except:
            continue

    raise ValueError("No se pudo leer el CSV")

# ---------------------------------------------------
# CARGAR ARCHIVO
# ---------------------------------------------------

@st.cache_data
def cargar_archivo(file):

    nombre = file.name.lower()

    if nombre.endswith(".csv"):
        df = leer_csv_seguro(file)

    elif nombre.endswith(".zip"):

        with zipfile.ZipFile(file) as z:

            archivos_csv = [n for n in z.namelist() if n.endswith(".csv")]

            if not archivos_csv:
                raise ValueError("El ZIP no contiene CSV")

            with z.open(archivos_csv[0]) as f:
                df = leer_csv_seguro(f)

    else:
        df = pd.read_excel(file)

    return df


# ---------------------------------------------------
# PROCESAR
# ---------------------------------------------------

if archivo is not None:

    with st.spinner("Procesando archivo..."):
        df = cargar_archivo(archivo)

    df.columns = df.columns.str.lower().str.strip()

    st.success("Archivo cargado correctamente")

    df["op_amount"] = pd.to_numeric(df["op_amount"], errors="coerce")

# ---------------------------------------------------
# DASHBOARD
# ---------------------------------------------------

    st.subheader("📊 Dashboard Financiero")

    c1, c2, c3 = st.columns(3)

    c1.metric("📄 Total registros", f"{len(df):,}")
    c2.metric("📊 Columnas", len(df.columns))
    c3.metric("🏦 PSP únicos", df["psp_tin"].nunique())

    st.divider()

# ---------------------------------------------------
# SEPARACIÓN POR MONEDA
# ---------------------------------------------------

    pen = df[df["tx_currency_code"] == "PEN"]
    usd = df[df["tx_currency_code"] == "USD"]

    st.subheader("💱 Separación por moneda")

    c1, c2 = st.columns(2)

    c1.metric("🇵🇪 Registros PEN", f"{len(pen):,}")
    c2.metric("🇺🇸 Registros USD", f"{len(usd):,}")

    st.divider()

# ---------------------------------------------------
# DESCARGAS
# ---------------------------------------------------

    st.subheader("⬇️ Descargar resultados")

    c1, c2 = st.columns(2)

    with c1:
        st.download_button(
            "Descargar registros PEN",
            exportar_csv(pen),
            "registros_pen.csv",
            mime="text/csv"
        )

    with c2:
        st.download_button(
            "Descargar registros USD",
            exportar_csv(usd),
            "registros_usd.csv",
            mime="text/csv"
        )

# ===================================================
# COMPARACIÓN DE COMISIONES
# ===================================================

    st.divider()
    st.subheader("💳 Comparación de comisiones")

    porcentaje_contrato = st.number_input(
        "Porcentaje comisión (%)",
        value=2.30,
        step=0.01
    )

    fee_fijo = st.number_input(
        "Fee fijo",
        value=0.90,
        step=0.01
    )

    aplicar_igv = st.checkbox("Aplicar IGV (18%)", value=True)

# ---------------------------------------------------
# PAGOS (solo PY)
# ---------------------------------------------------

    pagos = (
        df[df["op_operation_no"].str.startswith("PY", na=False)]
        .groupby("psp_tin", as_index=False)["op_amount"]
        .sum()
    )

    pagos = pagos.rename(columns={"op_amount": "tx_amount_pago"})

# ---------------------------------------------------
# COMISIONES (solo SF)
# ---------------------------------------------------

    comisiones = (
        df[df["tx_reference"].str.startswith("SF", na=False)]
        .groupby("psp_tin", as_index=False)["op_amount"]
        .sum()
    )

    comisiones["op_amount"] = comisiones["op_amount"].abs()

    comisiones = comisiones.rename(columns={"op_amount": "comision"})

# ---------------------------------------------------
# LISTA COMPLETA DE PSP
# ---------------------------------------------------

    todos_psp = df[["psp_tin"]].drop_duplicates()

# ---------------------------------------------------
# MERGE
# ---------------------------------------------------

    tabla = todos_psp.merge(pagos, on="psp_tin", how="left") \
                     .merge(comisiones, on="psp_tin", how="left")

    tabla = tabla.fillna(0)

# ---------------------------------------------------
# COMISIÓN CONTRATO
# ---------------------------------------------------

    tabla["comision_contrato"] = (
        (tabla["tx_amount_pago"] * (porcentaje_contrato / 100))
        + fee_fijo
    )

    if aplicar_igv:
        tabla["comision_contrato"] = tabla["comision_contrato"] * 1.18

    tabla["comision_contrato"] = tabla["comision_contrato"].round(2)

# ---------------------------------------------------
# DIFERENCIA
# ---------------------------------------------------

    tabla["diferencia"] = (
        tabla["comision"] - tabla["comision_contrato"]
    ).round(2)

# ---------------------------------------------------
# TOTAL NETO
# ---------------------------------------------------

    tabla["total_neto"] = tabla["tx_amount_pago"] - tabla["comision"]

# ---------------------------------------------------
# RESUMEN
# ---------------------------------------------------

    total_pagos = tabla["tx_amount_pago"].sum()
    total_comisiones = tabla["comision"].sum()
    total_neto = tabla["total_neto"].sum()

    st.subheader("📊 Resumen financiero")

    c1, c2, c3 = st.columns(3)

    c1.metric("💰 Total pagos", round(total_pagos, 2))
    c2.metric("💸 Total comisiones", round(total_comisiones, 2))
    c3.metric("💵 Total neto", round(total_neto, 2))

    st.dataframe(tabla)

    st.download_button(
        "Descargar comparación",
        exportar_csv(tabla),
        "comparacion_comisiones.csv",
        mime="text/csv"
    )
