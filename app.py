import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Analizador Financiero", layout="wide")

st.title("Analizador Financiero de Bases")

archivo = st.file_uploader(
    "Sube tu archivo Excel o CSV",
    type=["xlsx", "csv"]
)

def exportar_excel(df):
    output = BytesIO()
    df.to_excel(output, index=False)
    return output.getvalue()

if archivo is not None:

    try:

        if archivo.name.endswith(".csv"):
            df = pd.read_csv(archivo)
        else:
            df = pd.read_excel(archivo)

        st.success("Archivo cargado correctamente")

    except Exception:
        st.error("No se pudo leer el archivo")
        st.stop()

    st.subheader("Resumen")

    c1, c2 = st.columns(2)

    c1.metric("Filas", len(df))
    c2.metric("Columnas", len(df.columns))

    st.divider()

    columna = st.selectbox(
        "Selecciona columna para detectar duplicados",
        df.columns
    )

    duplicados = df[df.duplicated(columna, keep=False)]

    st.write("Duplicados encontrados:", len(duplicados))

    if len(duplicados) > 0:
        st.dataframe(duplicados)

    st.divider()

    moneda_col = None

    for col in df.columns:
        if df[col].astype(str).str.contains("PEN|USD", na=False).any():
            moneda_col = col
            break

    if moneda_col:

        pen = df[df[moneda_col].astype(str).str.contains("PEN", na=False)]
        usd = df[df[moneda_col].astype(str).str.contains("USD", na=False)]

        st.subheader("Separación por moneda")

        c1, c2 = st.columns(2)

        c1.metric("PEN", len(pen))
        c2.metric("USD", len(usd))

        st.download_button(
            "Descargar duplicados",
            exportar_excel(duplicados),
            "duplicados.xlsx"
        )

        st.download_button(
            "Descargar PEN",
            exportar_excel(pen),
            "pen.xlsx"
        )

        st.download_button(
            "Descargar USD",
            exportar_excel(usd),
            "usd.xlsx"
        )
