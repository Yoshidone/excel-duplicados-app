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

# ---------- EXPORTAR ----------
def exportar_excel(df):
    output = BytesIO()
    df.to_excel(output, index=False)
    return output.getvalue()

# ---------- CARGAR ARCHIVO ----------
@st.cache_data
def cargar_archivo(file):

    # CSV
    if file.name.endswith(".csv"):
        df = pd.read_csv(file, low_memory=False)

    # ZIP con CSV
    elif file.name.endswith(".zip"):

        with zipfile.ZipFile(file) as z:

            nombre = z.namelist()[0]

            with z.open(nombre) as f:

                df = pd.read_csv(f, low_memory=False)

    # Excel
    else:
        df = pd.read_excel(file)

    return df


# ---------- PROCESAR ----------
if archivo is not None:

    with st.spinner("Procesando archivo grande..."):

        try:
            df = cargar_archivo(archivo)
        except:
            st.error("Error leyendo el archivo")
            st.stop()

    st.success("Archivo cargado correctamente")

    # ======================
    # DASHBOARD
    # ======================

    st.subheader("Dashboard financiero")

    col1, col2, col3, col4 = st.columns(4)

    total_registros = len(df)
    total_columnas = len(df.columns)
    duplicados_total = df.duplicated().sum()

    col1.metric("Total registros", total_registros)
    col2.metric("Columnas", total_columnas)
    col3.metric("Duplicados", duplicados_total)

    # detectar moneda
    moneda_col = None

    for col in df.columns:

        if df[col].astype(str).str.contains("PEN|USD", na=False).any():
            moneda_col = col
            break

    if moneda_col:

        pen = df[df[moneda_col].astype(str).str.contains("PEN", na=False)]
        usd = df[df[moneda_col].astype(str).str.contains("USD", na=False)]

        col4.metric("Registros PEN", len(pen))

    st.divider()

    # ======================
    # BUSCADOR
    # ======================

    st.subheader("Buscar registro")

    buscar = st.text_input("Buscar cliente, RUC o texto")

    if buscar:

        resultado = df[df.astype(str).apply(
            lambda x: x.str.contains(buscar, case=False)
        ).any(axis=1)]

        st.write("Resultados encontrados:", len(resultado))

        st.dataframe(resultado)

    st.divider()

    # ======================
    # DUPLICADOS
    # ======================

    st.subheader("Detección de duplicados")

    columna = st.selectbox(
        "Selecciona columna para revisar duplicados",
        df.columns
    )

    duplicados = df[df.duplicated(columna, keep=False)]

    st.write("Duplicados encontrados:", len(duplicados))

    if len(duplicados) > 0:
        st.dataframe(duplicados)

    st.divider()

    # ======================
    # MONEDA
    # ======================

    if moneda_col:

        st.subheader("Separación por moneda")

        c1, c2 = st.columns(2)

        c1.metric("Registros PEN", len(pen))
        c2.metric("Registros USD", len(usd))

        # detectar columna monto
        monto_col = None

        for col in df.columns:

            if "monto" in col.lower() or "amount" in col.lower():
                monto_col = col
                break

        if monto_col:

            total_pen = pen[monto_col].sum()
            total_usd = usd[monto_col].sum()

            c1.metric("Total PEN", total_pen)
            c2.metric("Total USD", total_usd)

        st.divider()

        # ======================
        # DESCARGAS
        # ======================

        st.subheader("Descargar resultados")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.download_button(
                "Descargar duplicados",
                exportar_excel(duplicados),
                "duplicados.xlsx"
            )

        with col2:
            st.download_button(
                "Descargar PEN",
                exportar_excel(pen),
                "pen.xlsx"
            )

        with col3:
            st.download_button(
                "Descargar USD",
                exportar_excel(usd),
                "usd.xlsx"
            )
