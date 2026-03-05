import streamlit as st
import pandas as pd
import zipfile
from io import BytesIO

st.set_page_config(page_title="Analizador Financiero", layout="wide")

st.title("💰 Analizador Financiero de Transacciones")

archivo = st.file_uploader(
    "Sube tu archivo Excel, CSV o ZIP",
    type=["xlsx", "csv", "zip"]
)

# ---------------------------
# Exportar CSV
# ---------------------------
def exportar_csv(df):
    return df.to_csv(index=False).encode("utf-8")

# ---------------------------
# Leer CSV
# ---------------------------
def leer_csv_seguro(f):
    for sep in [",", ";"]:
        try:
            f.seek(0)
            return pd.read_csv(f, sep=sep, low_memory=False)
        except:
            continue
    raise ValueError("No se pudo leer el CSV")

# ---------------------------
# Cargar archivo
# ---------------------------
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


# ---------------------------
# Procesar
# ---------------------------
if archivo is not None:

    with st.spinner("Procesando archivo..."):
        df = cargar_archivo(archivo)

    df.columns = df.columns.str.lower().str.strip()

    st.success("Archivo cargado correctamente")

    df["tx_amount"] = pd.to_numeric(df["tx_amount"], errors="coerce")

# ---------------------------
# Dashboard
# ---------------------------
    st.subheader("Dashboard Financiero")

    c1, c2, c3 = st.columns(3)

    c1.metric("Total registros", len(df))
    c2.metric("Columnas", len(df.columns))
    c3.metric("PSP únicos", df["psp_tin"].nunique())

    st.divider()

# ---------------------------
# COMPARACIÓN DE COMISIONES
# ---------------------------

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

# ---------------------------
# PAGOS (PY)
# ---------------------------

    pagos = df[df["tx_reference"].str.startswith("PY", na=False)]

    pagos = pagos[[
        "psp_tin",
        "tx_transaction_id",
        "tx_amount"
    ]]

    pagos = pagos.rename(columns={
        "tx_transaction_id": "PY",
        "tx_amount": "pago"
    })

# ---------------------------
# COMISIONES (SF)
# ---------------------------

    comisiones = df[df["tx_reference"].str.startswith("SF", na=False)]

    comisiones = comisiones[[
        "sf_transaction_related_id",
        "tx_transaction_id",
        "tx_amount"
    ]]

    comisiones = comisiones.rename(columns={
        "sf_transaction_related_id": "PY",
        "tx_transaction_id": "SF",
        "tx_amount": "comision"
    })

# ---------------------------
# MERGE PY ↔ SF
# ---------------------------

    tabla = pagos.merge(
        comisiones,
        on="PY",
        how="left"
    )

    tabla = tabla.fillna(0)

# ---------------------------
# COMISION CONTRATO
# ---------------------------

    tabla["comision_contrato"] = (
        (tabla["pago"] * (porcentaje_contrato / 100))
        + fee_fijo
    )

    if aplicar_igv:
        tabla["comision_contrato"] = tabla["comision_contrato"] * 1.18

    tabla["comision_contrato"] = tabla["comision_contrato"].round(2)

# ---------------------------
# DIFERENCIA
# ---------------------------

    tabla["diferencia"] = (
        tabla["comision"] - tabla["comision_contrato"]
    ).round(2)

# ---------------------------
# NETO
# ---------------------------

    tabla["neto"] = tabla["pago"] - tabla["comision"]

# ---------------------------
# AGRUPAR POR PSP
# ---------------------------

    tabla = tabla.groupby("psp_tin", as_index=False).agg({
        "PY": "first",
        "SF": "first",
        "pago": "sum",
        "comision": "sum",
        "comision_contrato": "sum",
        "diferencia": "sum",
        "neto": "sum"
    })

# ---------------------------
# Resumen
# ---------------------------

    total_pagos = tabla["pago"].sum()
    total_comisiones = tabla["comision"].sum()
    total_neto = tabla["neto"].sum()

    st.subheader("Resumen financiero")

    c1, c2, c3 = st.columns(3)

    c1.metric("Total pagos", round(total_pagos, 2))
    c2.metric("Total comisiones", round(total_comisiones, 2))
    c3.metric("Total neto", round(total_neto, 2))

    st.dataframe(tabla)

    st.download_button(
        "Descargar comparación",
        exportar_csv(tabla),
        "comparacion_comisiones.csv",
        mime="text/csv"
    )
