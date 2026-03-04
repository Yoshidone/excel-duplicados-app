import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Detector de Duplicados", layout="wide")

st.title("Detector de Duplicados y Separador por Moneda")

archivo = st.file_uploader("Sube tu archivo Excel", type=["xlsx"])


# -------- CARGA OPTIMIZADA --------
@st.cache_data
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

    with st.spinner("Procesando archivo..."):
        df = cargar_excel(archivo)

    st.success("Archivo cargado correctamente")

    # -------- INFO GENERAL --------
    st.subheader("Resumen del archivo")

    col1, col2, col3 = st.columns(3)

    col1.metric("Filas totales", len(df))
    col2.metric("Columnas", len(df.columns))
    col3.metric("Memoria aprox (MB)", round(df.memory_usage().sum()/1000000,2))


    # -------- SELECCIONAR COLUMNA DUPLICADOS --------
    st.subheader("Detección de duplicados")

    columna_dup = st.selectbox(
        "Selecciona la columna para buscar duplicados",
        df.columns
    )

    duplicados = df[df.duplicated(subset=[columna_dup], keep=False)]

    if not duplicados.empty:

        st.warning(f"{len(duplicados)} registros duplicados encontrados")

        st.dataframe(
            duplicados,
            use_container_width=True,
            height=400
        )

    else:
        st.success("No se encontraron duplicados")


    # -------- DETECTAR MONEDA --------
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

        st.subheader("Separación por moneda")

        c1, c2 = st.columns(2)

        c1.metric("Registros PEN", len(pen))
        c2.metric("Registros USD", len(usd))

    else:
        st.warning("No se detectó columna de moneda automáticamente")


    # -------- DESCARGAS --------
    st.subheader("Descargar resultados")

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
