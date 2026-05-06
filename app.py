import streamlit as st
import pandas as pd
import polars as pl
import zipfile
import io
import gc
import pyarrow

st.set_page_config(page_title="Analizador Financiero Payin", layout="wide")

st.markdown("""
<style>
.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}

[data-testid="metric-container"] {
    background-color: #111827;
    padding: 15px;
    border-radius: 12px;
    border: 1px solid #374151;
}

[data-testid="metric-container"] label {
    color: #9CA3AF;
}

[data-testid="metric-container"] div {
    color: white;
}
</style>
""", unsafe_allow_html=True)

st.title("Analizador Financiero Payin")

# ================= SUBIR VARIOS ARCHIVOS =================
archivos = st.file_uploader(
    "Sube tu archivo Excel, CSV, PARQUET o ZIP",
    type=["xlsx", "csv", "zip", "parquet"],
    accept_multiple_files=True
)

def exportar_csv(df):
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue()

# ================= LEER CSV RAPIDO CON POLARS PURO =================
def leer_csv_seguro(f):
    contenido = f.read() if hasattr(f, "read") else f

    if isinstance(contenido, bytes):
        buffer = io.BytesIO(contenido)
    else:
        buffer = contenido

    for sep in [",", ";"]:
        try:
            buffer.seek(0)
            df = pl.read_csv(
                buffer,
                separator=sep,
                ignore_errors=True,
                infer_schema_length=500,
                low_memory=False,
                rechunk=True,
            )
            return df.to_pandas()
        except Exception:
            continue

    raise ValueError("No se pudo leer el CSV")

# ================= LEER EXCEL =================
def leer_excel_seguro(f):
    contenido = f.read() if hasattr(f, "read") else f

    return pd.read_excel(
        io.BytesIO(contenido),
        engine="openpyxl",
        dtype_backend="numpy_nullable",
    )

# ================= LEER PARQUET =================
def leer_parquet_seguro(f):
    contenido = f.read() if hasattr(f, "read") else f
    return pd.read_parquet(io.BytesIO(contenido))

# ================= CARGAR ARCHIVOS =================
@st.cache_data(show_spinner=False, max_entries=10)
def cargar_archivo(file_bytes: bytes, nombre: str) -> pd.DataFrame:

    nombre = nombre.lower()

    # ================= CSV =================
    if nombre.endswith(".csv"):
        return leer_csv_seguro(io.BytesIO(file_bytes))

    # ================= PARQUET =================
    elif nombre.endswith(".parquet"):
        return leer_parquet_seguro(io.BytesIO(file_bytes))

    # ================= ZIP =================
    elif nombre.endswith(".zip"):

        dfs_zip = []

        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:

            for nombre_archivo in z.namelist():

                # ================= CSV EN ZIP =================
                if nombre_archivo.lower().endswith(".csv"):

                    with z.open(nombre_archivo) as f:
                        contenido = f.read()

                    df_zip = leer_csv_seguro(io.BytesIO(contenido))
                    df_zip.columns = df_zip.columns.str.lower().str.strip()
                    dfs_zip.append(df_zip)

                # ================= EXCEL EN ZIP =================
                elif nombre_archivo.lower().endswith((".xlsx", ".xls")):

                    with z.open(nombre_archivo) as f:
                        contenido = f.read()

                    df_zip = leer_excel_seguro(io.BytesIO(contenido))
                    df_zip.columns = df_zip.columns.str.lower().str.strip()
                    dfs_zip.append(df_zip)

                # ================= PARQUET EN ZIP =================
                elif nombre_archivo.lower().endswith(".parquet"):

                    with z.open(nombre_archivo) as f:
                        contenido = f.read()

                    df_zip = leer_parquet_seguro(io.BytesIO(contenido))
                    df_zip.columns = df_zip.columns.str.lower().str.strip()
                    dfs_zip.append(df_zip)

        if dfs_zip:
            return pd.concat(dfs_zip, ignore_index=True)

        raise ValueError("ZIP sin CSV, Excel ni Parquet")

    # ================= EXCEL =================
    else:
        return leer_excel_seguro(io.BytesIO(file_bytes))

# ================= NORMALIZAR COLUMNAS =================
def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:

    df.columns = df.columns.str.lower().str.strip()

    if "tx_currency_code" in df.columns:
        df["tx_currency_code"] = df["tx_currency_code"].astype(str).str.upper()

    if "tx_reference" in df.columns:
        df["tx_reference"] = df["tx_reference"].astype(str).str.upper()

    return df

