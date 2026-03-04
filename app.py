import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Detector de Duplicados", layout="wide")

st.title("Detector de Duplicados y Separador por Moneda")

archivo = st.file_uploader("Sube tu archivo Excel", type=["xlsx"])


# -------- CARGA OPTIMIZADA --------
@st.cache_data(show_spinner=False)
def cargar_excel(file):
    df = pd.read_excel(file, engine="openpyxl")
    return df


# -------- CONVERTIR PARA DESCARGA --------
def convertir_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()


if archivo is not None:

    with st.spinner("Procesando archivo grande..."):
        df = cargar_excel(archivo)

    st.success("Archivo cargado correctamente")

    # -------- DUPLICADOS --------
    duplicados = df[df.duplicated(keep=False)]

    st.subheader("Registros duplicados encontrados")

    if not duplicados.empty:

        st.warning(f"{len(duplicados)} registros duplicados encontrados")

        st.dataframe(
            duplicados,
            use_container_width=True,
            height=500
        )

    else:
        st.success("No se encontraron duplicados")

    # -------- DETECTAR COLUMNA MONEDA --------
    moneda_col = None

    for col in df.columns:

        valores = df[col].astype(str).str.upper()

        if valores.str.contains("PEN|USD", na=False).any():
            moneda_col = col
            break

    pen = pd.DataFrame()
    usd = pd.DataFrame()

    if moneda_col:

        pen = df[df[moneda_col].astype(str).str.contains("PEN", na=False)]
        usd = df[df[moneda_col].astype(str).str.contains("USD", na=False)]

    # -------- DESCARGAS --------
    st.subheader("Descargar archivos")

    col1, col2, col3 = st.columns(3)

    with col1:
        if not duplicados.empty:
            st.download_button(
                "Descargar duplicados",
                convertir_excel(duplicados),
                "duplicados.xlsx"
            )

    with col2:
        if not pen.empty:
            st.download_button(
                "Descargar PEN",
                convertir_excel(pen),
                "pen.xlsx"
            )

    with col3:
        if not usd.empty:
            st.download_button(
                "Descargar USD",
                convertir_excel(usd),
                "usd.xlsx"
            )
