import streamlit as st
import pandas as pd
import zipfile
from io import BytesIO

st.set_page_config(page_title="Analizador Financiero", layout="wide")

st.title("Dashboard financiero")

# ---------------------------
# CONFIGURACIÓN DE COMISIONES
# ---------------------------

porcentaje = st.number_input("Porcentaje comisión (%)", value=2.30)
fee_fijo = st.number_input("Fee fijo", value=0.90)
aplicar_igv = st.checkbox("Aplicar IGV (18%)", value=True)

porcentaje = porcentaje / 100


# ---------------------------
# CARGA DE ARCHIVOS
# ---------------------------

archivo = st.file_uploader("Subir archivo CSV o Excel", type=["csv","xlsx"])

if archivo:

    if archivo.name.endswith(".csv"):
        df = pd.read_csv(archivo)

    else:
        df = pd.read_excel(archivo)

    st.subheader("Preview datos")
    st.dataframe(df.head())

    # ------------------------------------
    # LIMPIEZA
    # ------------------------------------

    df.columns = df.columns.str.strip()

    # ------------------------------------
    # DETECTAR PAGOS Y COMISIONES
    # ------------------------------------

    pagos = df[df["OP_amount"] > 0]
    comisiones = df[df["OP_amount"] < 0]

    pagos = pagos.groupby(["psp_tin","tx_currency_code"])["OP_amount"].sum().reset_index()
    pagos.rename(columns={"OP_amount":"tx_amount_pago"}, inplace=True)

    comisiones = comisiones.groupby(["psp_tin","tx_currency_code"])["OP_amount"].sum().reset_index()
    comisiones.rename(columns={"OP_amount":"comision_contrato"}, inplace=True)

    resultado = pagos.merge(comisiones, on=["psp_tin","tx_currency_code"], how="left")

    resultado["comision_contrato"] = resultado["comision_contrato"].abs()

    # ------------------------------------
    # CALCULAR COMISIÓN ESPERADA
    # ------------------------------------

    resultado["comision"] = (resultado["tx_amount_pago"] * porcentaje) + fee_fijo

    if aplicar_igv:
        resultado["comision"] = resultado["comision"] * 1.18

    resultado["comision"] = resultado["comision"].round(2)

    # ------------------------------------
    # DIFERENCIA
    # ------------------------------------

    resultado["diferencia"] = resultado["comision_contrato"] - resultado["comision"]

    resultado["total_neto"] = resultado["tx_amount_pago"] - resultado["comision_contrato"]

    # ------------------------------------
    # DASHBOARD
    # ------------------------------------

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Total registros", len(df))

    with col2:
        st.metric("Total transacciones únicas", len(resultado))


    # ------------------------------------
    # TABLA
    # ------------------------------------

    st.dataframe(resultado)

    # ------------------------------------
    # CONTROL DE COMISIONES
    # ------------------------------------

    st.subheader("Control de comisiones")

    no_coinciden = resultado[resultado["diferencia"].abs() > 0.01]

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Total comisiones analizadas", len(resultado))

    with col2:
        st.metric("Comisiones que NO coinciden", len(no_coinciden))


    # ------------------------------------
    # DESCARGA
    # ------------------------------------

    csv = resultado.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Descargar comparación de comisiones",
        csv,
        "comparacion_comisiones.csv",
        "text/csv"
    )
