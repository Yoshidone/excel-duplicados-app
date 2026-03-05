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

def exportar_csv(df):
    return df.to_csv(index=False).encode("utf-8")

def leer_csv_seguro(f):
    for sep in [",", ";"]:
        try:
            f.seek(0)
            return pd.read_csv(f, sep=sep, low_memory=False)
        except:
            continue
    raise ValueError("No se pudo leer el CSV")

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

if archivo is not None:
    with st.spinner("Procesando archivo..."):
        df = cargar_archivo(archivo)

    df.columns = df.columns.str.lower().str.strip()

    # --- DETECTAR TIPOS (Basado en tu archivo real) ---
    df["tx_amount"] = pd.to_numeric(df["tx_amount"], errors="coerce")
    
    # En tu data: 'tipo' PAGO es el ingreso. 
    # Las comisiones suelen ser registros con monto negativo o marcados distinto.
    df["tipo_operacion"] = "OTRO"
    if "tipo" in df.columns:
        df.loc[df["tipo"].astype(str).str.upper() == "PAGO", "tipo_operacion"] = "PAGO"
    
    # Identificamos comisiones: registros que NO son PAGO y tienen monto negativo
    df.loc[(df["tipo_operacion"] != "PAGO") & (df["tx_amount"] < 0), "tipo_operacion"] = "COMISION"

    st.success("Archivo procesado")

    # --- FILTROS DE MONEDA ---
    if "tx_currency_code" in df.columns:
        df["tx_currency_code"] = df["tx_currency_code"].astype(str).str.upper()
        monedas = df["tx_currency_code"].unique()
        moneda_sel = st.selectbox("Selecciona la moneda para el análisis", monedas)
        df_filtrado = df[df["tx_currency_code"] == moneda_sel]
    else:
        df_filtrado = df

    # --- ANÁLISIS DE COMISIONES (AGRUPADO POR PSP_TIN) ---
    st.divider()
    st.subheader(f"Comparación de Comisiones - {moneda_sel if 'tx_currency_code' in df.columns else ''}")

    col_inp1, col_inp2, col_inp3 = st.columns(3)
    porcentaje_contrato = col_inp1.number_input("Porcentaje comisión (%)", value=2.30, step=0.01)
    fee_fijo = col_inp2.number_input("Fee fijo", value=0.90, step=0.01)
    aplicar_igv = col_inp3.checkbox("Aplicar IGV (18%)", value=True)

    # Agrupamos por psp_tin para consolidar Pago y Comisión en una sola fila
    # Sumamos los montos positivos como 'Monto Pago' y los negativos como 'Comisión'
    resumen = df_filtrado.groupby("psp_tin").agg({
        "tx_amount": [
            ("monto_pago", lambda x: x[x > 0].sum()),
            ("comision_cobrada", lambda x: x[x < 0].abs().sum())
        ],
        "tx_reference": "first" # Para mantener la referencia visual
    })
    
    # Limpiar jerarquía de columnas del groupby
    resumen.columns = resumen.columns.get_level_values(1)
    resumen = resumen.reset_index()

    # --- CÁLCULOS DEL CONTRATO ---
    def calcular_esperado(monto):
        if monto <= 0: return 0.0
        comm = (monto * (porcentaje_contrato / 100)) + fee_fijo
        if aplicar_igv:
            comm = comm * 1.18
        return round(comm, 2)

    resumen["comision_contrato"] = resumen["monto_pago"].apply(calcular_esperado)
    resumen["diferencia"] = (resumen["comision_cobrada"] - resumen["comision_contrato"]).round(2)
    resumen["neto_final"] = resumen["monto_pago"] - resumen["comision_cobrada"]

    # --- ORDENAR Y MOSTRAR ---
    # Ponemos las diferencias más grandes arriba
    resumen = resumen.sort_values(by="diferencia", ascending=False)

    st.dataframe(resumen, use_container_width=True)

    # --- MÉTRICAS ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Procesado", f"{resumen['monto_pago'].sum():,.2f}")
    c2.metric("Total Comisiones Cobradas", f"{resumen['comision_cobrada'].sum():,.2f}")
    
    dif_total = resumen["diferencia"].sum()
    c3.metric("Diferencia Total (Vs Contrato)", f"{dif_total:,.2f}", delta=-dif_total, delta_color="inverse")

    st.download_button(
        "Descargar Reporte Ordenado",
        exportar_csv(resumen),
        "analisis_final.csv",
        "text/csv"
    )
