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
        df = pd.read_csv(file, sep=None, engine="python")

    return df


if archivo:

    dfs = []

    # ---------------------------
    # Leer ZIP
    # ---------------------------

    if archivo.name.endswith(".zip"):

        with zipfile.ZipFile(archivo) as z:

            for nombre in z.namelist():

                try:

                    if nombre.endswith(".csv"):
                        with z.open(nombre) as f:
                            df = pd.read_csv(f, sep=None, engine="python")
                            dfs.append(df)

                    elif nombre.endswith(".xlsx"):
                        with z.open(nombre) as f:
                            df = pd.read_excel(f)
                            dfs.append(df)

                except:
                    pass

        df = pd.concat(dfs, ignore_index=True)

    else:

        df = leer_archivo(archivo)

    # ---------------------------
    # LIMPIAR COMAS DEL ID
    # ---------------------------

    if "TX_transaction_id" in df.columns:

        df["TX_transaction_id"] = (
            df["TX_transaction_id"]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.strip()
        )

    # ---------------------------
    # CAMBIO IMPORTANTE
    # antes usaba psp_tin
    # ahora usa SF_transaction_related_id
    # ---------------------------

    if "SF_transaction_related_id" in df.columns and "TX_transaction_id" in df.columns:

        df = df.merge(
            df[["TX_transaction_id", "TX_amount"]],
            left_on="SF_transaction_related_id",
            right_on="TX_transaction_id",
            how="left",
            suffixes=("","_tx")
        )

        df["tx_amount_pago"] = df["TX_amount_tx"]

    # ---------------------------
    # RESUMEN FINANCIERO
    # ---------------------------

    st.subheader("Resumen financiero")

    total_pago = df["tx_amount_pago"].sum()
    total_comision = df["comision"].sum()
    total_neto = df["total_neto"].sum()

    col1,col2,col3 = st.columns(3)

    col1.metric("Total pagos", round(total_pago,2))
    col2.metric("Total comisiones", round(total_comision,2))
    col3.metric("Total neto", round(total_neto,2))

    # ---------------------------
    # CUADRO FINAL
    # ---------------------------

    st.dataframe(df)

    # ---------------------------
    # SEPARAR POR MONEDA
    # ---------------------------

    if "TX_currency_code" in df.columns:

        soles = df[df["TX_currency_code"] == "PEN"]
        dolares = df[df["TX_currency_code"] == "USD"]

        st.subheader("Transacciones PEN")
        st.dataframe(soles)

        st.subheader("Transacciones USD")
        st.dataframe(dolares)

        csv_soles = soles.to_csv(index=False).encode("utf-8")
        csv_dolares = dolares.to_csv(index=False).encode("utf-8")

        col1, col2 = st.columns(2)

        col1.download_button(
            "Descargar PEN",
            csv_soles,
            "transacciones_pen.csv",
            "text/csv"
        )

        col2.download_button(
            "Descargar USD",
            csv_dolares,
            "transacciones_usd.csv",
            "text/csv"
        )
