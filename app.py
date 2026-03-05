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
    # DETECTAR TIPO OPERACION (Basado en OP_AMOUNT)
    # ---------------------------

    df["tipo_operacion"] = "OTRO"
    
    # Convertimos OP_AMOUNT a numérico por seguridad
    if "op_amount" in df.columns:
        df["op_amount"] = pd.to_numeric(df["op_amount"], errors="coerce").fillna(0)

        # REGLA: OP_AMOUNT POSITIVO = PAGO (TOTAL)
        df.loc[df["op_amount"] > 0, "tipo_operacion"] = "PAGO"

        # REGLA: OP_AMOUNT NEGATIVO = COMISION
        df.loc[df["op_amount"] < 0, "tipo_operacion"] = "COMISION"

    st.success("Archivo cargado correctamente")

    if "psp_tin" not in df.columns:
        st.error("No existe la columna psp_tin")
        st.stop()

    if "tx_currency_code" not in df.columns:
        st.error("No existe la columna tx_currency_code")
        st.stop()

    # normalizar moneda
    df["tx_currency_code"] = df["tx_currency_code"].astype(str).str.upper()

    # normalizar referencia
    if "tx_reference" in df.columns:
        df["tx_reference"] = df["tx_reference"].astype(str).str.upper()

    # eliminar duplicados
    df_sin_duplicados = df.drop_duplicates(subset="psp_tin")

    # ---------------------------
    # Dashboard
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
    # Descargas
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

# ==================================================
# ANALISIS DE COMISIONES
# ==================================================

    st.divider()
    st.subheader("Comparación de comisiones")

    porcentaje_contrato = st.number_input(
        "Porcentaje comisión (%)",
        value=2.30,
        step=0.01
    )

    fee_fijo = st.number_input(
        "Fee fijo",
        value=0.90,
        step=0.01
    )

    aplicar_igv = st.checkbox("Aplicar IGV (18%)", value=True)

    if "tx_reference" in df.columns and "op_amount" in df.columns:

        # Separamos usando OP_AMOUNT para asegurar que nada sea 0
        pagos = df[df["tipo_operacion"] == "PAGO"][["psp_tin", "op_amount"]].rename(columns={"op_amount": "tx_amount_pago"})
        fees = df[df["tipo_operacion"] == "COMISION"][["psp_tin", "op_amount"]].rename(columns={"op_amount": "tx_amount_comision"})

        # MERGE OUTER para unir ambas filas por PSP_TIN
        comisiones = pd.merge(pagos, fees, on="psp_tin", how="outer")

        comisiones["tx_amount_pago"] = comisiones["tx_amount_pago"].fillna(0)
        comisiones["tx_amount_comision"] = comisiones["tx_amount_comision"].fillna(0)

        comisiones["comision"] = comisiones["tx_amount_comision"].abs()

        # Calculamos contrato
        comisiones["comision_contrato"] = 0.0
        mask = comisiones["tx_amount_pago"] > 0
        comisiones.loc[mask, "comision_contrato"] = (
            (comisiones.loc[mask, "tx_amount_pago"] * (porcentaje_contrato / 100))
            + fee_fijo
        )

        if aplicar_igv:
            comisiones["comision_contrato"] = comisiones["comision_contrato"] * 1.18

        comisiones["comision_contrato"] = comisiones["comision_contrato"].round(2)

        comisiones["diferencia"] = (
            comisiones["comision"] - comisiones["comision_contrato"]
        ).round(2)

        tabla = comisiones[
            [
                "psp_tin",
                "tx_amount_pago",
                "comision",
                "comision_contrato",
                "diferencia"
            ]
        ]

        tabla = tabla.fillna(0)
        
        # Filtramos para mostrar solo donde hubo una venta real
        tabla = tabla[tabla["tx_amount_pago"] > 0]
        
        tabla["total_neto"] = tabla["tx_amount_pago"] - tabla["comision"]

        st.dataframe(tabla)

        st.subheader("Control de comisiones")

        c1, c2 = st.columns(2)

        c1.metric("Total transacciones analizadas", len(tabla))

        c2.metric(
            "Diferencias detectadas",
            len(tabla[tabla["diferencia"] != 0])
        )

        st.download_button(
            "Descargar reporte de comparación",
            exportar_csv(tabla),
            "comparacion_comisiones.csv",
            mime="text/csv"
        )