# ================= PROCESAR =================
if archivos:

    placeholder_carga = st.empty()
    placeholder_carga.info("⏳ Procesando archivos...")

    dfs = []

    for archivo in archivos:

        file_bytes = archivo.read()
        df_temp = cargar_archivo(file_bytes, archivo.name)
        df_temp = normalizar_columnas(df_temp)
        dfs.append(df_temp)

    df = pd.concat(dfs, ignore_index=True)

    del dfs
    gc.collect()

    df_original = df.copy()

    placeholder_carga.success("✅ Archivo cargado correctamente")

    st.divider()

    opcion_reporte = st.radio(
        "Selecciona qué deseas visualizar:",
        ["Comparación de comisiones", "Reporte detallado", "Ambas"],
        horizontal=True,
        index=None
    )

    if opcion_reporte:

        st.divider()

        col1, col2 = st.columns(2)

        df["fecha"] = pd.to_datetime(
            df["x_create_date_gmt_peru"],
            errors="coerce",
            utc=False,
            format="mixed",
        )

        df["mes"] = df["fecha"].dt.strftime("%Y-%m")

        mes_sel = col1.selectbox(
            "Selecciona un mes",
            sorted(df["mes"].dropna().unique())
        )

        moneda_sel = col2.selectbox(
            "Selecciona moneda",
            ["PEN", "USD"]
        )

        mask = (df["mes"] == mes_sel) & (df["tx_currency_code"] == moneda_sel)
        df = df.loc[mask].copy()

        simbolo = "S/" if moneda_sel == "PEN" else "$"

        # ================= COMPARACION =================
        if opcion_reporte in ["Comparación de comisiones", "Ambas"]:

            st.divider()
            st.subheader(f"Comparación de comisiones ({moneda_sel})")

            porcentaje = st.number_input("Porcentaje comisión (%)", value=2.30)
            fee_fijo = st.number_input(f"Fee fijo ({simbolo})", value=0.90)

            mask_py = df["tx_reference"].str.startswith("PY", na=False)
            mask_sf = df["tx_reference"].str.startswith("SF", na=False)

            pagos = df.loc[mask_py].copy()
            fees = df.loc[mask_sf, ["psp_tin", "tx_amount"]].copy()

            comisiones = pagos.merge(
                fees,
                on="psp_tin",
                how="left",
                suffixes=("_pago", "_comision")
            )

            comisiones["tx_amount_pago"] = pd.to_numeric(
                comisiones["tx_amount_pago"],
                errors="coerce"
            )

            comisiones["tx_amount_comision"] = pd.to_numeric(
                comisiones["tx_amount_comision"],
                errors="coerce"
            )

            base = comisiones["tx_amount_pago"] * (porcentaje / 100) + fee_fijo
            igv = (base * 0.18).round(2)

            comisiones = comisiones.assign(
                comision_real=comisiones["tx_amount_comision"].abs(),
                comision_base=base.round(2),
                igv=igv,
                comision_final=(base + igv).round(2),
            )

            comisiones["diferencia"] = (
                comisiones["comision_real"] - comisiones["comision_final"]
            ).round(2)

            comisiones["total_neto"] = (
                comisiones["tx_amount_pago"] - comisiones["comision_real"]
            ).round(2)

            cols_tabla = [
                "psp_tin",
                "tx_amount_pago",
                "comision_real",
                "comision_base",
                "igv",
                "comision_final",
                "diferencia",
                "total_neto"
            ]

            tabla = comisiones[cols_tabla].fillna(0)

            st.dataframe(tabla.head(500), use_container_width=True)

            st.download_button(
                "📥 Descargar comparación de comisiones",
                exportar_csv(tabla),
                "comisiones.csv"
            )

            st.subheader("📊 Resumen financiero")

            total_recaudo = tabla["tx_amount_pago"].sum()
            total_base = tabla["comision_base"].sum()
            total_igv = round(total_base * 0.18, 2)
            total_final = round(total_base + total_igv, 2)
            total_comisiones = round(tabla["comision_real"].sum(), 2)
            total_neto = round(tabla["total_neto"].sum(), 2)
            total_diferencia = round(total_comisiones - total_final, 2)
            operaciones = tabla["psp_tin"].nunique()

            c1, c2, c3, c4 = st.columns(4)

            c1.metric("💰 Recaudado", f"{simbolo} {total_recaudo:,.2f}")
            c2.metric("💸 Comisiones", f"{simbolo} {total_comisiones:,.2f}")
            c3.metric("🧾 Base", f"{simbolo} {total_base:,.2f}")
            c4.metric("🏛 IGV", f"{simbolo} {total_igv:,.2f}")

            c5, c6, c7, c8 = st.columns(4)

            c5.metric("📑 Final", f"{simbolo} {total_final:,.2f}")
            c6.metric("⚖️ Diferencia", f"{simbolo} {total_diferencia:,.2f}")
            c7.metric("🔢 Operaciones", f"{operaciones:,}")
            c8.metric("🧮 Neto", f"{simbolo} {total_neto:,.2f}")

        # ================= REPORTE DETALLADO =================
        if opcion_reporte in ["Reporte detallado", "Ambas"]:

            st.divider()
            st.subheader("📄 Reporte detallado (mes seleccionado)")

            mask_py = df["tx_reference"].str.startswith("PY", na=False)
            mask_sf = df["tx_reference"].str.startswith("SF", na=False)

            pagos = df.loc[mask_py].copy()
            fees = df.loc[mask_sf].copy()

            pagos.rename(
                columns={
                    "tx_amount": "RECAUDO",
                    "tx_reference": "PY_operation_no"
                },
                inplace=True
            )

            fees.rename(
                columns={
                    "tx_amount": "COMISION",
                    "tx_reference": "SF_operation_no"
                },
                inplace=True
            )

            detalle = pagos.merge(
                fees[["psp_tin", "COMISION", "SF_operation_no"]],
                on="psp_tin",
                how="left"
            )

            def col(name):
                return detalle[name] if name in detalle.columns else pd.Series("", index=detalle.index)

            reporte = pd.DataFrame({
                "FECHA": col("x_create_date_gmt_peru"),
                "COMERCIO": col("com_nombre"),
                "MONEDA": col("tx_currency_code"),
                "CLIENTE": col("deb_nombre"),
                "psp_tin": detalle["psp_tin"],
                "tipo": col("tipo"),
                "PY_operation_no": detalle["PY_operation_no"],
                "SF_operation_no": detalle["SF_operation_no"],
                "RECAUDO": detalle["RECAUDO"],
                "COMISION": pd.to_numeric(detalle["COMISION"], errors="coerce").abs(),
                "SET_referencia": col("set_referencia"),
                "Fecha Transferencia": col("fecha transferencia"),
            }).fillna(0)

            st.dataframe(reporte.head(500), use_container_width=True)

            st.download_button(
                "📥 Descargar reporte detallado (mes)",
                exportar_csv(reporte),
                "reporte_detallado_mes.csv"
            )

            st.divider()
            st.subheader("🏪 Total de comisiones por comercio")

            resumen_comercios = (
                reporte.groupby("COMERCIO", as_index=False)["COMISION"]
                .sum()
                .sort_values("COMISION", ascending=False)
            )

            resumen_comercios["COMISION"] = resumen_comercios["COMISION"].round(2)

            st.dataframe(resumen_comercios.head(500), use_container_width=True)

            st.download_button(
                "📥 Descargar resumen comercios",
                exportar_csv(resumen_comercios),
                "resumen_comercios.csv"
            )

