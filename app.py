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
# Leer CSV MEJORADO
# ---------------------------
def leer_csv_seguro(f):
    for sep in [",", ";"]:
        try:
            f.seek(0)
            df = pd.read_csv(
                f,
                sep=sep,
                decimal=".",
                encoding="utf-8",
                low_memory=False
            )
            return df
        except:
            continue
    raise ValueError("No se pudo leer el CSV")

# ---------------------------
# Cargar archivo (ZIP inteligente)
# ---------------------------
@st.cache_data
def cargar_archivo(file):

    nombre = file.name.lower()

    if nombre.endswith(".csv"):
        return leer_csv_seguro(file)

    elif nombre.endswith(".zip"):
        with zipfile.ZipFile(file) as z:

            archivos = z.namelist()

            archivos_csv = [n for n in archivos if n.lower().endswith(".csv")]
            if archivos_csv:
                with z.open(archivos_csv[0]) as f:
                    return leer_csv_seguro(f)

            archivos_excel = [n for n in archivos if n.lower().endswith((".xlsx", ".xls"))]
            if archivos_excel:
                with z.open(archivos_excel[0]) as f:
                    return pd.read_excel(f)

            raise ValueError("El ZIP no contiene CSV ni Excel")

    else:
        return pd.read_excel(file)


# ---------------------------
# PROCESAR
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

    if "tx_reference" in df.columns and "tx_amount" in df.columns:

        pagos = df[df["tx_reference"].str.startswith("PY", na=False)]
        fees = df[df["tx_reference"].str.startswith("SF", na=False)]

        comisiones = pagos.merge(
            fees[["psp_tin", "tx_amount"]],
            on="psp_tin",
            how="left",
            suffixes=("_pago", "_comision")
        )

        comisiones["tx_amount_pago"] = pd.to_numeric(
            comisiones["tx_amount_pago"], errors="coerce"
        )

        comisiones["tx_amount_comision"] = pd.to_numeric(
            comisiones["tx_amount_comision"], errors="coerce"
        )

        comisiones["comision"] = comisiones["tx_amount_comision"].abs()

        comisiones["comision_contrato"] = (
            (comisiones["tx_amount_pago"] * (porcentaje_contrato / 100))
            + fee_fijo
        )

        if aplicar_igv:
            comisiones["comision_contrato"] *= 1.18

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
        ].fillna(0)

        tabla["total_neto"] = tabla["tx_amount_pago"] - tabla["comision"]

        st.dataframe(tabla)

        # ===============================
        # TABLERO FINANCIERO
        # ===============================
        st.subheader("Resumen financiero")

        total_recaudo = tabla["tx_amount_pago"].sum()
        total_comisiones = tabla["comision"].sum()
        total_contrato = tabla["comision_contrato"].sum()
        total_diferencia = tabla["diferencia"].sum()
        total_neto = tabla["total_neto"].sum()

        c1, c2, c3 = st.columns(3)
        c4, c5 = st.columns(2)

        c1.metric("💰 Total Recaudado", f"S/ {total_recaudo:,.2f}")
        c2.metric("💸 Total Comisiones", f"S/ {total_comisiones:,.2f}")
        c3.metric("📑 Total Comisión Contrato", f"S/ {total_contrato:,.2f}")
        c4.metric("⚖️ Diferencia Total", f"S/ {total_diferencia:,.2f}")
        c5.metric("🧮 Total Neto", f"S/ {total_neto:,.2f}")
