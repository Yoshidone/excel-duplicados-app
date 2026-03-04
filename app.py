import streamlit as st
import polars as pl
import pandas as pd
from io import BytesIO
import zipfile

# ---------- CONFIGURACION ----------
st.set_page_config(
    page_title="Analizador Financiero",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.title("Analizador Financiero de Bases")

archivo = st.file_uploader(
    "Sube tu archivo (Excel, CSV, ZIP o Parquet)",
    type=["xlsx", "csv", "zip", "parquet"]
)


# ---------- LECTURA SEGURA CSV ----------
def leer_csv_seguro(f):

    try:
        df = pl.read_csv(
            f,
            separator=",",
            ignore_errors=True,
            infer_schema_length=10000
        )
    except:

        f.seek(0)

        df = pl.read_csv(
            f,
            separator=";",
            ignore_errors=True,
            infer_schema_length=10000
        )

    return df


# ---------- CARGAR ARCHIVO ----------
def cargar_base(file):

    nombre = file.name.lower()

    # CSV
    if nombre.endswith(".csv"):
        df = leer_csv_seguro(file)

    # PARQUET
    elif nombre.endswith(".parquet"):
        df = pl.read_parquet(file)

    # ZIP
    elif nombre.endswith(".zip"):

        with zipfile.ZipFile(file) as z:

            nombre_archivo = z.namelist()[0]

            with z.open(nombre_archivo) as f:
                df = leer_csv_seguro(f)

    # EXCEL
    else:

        df_pandas = pd.read_excel(file, engine="openpyxl")

        buffer = BytesIO()
        df_pandas.to_csv(buffer, index=False)
        buffer.seek(0)

        df = leer_csv_seguro(buffer)

    return df


# ---------- EXPORTAR EXCEL ----------
def exportar_excel(df):

    output = BytesIO()

    df.to_pandas().to_excel(output, index=False)

    return output.getvalue()


# ---------- PROCESAR ARCHIVO ----------
if archivo is not None:

    with st.spinner("Cargando base..."):

        try:
            df = cargar_base(archivo)

        except Exception as e:
            st.error("Error al leer el archivo.")
            st.exception(e)
            st.stop()

    st.success("Archivo cargado correctamente")

    # ---------- RESUMEN ----------
    st.subheader("Resumen del archivo")

    col1, col2, col3 = st.columns(3)

    col1.metric("Filas", df.height)
    col2.metric("Columnas", df.width)
    col3.metric("Memoria (MB)", round(df.estimated_size() / 1_000_000, 2))

    st.divider()

    # ---------- DUPLICADOS ----------
    st.subheader("Detección de duplicados")

    columna_dup = st.selectbox(
        "Selecciona la columna para detectar duplicados",
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

    # ---------- DETECTAR MONEDA ----------
    moneda_col = None

    for col in df.columns:

        try:
            if df[col].cast(str).str.contains("PEN|USD").any():
                moneda_col = col
                break
        except:
            pass

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

    # ---------- DESCARGAS ----------
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
