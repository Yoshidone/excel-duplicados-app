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

    # Normalizar nombres de columnas
    df.columns = df.columns.str.lower().str.strip()

    # ---------------------------
    # DETECTAR TIPO OPERACION (CORREGIDO)
    # ---------------------------
    # En tu archivo, la columna 'tipo' ya trae la palabra 'PAGO'
    # Y los registros de comisión suelen tener el monto negativo en 'tx_amount'
    
    df["tipo_operacion"] = "OTRO"

    if "tipo" in df.columns:
        # Asignamos según la columna tipo que ya existe en tu CSV
        df.loc[df["tipo"].astype(str).str.upper() == "PAGO", "tipo_operacion"] = "PAGO"
    
    # Si las comisiones no dicen "COMISION" en la columna tipo, 
    # las detectamos por el prefijo "SF" en tx_reference (según tu data)
    if "tx_reference" in df.columns:
        df.loc[
            df["tx_reference"].astype(str).str.upper().str.startswith("SF", na=False) & 
            (df["tipo_operacion"] != "PAGO"), 
            "tipo_operacion"
        ] = "COMISION"

    st.success("Archivo cargado correctamente")

    # Validaciones de seguridad
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

    # eliminar duplicados para resumen
    df_sin_duplicados = df.drop_duplicates(subset="psp_tin")

    # ---------------------------
    # Dashboard
    # ---------------------------
    st.subheader("Dashboard financiero")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total registros", len(df))
    c2.metric("Columnas", len(df.columns))
    c3.metric("Registros únicos (psp_tin)", len(df_sin_duplicados))

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
    c1.metric("PEN totales", len(pen_total))
    c2.metric("USD totales", len(usd_total))
    c3.metric("PEN únicos", len(pen))
    c4.metric("USD únicos", len(usd))

    st.divider()

    # ---------------------------
    # Descargas
    # ---------------------------
    st.subheader("Descargar resultados")
    c1, c2, c3 = st.columns(3)

    with c1:
        st.download_button("Descargar base sin duplicados", exportar_csv(df_sin_duplicados), "base_sin_duplicados.csv", "text/csv")
    with c2:
        st.download_button("Descargar PEN", exportar_csv(pen), "registros_pen.csv", "text/csv")
    with c3:
        st.download_button("Descargar USD", exportar_csv(usd), "registros_usd.csv", "text/csv")

    # ==================================================
    # ANALISIS DE COMISIONES
    # ==================================================
    st.divider()
    st.subheader("Comparación de comisiones")

    col_inp1, col_inp2, col_inp3 = st.columns(3)
    with col_inp1:
        porcentaje_contrato = st.number_input("Porcentaje comisión (%)", value=2.30, step=0.01)
    with col_inp2:
        fee_fijo = st.number_input("Fee fijo", value=0.90, step=0.01)
    with col_inp3:
        aplicar_igv = st.checkbox("Aplicar IGV (18%)", value=True)

    if "tx_amount" in df.columns:
        # Separar bases
        pagos = df[df["tipo_operacion"] == "PAGO"].copy()
        # Intentamos buscar comisiones. Si no hay registros marcados como COMISION, 
        # el análisis mostrará que faltan datos.
        fees = df[df["tipo_operacion"] == "COMISION"].copy()

        # Asegurar que los montos sean numéricos
        pagos["tx_amount"] = pd.to_numeric(pagos["tx_amount"], errors="coerce")
        fees["tx_amount"] = pd.to_numeric(fees["tx_amount"], errors="coerce")

        # Cruce de datos por psp_tin
        comisiones = pagos.merge(
            fees[["psp_tin", "tx_amount"]],
            on="psp_tin",
            how="left",
            suffixes=("_pago", "_comision")
        )

        # Cálculo de comisión real (valor absoluto)
        comisiones["comision_cobrada"] = comisiones["tx_amount_comision"].abs().fillna(0)

        # Cálculo de comisión según contrato
        comisiones["comision_contrato"] = (
            (comisiones["tx_amount_pago"] * (porcentaje_contrato / 100)) + fee_fijo
        )
        if aplicar_igv:
            comisiones["comision_contrato"] = comisiones["comision_contrato"] * 1.18

        comisiones["comision_contrato"] = comisiones["comision_contrato"].round(2)
        comisiones["diferencia"] = (comisiones["comision_cobrada"] - comisiones["comision_contrato"]).round(2)
        comisiones["total_neto"] = comisiones["tx_amount_pago"] - comisiones["comision_cobrada"]

        # Mostrar Tabla
        tabla_final = comisiones[[
            "psp_tin", "tx_reference", "tx_currency_code", 
            "tx_amount_pago", "comision_cobrada", "comision_contrato", "diferencia", "total_neto"
        ]].fillna(0)

        st.dataframe(tabla_final, use_container_width=True)

        # Métricas de Control
        st.subheader("Control de errores")
        m1, m2 = st.columns(2)
        m1.metric("Transacciones analizadas", len(tabla_final))
        m2.metric("Diferencias detectadas", len(tabla_final[tabla_final["diferencia"] != 0]))

        st.download_button(
            "Descargar reporte de comisiones",
            exportar_csv(tabla_final),
            "reporte_comisiones.csv",
            mime="text/csv"
        )
