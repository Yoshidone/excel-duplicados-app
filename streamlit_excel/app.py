import streamlit as st
import pandas as pd
from io import BytesIO

st.title("Detector de Duplicados y Separador por Moneda")

archivo = st.file_uploader("Sube tu archivo Excel", type=["xlsx"])

@st.cache_data
def cargar_excel(archivo):
    df = pd.read_excel(archivo, engine="openpyxl")
    return df

if archivo is not None:

    with st.spinner("Procesando archivo grande..."):
        df = cargar_excel(archivo)

    st.success("Archivo cargado correctamente")

    columna = st.selectbox(
        "Selecciona la columna para detectar duplicados",
        df.columns
    )

    duplicados = df[df.duplicated(subset=[columna], keep=False)]

    st.subheader("Registros duplicados encontrados")

    if not duplicados.empty:
        st.dataframe(duplicados)
        st.warning(f"Se encontraron {len(duplicados)} registros duplicados")
    else:
        st.success("No se encontraron duplicados")

    def convertir_excel(dataframe):
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            dataframe.to_excel(writer, index=False)
        return output.getvalue()

    st.subheader("Descargar archivos")

    st.download_button(
        label="Descargar Excel completo",
        data=convertir_excel(df),
        file_name="archivo_completo.xlsx"
    )

    st.download_button(
        label="Descargar duplicados",
        data=convertir_excel(duplicados),
        file_name="duplicados.xlsx"
    )
