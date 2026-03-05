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

    # 🔹 asegurar que tx_reference sea texto
    df["tx_reference"] = df["tx_reference"].astype(str)

    # ---------------------------
    # Dashboard
    # ---------------------------
    st.subheader("Dashboard financiero")

    c1, c2, c3 = st.columns(3)

    c1.metric("Total registros", len(df))
    c2.metric("Columnas", len(df.columns))
    c3.metric("PSP únicos", df["psp_tin"].nunique())

    st.divider()

    # ---------------------------
    # Separación por moneda
    # ---------------------------
    pen = df[df["tx_currency_code"] == "PEN"]
    usd = df[df["tx_currency_code"] == "USD"]

    st.subheader("Separación por moneda")

    c1, c2 = st.columns(2)

    c1.metric("Registros PEN", len(pen))
    c2.metric("Registros USD", len(usd))

    st.divider()

    # ---------------------------
    # Descargas
    # ---------------------------
    st.subheader("Descargar resultados")

    c1, c2 = st.columns(2)

    with c1:
        st.download_button(
            "Descargar PEN",
            exportar_csv(pen),
            "registros_pen.csv",
            mime="text/csv"
        )

    with c2:
        st.download_button(
            "Descargar USD",
            exportar_csv(usd),
            "registros_usd.csv",
            mime="text/csv"
        )

# ==================================================
# COMPARACIÓN DE COMISIONES
# ==================================================

    st.divider()
    st.subheader("Comparación de comisiones")

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

    pagos = (
        df[df["tx_reference"].str.startswith("PY", na=False)]
        .groupby("psp_tin", as_index=False)["tx_amount"]
        .sum()
    )

    pagos = pagos.rename(columns={"tx_amount": "tx_amount_pago"})

# ---------------------------
# COMISIONES (SF)
# ---------------------------

    comisiones = (
        df[df["tx_reference"].str.startswith("SF", na=False)]
        .groupby("psp_tin", as_index=False)["tx_amount"]
        .sum()
    )

    comisiones = comisiones.rename(columns={"tx_amount": "comision"})

# ---------------------------
# MERGE
# ---------------------------

    tabla = pagos.merge(comisiones, on="psp_tin", how="left")

# ---------------------------
# comisión contrato
# ---------------------------

    tabla["comision_contrato"] = (
        (tabla["tx_amount_pago"] * (porcentaje_contrato / 100))
        + fee_fijo
    )

    if aplicar_igv:
        tabla["comision_contrato"] = tabla["comision_contrato"] * 1.18

    tabla["comision_contrato"] = tabla["comision_contrato"].round(2)

# ---------------------------
# diferencia
# ---------------------------

    tabla["diferencia"] = (
        tabla["comision"] - tabla["comision_contrato"]
    ).round(2)

# ---------------------------
# neto
# ---------------------------

    tabla["total_neto"] = tabla["tx_amount_pago"] - tabla["comision"]

# ---------------------------
# Resumen
# ---------------------------

    total_pagos = tabla["tx_amount_pago"].sum()
    total_comisiones = tabla["comision"].sum()
    total_neto = tabla["total_neto"].sum()
    total_diferencia = tabla["diferencia"].sum()

    st.subheader("Resumen financiero")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Total pagos", round(total_pagos, 2))
    c2.metric("Total comisiones", round(total_comisiones, 2))
    c3.metric("Total neto", round(total_neto, 2))
    c4.metric("Total diferencia", round(total_diferencia, 2))

    st.dataframe(tabla)

    st.download_button(
        "Descargar comparación de comisiones",
        exportar_csv(tabla),
        "comparacion_comisiones.csv",
        mime="text/csv"
    )
