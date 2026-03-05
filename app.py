import streamlit as st
import pandas as pd
import zipfile

st.set_page_config(page_title="Analizador Financiero", layout="wide")
st.title("Analizador Financiero de Bases")

archivo = st.file_uploader(
    "Sube tu archivo Excel, CSV o ZIP",
    type=["xlsx", "csv", "zip"]
)

# ---------------------------
# Configuración BIG DATA
# ---------------------------
COLUMNAS_NECESARIAS = [
    "psp_tin",
    "tx_currency_code",
    "tx_reference",
    "tx_amount"
]

CHUNK_SIZE = 500_000  # medio millón de filas por bloque

# ---------------------------
# Exportar CSV
# ---------------------------
def exportar_csv(df):
    return df.to_csv(index=False).encode("utf-8")

# ---------------------------
# Leer CSV MASIVO
# ---------------------------
def leer_csv_masivo(f):

    chunks = []

    for sep in [",", ";"]:
        try:
            f.seek(0)

            for chunk in pd.read_csv(
                f,
                sep=sep,
                usecols=lambda c: c.lower() in COLUMNAS_NECESARIAS,
                dtype=str,
                encoding="utf-8",
                chunksize=CHUNK_SIZE
            ):
                chunks.append(chunk)

            df = pd.concat(chunks, ignore_index=True)

            # Normalizar decimales latinos
            for col in df.columns:
                muestra = df[col].astype(str).str.replace(".", "", regex=False)
                if muestra.str.contains(",", regex=False).any():
                    df[col] = (
                        df[col]
                        .astype(str)
                        .str.replace(".", "", regex=False)
                        .str.replace(",", ".", regex=False)
                    )

            return df

        except:
            continue

    raise ValueError("No se pudo leer el CSV")

# ---------------------------
# Cargar archivo MASIVO
# ---------------------------
@st.cache_data
def cargar_archivo(file):

    nombre = file.name.lower()

    # Advertencia tamaño
    if file.size > 100_000_000:
        st.warning("⚠️ Archivo muy pesado. CSV recomendado para máxima velocidad.")

    # CSV
    if nombre.endswith(".csv"):
        return leer_csv_masivo(file)

    # ZIP
    elif nombre.endswith(".zip"):
        with zipfile.ZipFile(file) as z:

            archivos = z.namelist()

            archivos_csv = [n for n in archivos if n.lower().endswith(".csv")]
            if archivos_csv:
                with z.open(archivos_csv[0]) as f:
                    return leer_csv_masivo(f)

            archivos_excel = [n for n in archivos if n.lower().endswith((".xlsx", ".xls"))]
            if archivos_excel:
                with z.open(archivos_excel[0]) as f:
                    return pd.read_excel(
                        f,
                        engine="openpyxl",
                        usecols=lambda c: c.lower() in COLUMNAS_NECESARIAS,
                        dtype=str
                    )

            raise ValueError("El ZIP no contiene CSV ni Excel")

    # Excel directo (optimizado)
    else:
        return pd.read_excel(
            file,
            engine="openpyxl",
            usecols=lambda c: c.lower() in COLUMNAS_NECESARIAS,
            dtype=str
        )
