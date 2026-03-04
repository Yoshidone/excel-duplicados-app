import streamlit as st
import polars as pl
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Analizador Financiero", layout="wide")

st.title("Analizador Financiero de Bases")

archivo = st.file_uploader(
    "Sube tu archivo Excel o CSV",
    type=["xlsx", "csv"]
)


# -------- CARGA RAPIDA --------
@st.cache_data
def cargar_base(file):

    nombre = file.name.lower()

    # si es csv (MUY rápido)
    if nombre.endswith(".csv"):
        df = pl.read_csv(file)

    # si es excel
    else:
        df_pandas = pd.read_excel(file, engine="openpyxl")

        # convertir a csv en memoria
        buffer = BytesIO()
        df_pandas.to_csv(buffer, index=False)
        buffer.seek(0)

        df = pl.read_csv(buffer)

    return df


# -------- EXPORTAR EXCEL --------
def exportar_excel(df):

    output = BytesIO()

    df.to_pandas().to_excel(output, index=False)

    return output.getvalue()


if archivo is not None:

    with st.spinner("Cargando base..."):
        df = cargar_base(archivo)

    st.success("Archivo cargado correctamente")

    # -------- RESUMEN --------
    st.subheader("Resumen del archivo")

    c1, c2, c3 = st.columns(3)

    c1.metric("Filas", df.height)
    c2.metric("Columnas", df.width)
    c3.metric("Memoria MB", round(df.estimated_size()/1000000, 2))

    st.divider()

    # -------- DUPLICADOS --------
    st.subheader("Detección de duplicados")

    columna_dup = st.selectbox(
        "Selecciona la columna para buscar duplicados",
        df.columns
    )

    duplicados = df.filter(
        pl.col(columna_dup).is_duplicated()
    )

    st.metric("Duplicados encontrados", duplicados.height)

    if duplicados.height > 0:

        st.dataframe(
            duplicados.to_pandas(),
            use_container_width=True,
            height=400
        )

    st.divider()

    # -------- DETECTAR MONEDA --------
    moneda_col = None

    for col in df.columns:

        if df[col].cast(str).str.contains("PEN|USD").any():
            moneda_col = col
            break

    pen = pl.DataFrame()
    usd = pl.DataFrame()

    if moneda_col:

        pen = df.filter(
            pl.col(moneda_col).cast(str).str.contains("PEN")
        )

        usd = df.filter(
            pl.col(moneda_col).cast(str).str.contains("USD")
        )

        st.subheader("Separación por moneda")

        c1, c2 = st.columns(2)

        c1.metric("Registros PEN", pen.height)
        c2.metric("Registros USD", usd.height)

    st.divider()

    # -------- DESCARGAS --------
    st.subheader("Descargar resultados")

    col1, col2, col3 = st.columns(3)

    with col1:
        if duplicados.height > 0:
            st.download_button(
                "Descargar duplicados",
                exportar_excel(duplicados),
                "duplicados.xlsx"
            )

    with col2:
        if pen.height > 0:
            st.download_button(
                "Descargar SOLES",
                exportar_excel(pen),
                "soles.xlsx"
            )

    with col3:
        if usd.height > 0:
            st.download_button(
                "Descargar DÓLARES",
                exportar_excel(usd),
                "dolares.xlsx"
            )
