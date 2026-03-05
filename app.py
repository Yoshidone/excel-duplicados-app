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
# Leer CSV seguro
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
# Procesar archivo
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

    if "tx_reference" not in df.columns:
        st.error("No existe la columna tx_reference")
        st.stop()

    if "tx_amount" not in df.columns:
        st.error("No existe la columna tx_amount")
        st.stop()

    # ---------------------------
    # eliminar duplicados
    # ---------------------------
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

    pen_total = df[df["tx_currency_code"] == "PEN"]
    usd_total = df[df["tx_currency_code"] == "USD"]

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
    # Identificar PY y SF
    # ---------------------------

    pagos = df[df["tx_reference"].str.startswith("PY", na=False)]
    fees = df[df["tx_reference"].str.startswith("SF", na=False)]

    total_pagos = len(pagos)
    total_fees = len(fees)

    comision_total = fees["tx_amount"].abs().sum()

    comision_pen = fees[fees["tx_currency_code"] == "PEN"]["tx_amount"].abs().sum()
    comision_usd = fees[fees["tx_currency_code"] == "USD"]["tx_amount"].abs().sum()

    st.subheader("Análisis de comisiones")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Transacciones (PY)", total_pagos)
    c2.metric("Líneas de comisión (SF)", total_fees)
    c3.metric("Comisión total", f"{comision_total:,.2f}")
    c4.metric("Comisión PEN", f"{comision_pen:,.2f}")

    st.metric("Comisión USD", f"{comision_usd:,.2f}")

    st.divider()

    # ---------------------------
    # Análisis de revenue
    # ---------------------------

    volumen_total = pagos["tx_amount"].abs().sum()

    if volumen_total > 0:
        porcentaje_comision = (comision_total / volumen_total) * 100
    else:
        porcentaje_comision = 0

    st.subheader("Análisis de revenue")

    c1, c2, c3 = st.columns(3)

    c1.metric("Volumen total procesado", f"{volumen_total:,.2f}")
    c2.metric("Comisiones totales", f"{comision_total:,.2f}")
    c3.metric("% promedio comisión", f"{porcentaje_comision:.2f}%")

    st.divider()

    # ---------------------------
    # Descargas
    # ---------------------------
    st.subheader("Descargar resultados")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.download_button(
            "Base sin duplicados",
            exportar_csv(df_sin_duplicados),
            "base_sin_duplicados.csv",
            mime="text/csv"
        )

    with c2:
        st.download_button(
            "Registros PEN",
            exportar_csv(pen),
            "registros_pen.csv",
            mime="text/csv"
        )

    with c3:
        st.download_button(
            "Registros USD",
            exportar_csv(usd),
            "registros_usd.csv",
            mime="text/csv"
        )

    with c4:
        st.download_button(
            "Solo comisiones (SF)",
            exportar_csv(fees),
            "comisiones_sf.csv",
            mime="text/csv"
        )

    # ---------------------------
    # Comisión por cliente
    # ---------------------------

    st.divider()
    st.subheader("Comisión por cliente")

    comisiones_cliente = pagos.merge(
        fees[["psp_tin", "tx_amount"]],
        on="psp_tin",
        how="left",
        suffixes=("_pago", "_comision")
    )

    comisiones_cliente["comision"] = comisiones_cliente["tx_amount_comision"].abs()

    # evitar valores nulos
    comisiones_cliente["comision"] = comisiones_cliente["comision"].fillna(0)

    # evitar división por 0
    comisiones_cliente["tx_amount_pago"] = comisiones_cliente["tx_amount_pago"].replace(0, pd.NA)

    # porcentaje comisión corregido
    comisiones_cliente["porcentaje_comision"] = (
        (comisiones_cliente["comision"] /
        comisiones_cliente["tx_amount_pago"]) * 100
    ).round(2)

    columnas_mostrar = [
        "deb_nombre",
        "deb_doc",
        "tx_amount_pago",
        "comision",
        "porcentaje_comision",
        "tx_currency_code"
    ]

    columnas_existentes = [c for c in columnas_mostrar if c in comisiones_cliente.columns]

    tabla_final = comisiones_cliente[columnas_existentes]

    st.dataframe(tabla_final)

    st.download_button(
        "Descargar comisión por cliente",
        exportar_csv(tabla_final),
        "comisiones_por_cliente.csv",
        mime="text/csv"
    )
