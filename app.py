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
# MODO DE USO
# ---------------------------
modo = st.radio(
    "Modo de uso",
    [
        "📂 Solo preparar y descargar bases",
        "📊 Análisis completo de comisiones",
        "🧩 Completo (descargas + análisis)"
    ]
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
            return pd.read_csv(
                f,
                sep=sep,
                decimal=".",
                encoding="utf-8",
                low_memory=False
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
        return leer_csv_seguro(file)

    elif nombre.endswith(".zip"):
        with zipfile.ZipFile(file) as z:
            for nombre_archivo in z.namelist():
                if nombre_archivo.lower().endswith(".csv"):
                    with z.open(nombre_archivo) as f:
                        return leer_csv_seguro(f)
                if nombre_archivo.lower().endswith((".xlsx", ".xls")):
                    with z.open(nombre_archivo) as f:
                        return pd.read_excel(f, engine="openpyxl")
        raise ValueError("ZIP sin CSV ni Excel")
    else:
        return pd.read_excel(file, engine="openpyxl")

# ---------------------------
# PROCESAR
# ---------------------------
if archivo is not None:

    df = cargar_archivo(archivo)
    df.columns = df.columns.str.lower().str.strip()
    st.success("Archivo cargado correctamente")

    if "psp_tin" not in df.columns:
        st.error("Falta columna psp_tin")
        st.stop()

    if "tx_currency_code" not in df.columns:
        posibles = [c for c in df.columns if "currency" in c]
        if posibles:
            df.rename(columns={posibles[0]: "tx_currency_code"}, inplace=True)
        else:
            df["tx_currency_code"] = ""

    df["tx_currency_code"] = df["tx_currency_code"].astype(str).str.upper()

    if "tx_reference" in df.columns:
        df["tx_reference"] = df["tx_reference"].astype(str).str.upper()

    # ==================================================
    # COMISIONES
    # ==================================================
    if modo in [
        "📊 Análisis completo de comisiones",
        "🧩 Completo (descargas + análisis)"
    ]:

        st.subheader("Comparación de comisiones")

        porcentaje = st.number_input("Porcentaje comisión (%)", value=2.30, step=0.01)
        fee_fijo = st.number_input("Fee fijo (S/)", value=0.90, step=0.01)
        aplicar_igv = st.checkbox("Aplicar IGV (18%)", value=True)

        if "tx_reference" in df.columns and "tx_amount" in df.columns:

            pagos = df[df["tx_reference"].str.startswith("PY", na=False)].copy()
            fees = df[df["tx_reference"].str.startswith("SF", na=False)].copy()

            pagos = pagos.rename(columns={"tx_amount": "tx_amount_pago"})
            fees = fees.rename(columns={"tx_amount": "tx_amount_comision"})

            comisiones = pagos.merge(
                fees[["psp_tin", "tx_amount_comision"]],
                on="psp_tin",
                how="left"
            )

            # MONEDA segura
            moneda_map = df[["psp_tin","tx_currency_code"]].drop_duplicates("psp_tin")
            comisiones = comisiones.merge(moneda_map, on="psp_tin", how="left")
            comisiones.rename(columns={"tx_currency_code":"MONEDA"}, inplace=True)

            comisiones["tx_amount_pago"] = pd.to_numeric(comisiones["tx_amount_pago"], errors="coerce")
            comisiones["tx_amount_comision"] = pd.to_numeric(comisiones["tx_amount_comision"], errors="coerce")

            comisiones["comision_real"] = comisiones["tx_amount_comision"].abs()

            comisiones["comision_base"] = (
                (comisiones["tx_amount_pago"] * (porcentaje / 100)) + fee_fijo
            )

            comisiones["igv"] = comisiones["comision_base"] * 0.18

            if aplicar_igv:
                comisiones["comision_final"] = comisiones["comision_base"] + comisiones["igv"]
            else:
                comisiones["comision_final"] = comisiones["comision_base"]
                comisiones["igv"] = 0

            comisiones["comision_base"] = comisiones["comision_base"].round(2)
            comisiones["igv"] = comisiones["igv"].round(2)
            comisiones["comision_final"] = comisiones["comision_final"].round(2)

            comisiones["diferencia"] = (
                comisiones["comision_real"] - comisiones["comision_final"]
            ).round(2)

            comisiones["total_neto"] = (
                comisiones["tx_amount_pago"] - comisiones["comision_real"]
            ).round(2)

            tabla = comisiones[
                [
                    "psp_tin","MONEDA","tx_amount_pago","comision_real",
                    "comision_base","igv","comision_final",
                    "diferencia","total_neto"
                ]
            ].fillna(0)

            st.dataframe(tabla)

            st.download_button(
                "📥 Descargar comparación de comisiones",
                exportar_csv(tabla),
                "comparacion_comisiones.csv",
                mime="text/csv"
            )
