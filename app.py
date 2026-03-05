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
# Exportar CSV
# ---------------------------
def exportar_csv(df):
    return df.to_csv(index=False).encode("utf-8")

# ---------------------------
# Leer CSV
# ---------------------------
def leer_csv_seguro(f):
    for sep in [",", ";"]:
        try:
            f.seek(0)
            return pd.read_csv(f, sep=sep, low_memory=False)
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
# PROCESAR
# ---------------------------
if archivo is not None:

    with st.spinner("Procesando archivo..."):
        df = cargar_archivo(archivo)

    df.columns = df.columns.str.lower().str.strip()

    # ---------------------------
    # DETECTAR TIPO OPERACION
    # ---------------------------
    df["tipo_operacion"] = "OTRO"
    
    # Usamos OP_AMOUNT para identificar roles
    if "op_amount" in df.columns:
        df["op_amount"] = pd.to_numeric(df["op_amount"], errors="coerce").fillna(0)
        
        # Positivo = TOTAL (PAGO), Negativo = COMISION
        df.loc[df["op_amount"] > 0, "tipo_operacion"] = "PAGO"
        df.loc[df["op_amount"] < 0, "tipo_operacion"] = "COMISION"

    st.success("Archivo cargado correctamente")

    # Validamos columnas necesarias (psp_tin e invoice_public_id)
    columnas_clave = ["psp_tin", "invoice_public_id", "tx_currency_code"]
    for col in columnas_clave:
        if col not in df.columns:
            st.error(f"Falta la columna crítica: {col}")
            st.stop()

    # Normalización
    df["tx_currency_code"] = df["tx_currency_code"].astype(str).str.upper()
    if "tx_reference" in df.columns:
        df["tx_reference"] = df["tx_reference"].astype(str).str.upper()

    # Dashboard e info inicial (se mantiene tu código)
    df_sin_duplicados = df.drop_duplicates(subset="psp_tin")

    st.subheader("Dashboard financiero")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total registros", len(df))
    c2.metric("Columnas", len(df.columns))
    c3.metric("Registros únicos (PSP_TIN)", len(df_sin_duplicados))

    st.divider()

    # Separación por moneda (se mantiene tu código)
    pen_total = df[df["tx_currency_code"] == "PEN"]
    usd_total = df[df["tx_currency_code"] == "USD"]
    st.subheader("Separación por moneda")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("PEN totales", len(pen_total))
    c2.metric("USD totales", len(usd_total))
    c1.divider()

    # ---------------------------
    # ANALISIS DE COMISIONES (LLAVE COMPUESTA: PSP_TIN + INVOICE)
    # ---------------------------
    st.subheader("Comparación de comisiones")

    porcentaje_contrato = st.number_input("Porcentaje comisión (%)", value=2.30, step=0.01)
    fee_fijo = st.number_input("Fee fijo", value=0.90, step=0.01)
    aplicar_igv = st.checkbox("Aplicar IGV (18%)", value=True)

    # SEPARACIÓN Y CRUCE
    # Usamos psp_tin e invoice_public_id para que el match sea perfecto
    llave = ["psp_tin", "invoice_public_id"]

    pagos = df[df["tipo_operacion"] == "PAGO"][llave + ["op_amount", "tx_reference"]].rename(columns={"op_amount": "tx_amount_pago"})
    fees = df[df["tipo_operacion"] == "COMISION"][llave + ["op_amount"]].rename(columns={"op_amount": "tx_amount_comision"})

    # MERGE OUTER con DOBLE LLAVE para evitar ceros por desorden
    comisiones = pd.merge(pagos, fees, on=llave, how="outer")

    # Limpieza de datos post-merge
    comisiones["tx_amount_pago"] = comisiones["tx_amount_pago"].fillna(0)
    comisiones["tx_amount_comision"] = comisiones["tx_amount_comision"].fillna(0)
    comisiones["comision"] = comisiones["tx_amount_comision"].abs()

    # Cálculo según contrato
    comisiones["comision_contrato"] = 0.0
    mask = comisiones["tx_amount_pago"] != 0
    comisiones.loc[mask, "comision_contrato"] = (
        (comisiones.loc[mask, "tx_amount_pago"] * (porcentaje_contrato / 100)) + fee_fijo
    )

    if aplicar_igv:
        comisiones["comision_contrato"] = comisiones["comision_contrato"] * 1.18

    comisiones["comision_contrato"] = comisiones["comision_contrato"].round(2)
    comisiones["diferencia"] = (comisiones["comision"] - comisiones["comision_contrato"]).round(2)
    comisiones["total_neto"] = comisiones["tx_amount_pago"] - comisiones["comision"]

    # Mostrar Tabla Final
    tabla = comisiones[[
        "psp_tin", "invoice_public_id", "tx_amount_pago", 
        "comision", "comision_contrato", "diferencia", "total_neto"
    ]].fillna(0)

    st.dataframe(tabla)

    # Control de métricas final
    st.subheader("Control de auditoría")
    c1, c2 = st.columns(2)
    c1.metric("Transacciones procesadas", len(tabla))
    c2.metric("Casos con diferencia", len(tabla[tabla["diferencia"] != 0]))

    st.download_button("Descargar reporte detallado", exportar_csv(tabla), "analisis_comisiones_final.csv", mime="text/csv")
