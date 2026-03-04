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

# ---------------------------
# Exportar CSV (mucho más ligero)
# ---------------------------
def exportar_csv(df):
    return df.to_csv(index=False).encode("utf-8")

# ---------------------------
# Leer CSV (MEJORADO PARA METABASE)
# ---------------------------
def leer_csv_seguro(f):
    for sep in [",", ";"]:
        try:
            f.seek(0)
            return pd.read_csv(
                f,
                sep=sep,
                encoding="utf-8",
                engine="python",
                low_memory=False,
                on_bad_lines="skip"
            )
        except:
            continue
    raise ValueError("No se pudo leer el CSV")

# ---------------------------
# Cargar archivo
# ---------------------------
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


# ---------------------------
# Procesar
# ---------------------------
if archivo is not None:

    with st.spinner("Procesando archivo..."):
        df = cargar_archivo(archivo)

    df.columns = df.columns.str.lower().str.strip()

    st.success("Archivo cargado correctamente")

    if "psp_tin" not in df.columns:
        st.error("No existe la columna psp_tin")
        st.stop()

    if "tx_currency_code" not in df.columns:
        st.error("No existe la columna tx_currency_code")
        st.stop()

    # eliminar duplicados
    df_sin_duplicados = df.drop_duplicates(subset="psp_tin")

    # ---------------------------
    # Dashboard general
    # ---------------------------
    st.subheader("Dashboard financiero")

    c1, c2, c3 = st.columns(3)

    c1.metric("Total registros", len(df))
    c2.metric("Columnas", len(df.columns))
    c3.metric("Registros sin duplicados", len(df_sin_duplicados))

    st.divider()

    # ---------------------------
    # Separación por moneda
    # ---------------------------

    # CON DUPLICADOS
    pen_total = df[df["tx_currency_code"] == "PEN"]
    usd_total = df[df["tx_currency_code"] == "USD"]

    # SIN DUPLICADOS
    pen = df_sin_duplicados[df_sin_duplicados["tx_currency_code"] == "PEN"]
    usd = df_sin_duplicados[df_sin_duplicados["tx_currency_code"] == "USD"]

    st.subheader("Separación por moneda")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("PEN totales (con duplicados)", len(pen_total))
    c2.metric("USD totales (con duplicados)", len(usd_total))
    c3.metric("PEN sin duplicados", len(pen))
    c4.metric("USD sin duplicados", len(usd))

    st.divider()

    # ---------------------------
    # Descargas seguras
    # ---------------------------
    st.subheader("Descargar resultados")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.download_button(
            "Descargar base sin duplicados",
            exportar_csv(df_sin_duplicados),
            "base_sin_duplicados.csv",
            mime="text/csv"
        )

    with c2:
        st.download_button(
            "Descargar PEN",
            exportar_csv(pen),
            "registros_pen.csv",
            mime="text/csv"
        )

    with c3:
        st.download_button(
            "Descargar USD",
            exportar_csv(usd),
            "registros_usd.csv",
            mime="text/csv"
        )