# ================= TODOS LOS MESES =================
if archivos:

    st.subheader("📦 Reporte detallado (todos los meses)")

    df_full = df_original.copy()

    mask_py_f = df_full["tx_reference"].str.startswith("PY", na=False)
    mask_sf_f = df_full["tx_reference"].str.startswith("SF", na=False)

    pagos_full = df_full.loc[mask_py_f].copy()
    fees_full = df_full.loc[mask_sf_f].copy()

    pagos_full.rename(
        columns={
            "tx_amount": "RECAUDO",
            "tx_reference": "PY_operation_no"
        },
        inplace=True
    )

    fees_full.rename(
        columns={
            "tx_amount": "COMISION",
            "tx_reference": "SF_operation_no"
        },
        inplace=True
    )

    detalle_full = pagos_full.merge(
        fees_full[["psp_tin", "COMISION", "SF_operation_no"]],
        on="psp_tin",
        how="left"
    )

    def col_f(name):
        return detalle_full[name] if name in detalle_full.columns else pd.Series("", index=detalle_full.index)

    reporte_full = pd.DataFrame({
        "FECHA": col_f("x_create_date_gmt_peru"),
        "COMERCIO": col_f("com_nombre"),
        "MONEDA": col_f("tx_currency_code"),
        "CLIENTE": col_f("deb_nombre"),
        "psp_tin": detalle_full["psp_tin"],
        "tipo": col_f("tipo"),
        "PY_operation_no": detalle_full["PY_operation_no"],
        "SF_operation_no": detalle_full["SF_operation_no"],
        "RECAUDO": detalle_full["RECAUDO"],
        "COMISION": pd.to_numeric(detalle_full["COMISION"], errors="coerce").abs(),
        "SET_referencia": col_f("set_referencia"),
        "Fecha Transferencia": col_f("fecha transferencia"),
    }).fillna(0)

    st.download_button(
        "📥 Descargar reporte detallado (todos)",
        exportar_csv(reporte_full),
        "reporte_detallado_todos.csv"
    )
