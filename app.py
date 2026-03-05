import streamlit as st
import pandas as pd
import zipfile

st.set_page_config(page_title="Analizador Financiero", layout="wide")

st.title("Analizador Financiero de Bases")

archivo = st.file_uploader(
    "Sube tu archivo Excel, CSV o ZIP",
    type=["xlsx","csv","zip"]
)

# ---------------------------
# EXPORTAR CSV
# ---------------------------
def exportar_csv(df):
    return df.to_csv(index=False).encode("utf-8")

# ---------------------------
# LEER CSV SEGURO
# ---------------------------
def leer_csv_seguro(f):
    for sep in [",",";"]:
        try:
            f.seek(0)
            return pd.read_csv(f,sep=sep,low_memory=False)
        except:
            continue
    raise ValueError("No se pudo leer el CSV")

# ---------------------------
# CARGAR ARCHIVO
# ---------------------------
@st.cache_data
def cargar_archivo(file):

    nombre=file.name.lower()

    if nombre.endswith(".csv"):
        df=leer_csv_seguro(file)

    elif nombre.endswith(".zip"):

        with zipfile.ZipFile(file) as z:

            archivos_csv=[n for n in z.namelist() if n.endswith(".csv")]

            if not archivos_csv:
                raise ValueError("ZIP sin CSV")

            with z.open(archivos_csv[0]) as f:
                df=leer_csv_seguro(f)

    else:
        df=pd.read_excel(file)

    return df


# ---------------------------
# PROCESAR
# ---------------------------
if archivo is not None:

    with st.spinner("Procesando archivo..."):
        df=cargar_archivo(archivo)

    df.columns=df.columns.str.lower().str.strip()

    st.success("Archivo cargado correctamente")

    # normalizar texto
    df["tx_reference"]=df["tx_reference"].astype(str).str.upper()
    df["tx_currency_code"]=df["tx_currency_code"].astype(str).str.upper()

    # convertir números
    df["tx_amount"]=pd.to_numeric(df["tx_amount"],errors="coerce")

    if "tx_transaction_id" in df.columns:
        df["tx_transaction_id"]=pd.to_numeric(df["tx_transaction_id"],errors="coerce")

    if "sf_transaction_related_id" in df.columns:
        df["sf_transaction_related_id"]=pd.to_numeric(df["sf_transaction_related_id"],errors="coerce")

    # ---------------------------
    # DASHBOARD
    # ---------------------------
    st.subheader("Dashboard financiero")

    c1,c2=st.columns(2)

    c1.metric("Total registros",len(df))
    c2.metric("Columnas",len(df.columns))

    st.divider()

    # ---------------------------
    # SEPARACIÓN POR MONEDA
    # ---------------------------
    pen=df[df["tx_currency_code"]=="PEN"]
    usd=df[df["tx_currency_code"]=="USD"]

    st.subheader("Separación por moneda")

    c1,c2=st.columns(2)

    c1.metric("PEN registros",len(pen))
    c2.metric("USD registros",len(usd))

    st.divider()

# ==================================================
# COMISIONES
# ==================================================

    st.subheader("Comparación de comisiones")

    porcentaje_contrato=st.number_input(
        "Porcentaje comisión (%)",
        value=2.30,
        step=0.01
    )

    fee_fijo=st.number_input(
        "Fee fijo",
        value=0.90,
        step=0.01
    )

    aplicar_igv=st.checkbox("Aplicar IGV (18%)",value=True)

    # separar PY y SF
    pagos=df[df["tx_reference"].str.startswith("PY")].copy()
    fees=df[df["tx_reference"].str.startswith("SF")].copy()

    # ---------------------------
    # MERGE CORRECTO
    # ---------------------------
    comisiones=pagos.merge(

        fees[["sf_transaction_related_id","tx_amount"]],

        left_on="tx_transaction_id",
        right_on="sf_transaction_related_id",

        how="left",
        suffixes=("_pago","_comision")

    )

    # comisión real
    comisiones["comision"]=comisiones["tx_amount_comision"].abs()

    # comisión contrato
    comisiones["comision_contrato"]=(
        (comisiones["tx_amount_pago"]*(porcentaje_contrato/100))
        +fee_fijo
    )

    if aplicar_igv:
        comisiones["comision_contrato"]=comisiones["comision_contrato"]*1.18

    comisiones["comision_contrato"]=comisiones["comision_contrato"].round(2)

    # diferencia
    comisiones["diferencia"]=(
        comisiones["comision"]-comisiones["comision_contrato"]
    ).round(2)

    tabla=comisiones[
        [
            "psp_tin",
            "tx_amount_pago",
            "comision",
            "comision_contrato",
            "diferencia"
        ]
    ]

    tabla=tabla.fillna(0)

    # ---------------------------
    # TOTAL NETO
    # ---------------------------
    tabla["total_neto"]=tabla["tx_amount_pago"]-tabla["comision"]

    # ---------------------------
    # RESUMEN FINANCIERO
    # ---------------------------
    total_pagos=tabla["tx_amount_pago"].sum()
    total_comisiones=tabla["comision"].sum()
    total_neto=tabla["total_neto"].sum()

    st.subheader("Resumen financiero")

    c1,c2,c3=st.columns(3)

    c1.metric("Total pagos",round(total_pagos,2))
    c2.metric("Total comisiones",round(total_comisiones,2))
    c3.metric("Total neto",round(total_neto,2))

    st.dataframe(tabla)

    st.download_button(
        "Descargar comparación de comisiones",
        exportar_csv(tabla),
        "comparacion_comisiones.csv",
        mime="text/csv"
    )
