import streamlit as st
import pandas as pd
import zipfile
from io import BytesIO

# ---------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------

st.set_page_config(page_title="Analizador Financiero", layout="wide")

st.title("💰 Analizador Financiero de Transacciones")

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
# PAGOS (PY)
# ---------------------------------------------------

    pagos = df[df["tx_reference"].str.startswith("PY", na=False)]

    pagos = pagos[[
        "psp_tin",
        "tx_transaction_id",
        "op_amount"
    ]]

    pagos = pagos.rename(columns={
        "op_amount": "tx_amount_pago"
    })

# ---------------------------------------------------
# COMISIONES (SF)
# ---------------------------------------------------

    comisiones = df[df["tx_reference"].str.startswith("SF", na=False)]

    comisiones = comisiones[[
        "sf_transaction_related_id",
        "op_amount"
    ]]

    comisiones["op_amount"] = comisiones["op_amount"].abs()

    comisiones = comisiones.rename(columns={
        "sf_transaction_related_id": "tx_transaction_id",
        "op_amount": "comision"
    })

# ---------------------------------------------------
# MERGE PY ↔ SF
# ---------------------------------------------------

    tabla = pagos.merge(
        comisiones,
        on="tx_transaction_id",
        how="left"
    )

    tabla["comision"] = tabla["comision"].fillna(0)

# ---------------------------------------------------
# NETO
# ---------------------------------------------------

    tabla["total_neto"] = tabla["tx_amount_pago"] - tabla["comision"]

# ---------------------------------------------------
# AGRUPAR POR PSP
# ---------------------------------------------------

    tabla = tabla.groupby("psp_tin", as_index=False).agg({
        "tx_amount_pago": "sum",
        "comision": "sum",
        "total_neto": "sum"
    })

# ---------------------------------------------------
# RESUMEN
# ---------------------------------------------------

    total_pagos = tabla["tx_amount_pago"].sum()
    total_comisiones = tabla["comision"].sum()
    total_neto = tabla["total_neto"].sum()

    st.subheader("📊 Resumen financiero")

    c1, c2, c3 = st.columns(3)

    c1.metric("Total pagos", round(total_pagos, 2))
    c2.metric("Total comisiones", round(total_comisiones, 2))
    c3.metric("Total neto", round(total_neto, 2))

    st.dataframe(tabla)

    st.download_button(
        "Descargar resultado",
        exportar_csv(tabla),
        "resultado_financiero.csv",
        mime="text/csv"
    )
