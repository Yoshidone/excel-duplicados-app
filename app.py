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
# Leer archivo
# ---------------------------

def leer_archivo(file):
    if file.name.endswith(".xlsx"):
        df = pd.read_excel(file)

    elif file.name.endswith(".csv"):
        df = pd.read_csv(file)

    return df


if archivo:

    dfs = []

    # ---------------------------
    # Leer ZIP
    # ---------------------------

    if archivo.name.endswith(".zip"):

        with zipfile.ZipFile(archivo) as z:

            for nombre in z.namelist():

                if nombre.endswith(".csv"):
                    with z.open(nombre) as f:
                        df = pd.read_csv(f)
                        dfs.append(df)

                elif nombre.endswith(".xlsx"):
                    with z.open(nombre) as f:
                        df = pd.read_excel(f)
                        dfs.append(df)

        df = pd.concat(dfs, ignore_index=True)

    else:

        df = leer_archivo(archivo)

    # ---------------------------
    # LIMPIAR IDS (solo agregado)
    # ---------------------------

    if "TX_transaction_id" in df.columns:
        df["TX_transaction_id"] = (
            df["TX_transaction_id"]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.strip()
        )

    if "SF_transaction_related_id" in df.columns:
        df["SF_transaction_related_id"] = (
            df["SF_transaction_related_id"]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.strip()
        )

    # ---------------------------
    # Merge usando IDs correctos
    # ---------------------------

    if "TX_transaction_id" in df.columns and "SF_transaction_related_id" in df.columns:

        df = df.merge(
            df[["TX_transaction_id","TX_amount"]],
            left_on="SF_transaction_related_id",
            right_on="TX_transaction_id",
            how="left",
            suffixes=("","_tx")
        )

        df["tx_amount_pago"] = df["TX_amount_tx"]

    # ---------------------------
    # AQUÍ SIGUE TU LÓGICA ORIGINAL
    # (comisiones variables)
    # ---------------------------

    st.subheader("Resumen financiero")

    total_pago = df["tx_amount_pago"].sum()
    total_comision = df["comision"].sum()
    total_neto = df["total_neto"].sum()

    col1,col2,col3 = st.columns(3)

    col1.metric("Total pagos", round(total_pago,2))
    col2.metric("Total comisiones", round(total_comision,2))
    col3.metric("Total neto", round(total_neto,2))

    st.dataframe(df)

    # ---------------------------
    # Descargar
    # ---------------------------

    csv = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Descargar resultado",
        csv,
        "resultado_financiero.csv",
        "text/csv"
    )
