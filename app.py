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
    # DETECTAR TIPO OPERACION (SIN IMPORTAR EL ORDEN)
    # ---------------------------
    df["tipo_operacion"] = "OTRO"
    
    if "op_amount" in df.columns:
        # Forzamos conversión a número
        df["op_amount"] = pd.to_numeric(df["op_amount"], errors="coerce").fillna(0)
        
        # Si es positivo, es el PAGO (Total), sin importar el nombre de la referencia
        df.loc[df["op_amount"] > 0, "tipo_operacion"] = "PAGO"
        
        # Si es negativo, es la COMISION
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

    # eliminar duplicados para el dashboard inicial
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
    c1.metric("PEN totales", len(pen_total))
    c2.metric("USD totales", len(usd_total))
    c3.metric("PEN sin duplicados", len(pen))
    c4.metric("USD sin duplicados", len(usd))

    st.divider()

    # ---------------------------
    # Descargas
    # ---------------------------
    st.subheader("Descargar resultados")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button("Descargar base sin duplicados", exportar_csv(df_sin_duplicados), "base_sin_duplicados.csv", mime="text/csv")
    with c2:
        st.download_button("Descargar PEN", exportar_csv(pen), "registros_pen.csv", mime="text/csv")
    with c3:
        st.download_button("Descargar USD", exportar_csv(usd), "registros_usd.csv", mime="text/csv")

# ==================================================
# ANALISIS DE COMISIONES
# ==================================================

    st.divider()
    st.subheader("Comparación de comisiones")

    porcentaje_contrato = st.number_input("Porcentaje comisión (%)", value=2.30, step=0.01)
    fee_fijo = st.number_input("Fee fijo", value=0.90, step=0.01)
    aplicar_igv = st.checkbox("Aplicar IGV (18%)", value=True)

    if "psp_tin" in df.columns and "op_amount" in df.columns:

        # Extraemos los pagos (positivos) y comisiones (negativos)
        # No importa el orden de las filas en el Excel, aquí se separan por valor
        pagos = df[df["tipo_operacion"] == "PAGO"][["psp_tin", "op_amount"]].rename(columns={"op_amount": "tx_amount_pago"})
        fees = df[df["tipo_operacion"] == "COMISION"][["psp_tin", "op_amount"]].rename(columns={"op_amount": "tx_amount_comision"})

        # MERGE OUTER: Cruza la información del mismo psp_tin sin importar dónde esté cada fila
        comisiones = pd.merge(pagos, fees, on="psp_tin", how="outer")

        # Rellenar con 0 lo que no encuentre
        comisiones["tx_amount_pago"] = comisiones["tx_amount_pago"].fillna(0)
        comisiones["tx_amount_comision"] = comisiones["tx_amount_comision"].fillna(0)

        comisiones["comision"] = comisiones["tx_amount_comision"].abs()

        # Cálculo de contrato: solo si hay un pago registrado
        comisiones["comision_contrato"] = 0.0
        mask_hay_pago = comisiones["tx_amount_pago"] != 0
        
        comisiones.loc[mask_hay_pago, "comision_contrato"] = (
            (comisiones.loc[mask_hay_pago, "tx_amount_pago"] * (porcentaje_contrato / 100))
            + fee_fijo
        )

        if aplicar_igv:
            comisiones["comision_contrato"] = comisiones["comision_contrato"] * 1.18

        comisiones["comision_contrato"] = comisiones["comision_contrato"].round(2)
        comisiones["diferencia"] = (comisiones["comision"] - comisiones["comision_contrato"]).round(2)

        # Preparamos la tabla final respetando todos los registros
        tabla = comisiones[["psp_tin", "tx_amount_pago", "comision", "comision_contrato", "diferencia"]]
        tabla = tabla.fillna(0)
        tabla["total_neto"] = tabla["tx_amount_pago"] - tabla["comision"]

        # Mostramos la tabla completa (sin filtros)
        st.dataframe(tabla)

        st.subheader("Control de comisiones")
        c1, c2 = st.columns(2)
        c1.metric("Total registros analizados", len(tabla))
        c2.metric("Discrepancias", len(tabla[tabla["diferencia"] != 0]))

        st.download_button("Descargar comparación", exportar_csv(tabla), "reporte_comisiones.csv", mime="text/csv")
