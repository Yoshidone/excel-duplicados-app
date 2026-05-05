import streamlit as st
import pandas as pd
import zipfile

st.set_page_config(page_title="Analizador Financiero Payin", layout="wide")
st.title("Analizador Financiero Payin")

archivo = st.file_uploader("Sube tu archivo Excel, CSV o ZIP", type=["xlsx", "csv", "zip"])

modo = st.radio(
    "Modo de uso",
    [
        "📂 Solo preparar y descargar bases",
        "📊 Análisis completo de comisiones",
        "🧩 Completo (descargas + análisis)"
    ]
)

def exportar_csv(df):
    return df.to_csv(index=False).encode("utf-8")

def leer_csv_seguro(f):
    for sep in [",", ";"]:
        try:
            f.seek(0)
            return pd.read_csv(f, sep=sep, decimal=".", encoding="utf-8", low_memory=False)
        except:
            continue
    raise ValueError("No se pudo leer el CSV")

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

# ================= PROCESAR =================
if archivo is not None:

    df = cargar_archivo(archivo)
    df.columns = df.columns.str.lower().str.strip()
    df_original = df.copy()

    st.success("Archivo cargado correctamente")

    if "psp_tin" not in df.columns or "tx_currency_code" not in df.columns:
        st.error("Faltan columnas necesarias")
        st.stop()

    df["tx_currency_code"] = df["tx_currency_code"].astype(str).str.upper()

    if "tx_reference" in df.columns:
        df["tx_reference"] = df["tx_reference"].astype(str).str.upper()

    # ================= FILTRO =================
    st.divider()
    st.subheader("📅 Filtro por mes")

    col1, col2 = st.columns(2)

    if "x_create_date_gmt_peru" in df.columns:
        df["fecha"] = pd.to_datetime(df["x_create_date_gmt_peru"], errors="coerce")
        df["mes"] = df["fecha"].dt.strftime("%Y-%m")
        meses = sorted(df["mes"].dropna().unique())
        mes_sel = col1.selectbox("Selecciona un mes", meses)
    else:
        st.warning("No se encontró columna de fecha")
        st.stop()

    moneda_sel = col2.selectbox("Selecciona moneda", ["PEN", "USD"])

    df = df[
        (df["mes"] == mes_sel) &
        (df["tx_currency_code"] == moneda_sel)
    ]

    simbolo = "S/" if moneda_sel == "PEN" else "$"

    # ================= BASES =================
    df_sin_duplicados = df.drop_duplicates(subset="psp_tin")

    pen_total = df[df["tx_currency_code"] == "PEN"]
    usd_total = df[df["tx_currency_code"] == "USD"]

    pen = df_sin_duplicados[df_sin_duplicados["tx_currency_code"] == "PEN"]
    usd = df_sin_duplicados[df_sin_duplicados["tx_currency_code"] == "USD"]

    if modo in ["📂 Solo preparar y descargar bases", "🧩 Completo (descargas + análisis)"]:

        st.subheader("Dashboard financiero")

        c1, c2, c3 = st.columns(3)
        c1.metric("Total registros", len(df))
        c2.metric("Columnas", len(df.columns))
        c3.metric("Registros sin duplicados", len(df_sin_duplicados))

        st.divider()
        st.subheader("Separación por moneda")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("PEN totales", len(pen_total))
        c2.metric("USD totales", len(usd_total))
        c3.metric("PEN sin duplicados", len(pen))
        c4.metric("USD sin duplicados", len(usd))

        st.divider()
        st.subheader("Descargar resultados")

        c1, c2, c3 = st.columns(3)
        c1.download_button("Descargar base sin duplicados", exportar_csv(df_sin_duplicados), "base.csv")
        c2.download_button("Descargar PEN", exportar_csv(pen), "pen.csv")
        c3.download_button("Descargar USD", exportar_csv(usd), "usd.csv")

    # ================= COMISIONES (TU LÓGICA ORIGINAL) =================
    if modo in ["📊 Análisis completo de comisiones", "🧩 Completo (descargas + análisis)"]:

        st.divider()
        st.subheader(f"Comparación de comisiones ({moneda_sel})")

        porcentaje = st.number_input("Porcentaje comisión (%)", value=2.30)
        fee_fijo = st.number_input(f"Fee fijo ({simbolo})", value=0.90)
        aplicar_igv = st.checkbox("Aplicar IGV (18%)", True)

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
            comisiones["comision_base"] = (comisiones["tx_amount_pago"] * (porcentaje / 100)) + fee_fijo
            comisiones["igv"] = comisiones["comision_base"] * 0.18

            if aplicar_igv:
                comisiones["comision_final"] = comisiones["comision_base"] + comisiones["igv"]
            else:
                comisiones["comision_final"] = comisiones["comision_base"]
                comisiones["igv"] = 0

            comisiones["diferencia"] = (comisiones["comision_real"] - comisiones["comision_final"]).round(2)
            comisiones["total_neto"] = (comisiones["tx_amount_pago"] - comisiones["comision_real"]).round(2)

            tabla = comisiones[
                ["psp_tin","tx_amount_pago","comision_real","comision_base","igv",
                 "comision_final","diferencia","total_neto"]
            ].fillna(0)

            st.dataframe(tabla)

            st.download_button("📥 Descargar comparación de comisiones", exportar_csv(tabla), "comisiones.csv")

    # ================= REPORTE DETALLADO =================
    st.divider()
    st.subheader("📄 Reporte detallado (mes seleccionado)")

    pagos = df[df["tx_reference"].str.startswith("PY", na=False)].copy()
    fees = df[df["tx_reference"].str.startswith("SF", na=False)].copy()

    pagos.rename(columns={"tx_amount": "TOTAL", "tx_reference": "PY_operation_no"}, inplace=True)
    fees.rename(columns={"tx_amount": "COMISION", "tx_reference": "SF_operation_no"}, inplace=True)

    detalle = pagos.merge(
        fees[["psp_tin", "COMISION", "SF_operation_no"]],
        on="psp_tin",
        how="left"
    )

    salida = pd.DataFrame({
        "Com_Nombre": detalle.get("com_nombre", ""),
        "Deb_Nombre": detalle.get("deb_nombre", ""),
        "psp_tin": detalle["psp_tin"],
        "tipo": detalle.get("tipo", ""),
        "X_create_date_GMT_Peru": detalle.get("x_create_date_gmt_peru", ""),
        "PY_operation_no": detalle["PY_operation_no"],
        "SF_operation_no": detalle["SF_operation_no"],
        "TX_currency_code": detalle.get("tx_currency_code", ""),
        "TOTAL": detalle["TOTAL"],
        "COMISION": detalle["COMISION"].abs(),
        "SET_referencia": detalle.get("set_referencia", ""),
        "Fecha Transferencia": detalle.get("x_create_date_gmt_peru", "")
    }).fillna(0)

    st.dataframe(salida)

    st.download_button(
        "📥 Descargar reporte detallado (mes)",
        exportar_csv(salida),
        "reporte_detallado_mes.csv"
    )

    # ================= TODOS LOS MESES =================
    st.subheader("📦 Reporte detallado (todos los meses)")

    df_full = df_original.copy()

    pagos_full = df_full[df_full["tx_reference"].str.startswith("PY", na=False)].copy()
    fees_full = df_full[df_full["tx_reference"].str.startswith("SF", na=False)].copy()

    pagos_full.rename(columns={"tx_amount": "TOTAL", "tx_reference": "PY_operation_no"}, inplace=True)
    fees_full.rename(columns={"tx_amount": "COMISION", "tx_reference": "SF_operation_no"}, inplace=True)

    detalle_full = pagos_full.merge(
        fees_full[["psp_tin", "COMISION", "SF_operation_no"]],
        on="psp_tin",
        how="left"
    )

    reporte_full = salida = pd.DataFrame({
        "Com_Nombre": detalle_full.get("com_nombre", ""),
        "Deb_Nombre": detalle_full.get("deb_nombre", ""),
        "psp_tin": detalle_full["psp_tin"],
        "tipo": detalle_full.get("tipo", ""),
        "X_create_date_GMT_Peru": detalle_full.get("x_create_date_gmt_peru", ""),
        "PY_operation_no": detalle_full["PY_operation_no"],
        "SF_operation_no": detalle_full["SF_operation_no"],
        "TX_currency_code": detalle_full.get("tx_currency_code", ""),
        "TOTAL": detalle_full["TOTAL"],
        "COMISION": detalle_full["COMISION"].abs(),
        "SET_referencia": detalle_full.get("set_referencia", ""),
        "Fecha Transferencia": detalle_full.get("x_create_date_gmt_peru", "")
    }).fillna(0)

    st.download_button(
        "📥 Descargar reporte detallado (todos)",
        exportar_csv(reporte_full),
        "reporte_detallado_todos.csv"
    )
