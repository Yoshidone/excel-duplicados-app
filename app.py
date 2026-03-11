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

    if "psp_tin" not in df.columns or "tx_currency_code" not in df.columns:
        st.error("Faltan columnas necesarias")
        st.stop()

    df["tx_currency_code"] = df["tx_currency_code"].astype(str).str.upper()

    if "tx_reference" in df.columns:
        df["tx_reference"] = df["tx_reference"].astype(str).str.upper()

    df_sin_duplicados = df.drop_duplicates(subset="psp_tin")

    pen_total = df[df["tx_currency_code"] == "PEN"]
    usd_total = df[df["tx_currency_code"] == "USD"]

    pen = df_sin_duplicados[df_sin_duplicados["tx_currency_code"] == "PEN"]
    usd = df_sin_duplicados[df_sin_duplicados["tx_currency_code"] == "USD"]

    # ==================================================
    # BLOQUE BASES
    # ==================================================
    if modo in [
        "📂 Solo preparar y descargar bases",
        "🧩 Completo (descargas + análisis)"
    ]:

        st.subheader("Dashboard financiero")

        c1, c2, c3 = st.columns(3)
        c1.metric("Total registros", len(df))
        c2.metric("Columnas", len(df.columns))
        c3.metric("Registros sin duplicados", len(df_sin_duplicados))

        st.divider()

        st.subheader("Separación por moneda")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("PEN totales (con duplicados)", len(pen_total))
        c2.metric("USD totales (con duplicados)", len(usd_total))
        c3.metric("PEN sin duplicados", len(pen))
        c4.metric("USD sin duplicados", len(usd))

        st.divider()

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
    # BLOQUE COMISIONES
    # ==================================================
    if modo in [
        "📊 Análisis completo de comisiones",
        "🧩 Completo (descargas + análisis)"
    ]:

        st.divider()
        st.subheader("Comparación de comisiones")

        porcentaje = st.number_input("Porcentaje comisión (%)", value=2.30, step=0.01)
        fee_fijo = st.number_input("Fee fijo (S/)", value=0.90, step=0.01)
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

            # ==============================
            # REDONDEO POR OPERACIÓN (CLAVE)
            # ==============================
            comisiones["tx_amount_pago"] = comisiones["tx_amount_pago"].round(2)
            comisiones["comision_real"] = comisiones["comision_real"].round(2)
            comisiones["comision_base"] = comisiones["comision_base"].round(2)
            comisiones["igv"] = comisiones["igv"].round(2)
            comisiones["comision_final"] = comisiones["comision_final"].round(2)

            comisiones["diferencia"] = (comisiones["comision_real"] - comisiones["comision_final"]).round(2)
            comisiones["total_neto"] = (comisiones["tx_amount_pago"] - comisiones["comision_real"]).round(2)

            tabla = comisiones[
                ["psp_tin","tx_amount_pago","comision_real","comision_base","igv",
                 "comision_final","diferencia","total_neto"]
            ].fillna(0)

            st.dataframe(tabla)

            st.download_button(
                "📥 Descargar comparación de comisiones",
                exportar_csv(tabla),
                "comparacion_comisiones.csv",
                mime="text/csv"
            )

            # ========= DESCARGA POR MESES =========
            if "x_create_date_gmt_peru" in df.columns:

                tabla_descarga = tabla.copy()
                tabla_descarga["fecha"] = pd.to_datetime(
                    comisiones["x_create_date_gmt_peru"],
                    errors="coerce"
                )
                tabla_descarga["periodo"] = tabla_descarga["fecha"].dt.to_period("M")

                buffer_zip = BytesIO()

                with zipfile.ZipFile(buffer_zip, "w", zipfile.ZIP_DEFLATED) as z:
                    for periodo, datos_mes in tabla_descarga.groupby("periodo"):
                        nombre_archivo = f"comparacion_{periodo}.csv"
                        z.writestr(nombre_archivo, exportar_csv(datos_mes.drop(columns=["fecha","periodo"])))

                buffer_zip.seek(0)

                st.download_button(
                    "📥 Descargar comparaciones por meses (ZIP)",
                    data=buffer_zip,
                    file_name="comparaciones_mensuales.zip",
                    mime="application/zip"
                )

            # ================= RESUMEN =================
            st.subheader("Resumen financiero")

            total_recaudo = tabla["tx_amount_pago"].sum()
            total_comisiones = tabla["comision_real"].sum()
            total_base = tabla["comision_base"].sum()
            total_igv = tabla["igv"].sum()
            total_final = tabla["comision_final"].sum()
            total_neto = tabla["total_neto"].sum()
            total_diferencia = tabla["diferencia"].sum()
            operaciones = len(tabla)

            c1, c2, c3 = st.columns(3)
            c4, c5, c6 = st.columns(3)
            c7, _, _ = st.columns(3)

            c1.metric("💰 Total Recaudado", f"S/ {total_recaudo:,.2f}")
            c2.metric("💸 Comisiones Reales", f"S/ {total_comisiones:,.2f}")
            c3.metric("🧾 Comisión Base", f"S/ {total_base:,.2f}")
            c4.metric("🏛 IGV Total", f"S/ {total_igv:,.2f}")
            c5.metric("📑 Comisión Final", f"S/ {total_final:,.2f}")
            c6.metric("🔢 Número de Operaciones", f"{operaciones:,}")
            st.metric("🧮 Total Neto", f"S/ {total_neto:,.2f}")
            c7.metric("⚖️ Diferencia Total", f"S/ {total_diferencia:,.2f}")

            # ================= REPORTE MENSUAL =================
            st.divider()
            st.subheader("📊 Reporte mensual")

            if "x_create_date_gmt_peru" in df.columns:
                tabla["fecha"] = pd.to_datetime(
                    comisiones["x_create_date_gmt_peru"],
                    errors="coerce"
                )
                tabla["periodo"] = tabla["fecha"].dt.to_period("M")

                meses_nombres = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                                 "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

                tipo_cambio = st.number_input("Tipo de cambio PEN → USD", value=3.75, step=0.01)

                for periodo, datos_mes in tabla.groupby("periodo"):
                    año, mes = str(periodo).split("-")
                    nombre_mes = meses_nombres[int(mes)-1]

                    recaudado_mes = datos_mes["tx_amount_pago"].sum()
                    neto_mes = datos_mes["total_neto"].sum()
                    diferencia_mes = datos_mes["diferencia"].sum()
                    operaciones_mes = len(datos_mes)
                    usd_mes = recaudado_mes / tipo_cambio

                    st.markdown(f"### 📅 {nombre_mes} {año}")
                    c1, c2, c3, c4, c5 = st.columns(5)
                    c1.metric("💰 Recaudado", f"S/ {recaudado_mes:,.2f}")
                    c2.metric("💵 USD", f"US$ {usd_mes:,.2f}")
                    c3.metric("🔢 Operaciones", f"{operaciones_mes:,}")
                    c4.metric("🧮 Neto", f"S/ {neto_mes:,.2f}")
                    c5.metric("⚖️ Diferencia", f"S/ {diferencia_mes:,.2f}")
                    st.markdown("---")
