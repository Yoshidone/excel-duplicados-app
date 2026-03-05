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
# PROCESAR
# ---------------------------
if archivo is not None:

    with st.spinner("Procesando archivo..."):
        df = cargar_archivo(archivo)

    df.columns = df.columns.str.lower().str.strip()

    st.success("Archivo cargado correctamente")

    if "psp_tin" not in df.columns:
        st.error("No existe la columna psp_tin")
        st.stop()

    if "tx_currency_code" not in df.columns:
        st.error("No existe la columna tx_currency_code")
        st.stop()

    df["tx_currency_code"] = df["tx_currency_code"].astype(str).str.upper()

    if "tx_reference" in df.columns:
        df["tx_reference"] = df["tx_reference"].astype(str).str.upper()

    if "op_operation_no" in df.columns:
        df["op_operation_no"] = df["op_operation_no"].astype(str).str.upper()

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
    # Separación moneda
    # ---------------------------

    pen = df[df["tx_currency_code"] == "PEN"]
    usd = df[df["tx_currency_code"] == "USD"]

    st.subheader("Separación por moneda")

    c1, c2 = st.columns(2)

    c1.metric("Transacciones PEN", len(pen))
    c2.metric("Transacciones USD", len(usd))

    st.divider()

    # ==================================================
    # ANALISIS DE COMISIONES
    # ==================================================

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
    # PAGOS
    # ---------------------------

    pagos = df[df["tx_reference"].str.startswith("PY", na=False)].copy()

    # ---------------------------
    # COMISIONES
    # ---------------------------

    fees = df[df["op_operation_no"].str.startswith("SF", na=False)].copy()

    # convertir montos
    pagos["tx_amount"] = pd.to_numeric(pagos["tx_amount"], errors="coerce")
    fees["op_amount"] = pd.to_numeric(fees["op_amount"], errors="coerce")

    # ---------------------------
    # MERGE CORRECTO
    # ---------------------------

    comisiones = pagos.merge(
        fees[["sf_transaction_related_id", "op_amount"]],
        left_on="tx_transaction_id",
        right_on="sf_transaction_related_id",
        how="left"
    )

    # comisión real
    comisiones["comision"] = comisiones["op_amount"].abs()

    # comisión contrato
    comisiones["comision_contrato"] = (
        (comisiones["tx_amount"] * (porcentaje_contrato / 100))
        + fee_fijo
    )

    if aplicar_igv:
        comisiones["comision_contrato"] *= 1.18

    comisiones["comision_contrato"] = comisiones["comision_contrato"].round(2)

    # diferencia
    comisiones["diferencia"] = (
        comisiones["comision"] - comisiones["comision_contrato"]
    ).round(2)

    tabla = comisiones[
        [
            "psp_tin",
            "tx_transaction_id",
            "tx_amount",
            "comision",
            "comision_contrato",
            "diferencia"
        ]
    ].fillna(0)

    tabla["total_neto"] = tabla["tx_amount"] - tabla["comision"]

    st.dataframe(tabla)

    st.subheader("Control de comisiones")

    c1, c2 = st.columns(2)

    c1.metric("Total comisiones analizadas", len(tabla))
    c2.metric(
        "Comisiones que NO coinciden",
        len(tabla[tabla["diferencia"] != 0])
    )

    st.download_button(
        "Descargar comparación de comisiones",
        exportar_csv(tabla),
        "comparacion_comisiones.csv",
        mime="text/csv"
    )
