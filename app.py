import streamlit as st
import pandas as pd
import zipfile
from io import BytesIO

st.set_page_config(page_title="Analizador Financiero", layout="wide")

st.title("Analizador Financiero")

archivo = st.file_uploader(
    "Sube tu archivo Excel, CSV o ZIP",
    type=["xlsx","csv","zip"]
)

def leer_archivo(file):

    if file.name.endswith(".xlsx"):
        df = pd.read_excel(file)

    elif file.name.endswith(".csv"):
        df = pd.read_csv(file)

    return df


if archivo:

    dfs = []

    # -------------------------
    # Leer ZIP
    # -------------------------

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


    # -------------------------
    # Limpiar IDs
    # -------------------------

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


    # -------------------------
    # Separar tablas
    # -------------------------

    tx = df[df["TX_transaction_id"].notna()].copy()
    sf = df[df["SF_transaction_related_id"].notna()].copy()


    # -------------------------
    # Merge correcto
    # -------------------------

    df_final = sf.merge(
        tx,
        left_on="SF_transaction_related_id",
        right_on="TX_transaction_id",
        how="left",
        suffixes=("_sf","_tx")
    )


    # -------------------------
    # Monto pago
    # -------------------------

    if "TX_amount_tx" in df_final.columns:

        df_final["tx_amount_pago"] = df_final["TX_amount_tx"]

    else:

        df_final["tx_amount_pago"] = 0


    # -------------------------
    # Comisión sistema
    # -------------------------

    df_final["comision"] = (
        (df_final["tx_amount_pago"] * 0.023) + 0.9
    ) * 1.18


    # -------------------------
    # Comisión contrato
    # -------------------------

    df_final["comision_contrato"] = (
        (df_final["tx_amount_pago"] * 0.021) + 0.9
    ) * 1.18


    # -------------------------
    # Diferencia
    # -------------------------

    df_final["diferencia"] = (
        df_final["comision"] - df_final["comision_contrato"]
    )


    # -------------------------
    # Neto
    # -------------------------

    df_final["total_neto"] = (
        df_final["tx_amount_pago"] - df_final["comision"]
    )


    # -------------------------
    # Resumen
    # -------------------------

    total_pago = df_final["tx_amount_pago"].sum()
    total_comision = df_final["comision"].sum()
    total_neto = df_final["total_neto"].sum()


    st.subheader("Resumen financiero")

    col1,col2,col3 = st.columns(3)

    col1.metric("Total pagos", round(total_pago,2))
    col2.metric("Total comisiones", round(total_comision,2))
    col3.metric("Total neto", round(total_neto,2))


    # -------------------------
    # Tabla
    # -------------------------

    st.dataframe(df_final)


    # -------------------------
    # Descargar
    # -------------------------

    csv = df_final.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Descargar resultado",
        csv,
        "resultado_financiero.csv",
        "text/csv"
    )
