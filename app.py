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
# LEER CSV SEGURO
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

    # normalizar columnas
    df.columns = df.columns.str.lower().str.strip()

    st.success("Archivo cargado correctamente")

    # -------------------------
    # VALIDAR COLUMNAS
    # -------------------------

    if "psp_tin" not in df.columns:

        st.error("No existe la columna psp_tin")
        st.stop()

    if "tx_currency_code" not in df.columns:

        st.error("No existe la columna tx_currency_code")
        st.stop()

    # -------------------------
    # ELIMINAR DUPLICADOS
    # -------------------------

    df_sin_duplicados = df.drop_duplicates(subset="psp_tin")

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
    # SEPARAR MONEDA
    # -------------------------

    pen = df_sin_duplicados[
        df_sin_duplicados["tx_currency_code"] == "PEN"
    ]

    usd = df_sin_duplicados[
        df_sin_duplicados["tx_currency_code"] == "USD"
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

        st.download_button(
            "Descargar base sin duplicados",
            exportar_excel(df_sin_duplicados),
            "base_sin_duplicados.xlsx"
        )

    with col2:

        st.download_button(
            "Descargar PEN",
            exportar_excel(pen),
            "registros_pen.xlsx"
        )

    with col3:

        st.download_button(
            "Descargar USD",
            exportar_excel(usd),
            "registros_usd.xlsx"
        )
