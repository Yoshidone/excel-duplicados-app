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

# -------------------------
# EXPORTAR EXCEL
# -------------------------
def exportar_excel(df):

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    return output.getvalue()

# -------------------------
# LEER CSV
# -------------------------
def leer_csv_seguro(f):

    for sep in [",", ";"]:
        try:
            f.seek(0)
            return pd.read_csv(f, sep=sep, low_memory=False)
        except:
            continue

    raise ValueError("No se pudo leer el CSV")

# -------------------------
# CARGAR ARCHIVO
# -------------------------
@st.cache_data
def cargar_archivo(file):

    nombre = file.name.lower()

    if nombre.endswith(".csv"):

        df = leer_csv_seguro(file)

    elif nombre.endswith(".zip"):

        with zipfile.ZipFile(file) as z:

            archivos_csv = [n for n in z.namelist() if n.endswith(".csv")]

            if not archivos_csv:
                raise ValueError("El ZIP no contiene CSV")

            with z.open(archivos_csv[0]) as f:

                df = leer_csv_seguro(f)

    else:

        df = pd.read_excel(file)

    return df

# -------------------------
# PROCESAR ARCHIVO
# -------------------------
if archivo is not None:

    with st.spinner("Procesando archivo grande..."):

        df = cargar_archivo(archivo)

    st.success("Archivo cargado correctamente")

    # -------------------------
    # ELIMINAR DUPLICADOS
    # -------------------------

    if "PSP_TIN" not in df.columns:

        st.error("No existe la columna PSP_TIN")
        st.stop()

    df_sin_duplicados = df.drop_duplicates(subset="PSP_TIN")

    # -------------------------
    # DASHBOARD
    # -------------------------

    st.subheader("Dashboard financiero")

    col1, col2, col3 = st.columns(3)

    col1.metric("Total registros", len(df))
    col2.metric("Columnas", len(df.columns))
    col3.metric("Registros sin duplicados", len(df_sin_duplicados))

    st.divider()

    # -------------------------
    # DETECTAR MONEDA
    # -------------------------

    moneda_col = None

    for col in df.columns:

        if df[col].astype(str).str.contains("PEN|USD", na=False).any():

            moneda_col = col
            break

    if moneda_col is None:

        st.error("No se encontró columna de moneda")
        st.stop()

    # -------------------------
    # SEPARAR PEN Y USD
    # -------------------------

    pen = df_sin_duplicados[
        df_sin_duplicados[moneda_col].astype(str).str.contains("PEN", na=False)
    ]

    usd = df_sin_duplicados[
        df_sin_duplicados[moneda_col].astype(str).str.contains("USD", na=False)
    ]

    st.subheader("Separación por moneda")

    c1, c2 = st.columns(2)

    c1.metric("Registros PEN", len(pen))
    c2.metric("Registros USD", len(usd))

    st.divider()

    # -------------------------
    # DESCARGAS
    # -------------------------

    st.subheader("Descargar resultados")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Preparar base limpia"):
            st.download_button(
                "Descargar base limpia",
                exportar_excel(df_sin_duplicados),
                "base_limpia.xlsx"
            )

    with col2:
        if st.button("Preparar PEN"):
            st.download_button(
                "Descargar PEN",
                exportar_excel(pen),
                "pen.xlsx"
            )

    with col3:
        if st.button("Preparar USD"):
            st.download_button(
                "Descargar USD",
                exportar_excel(usd),
                "usd.xlsx"
            )
