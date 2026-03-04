import streamlit as st
import pandas as pd
import polars as pl
from io import BytesIO
import zipfile

st.set_page_config(page_title="Analizador Financiero", layout="wide")

st.title("Analizador Financiero de Bases")

archivo = st.file_uploader(
    "Sube tu archivo (Excel, CSV o ZIP)",
    type=["xlsx", "csv", "zip"]
)

# ---------- leer csv seguro ----------
def leer_csv(f):

    try:
        return pl.read_csv(f, separator=",", infer_schema_length=1000)
    except:
        f.seek(0)
        return pl.read_csv(f, separator=";", infer_schema_length=1000)


# ---------- cargar archivo ----------
def cargar_archivo(file):

    nombre = file.name.lower()

    if nombre.endswith(".csv"):
        df = leer_csv(file)

    elif nombre.endswith(".zip"):

        with zipfile.ZipFile(file) as z:

            archivo_csv = [f for f in z.namelist() if f.endswith(".csv")][0]

            with z.open(archivo_csv) as f:

                df = leer_csv(f)

    else:

        df = pd.read_excel(file)

        df = pl.from_pandas(df)

    return df


# ---------- ejecutar ----------
if archivo:

    with st.spinner("Procesando archivo..."):

        df = cargar_archivo(archivo)

    st.success("Archivo cargado")

    st.subheader("Resumen")

    col1, col2 = st.columns(2)

    col1.metric("Filas", df.height)
    col2.metric("Columnas", df.width)

    st.divider()

    columna = st.selectbox("Selecciona columna para duplicados", df.columns)

    duplicados = df.filter(pl.col(columna).is_duplicated())

    st.write("Duplicados encontrados:", duplicados.height)

    if duplicados.height > 0:

        st.dataframe(duplicados.to_pandas(), height=400)

    # detectar moneda
    moneda_col = None

    for col in df.columns:
        if df[col].cast(str).str.contains("PEN|USD").any():
            moneda_col = col
            break

    if moneda_col:

        pen = df.filter(pl.col(moneda_col).str.contains("PEN"))
        usd = df.filter(pl.col(moneda_col).str.contains("USD"))

        st.subheader("Separación por moneda")

        c1, c2 = st.columns(2)

        c1.metric("PEN", pen.height)
        c2.metric("USD", usd.height)

        def exportar(df):

            output = BytesIO()

            df.to_pandas().to_excel(output, index=False)

            return output.getvalue()

        st.download_button(
            "Descargar duplicados",
            exportar(duplicados),
            "duplicados.xlsx"
        )

        st.download_button(
            "Descargar PEN",
            exportar(pen),
            "pen.xlsx"
        )

        st.download_button(
            "Descargar USD",
            exportar(usd),
            "usd.xlsx"
        )
