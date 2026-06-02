import streamlit as st
import pandas as pd
import polars as pl
import zipfile
import io
import gc

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Analizador Financiero Payin",
    page_icon="💳",
    layout="wide",
)

st.markdown("""
<style>
.block-container { padding-top: 2rem; padding-bottom: 2rem; }
[data-testid="metric-container"] {
    background-color: #111827;
    padding: 15px;
    border-radius: 12px;
    border: 1px solid #374151;
}
[data-testid="metric-container"] label { color: #9CA3AF; }
[data-testid="metric-container"] div   { color: white; }
[data-testid="stDownloadButton"] button {
    width: 100%;
    border-radius: 8px;
    border: 1px solid #374151;
    background-color: #1f2937;
    color: white;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

st.title("💳 Analizador Financiero Payin")
st.caption("v1.0 · Payin Analytics")

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def exportar_csv(df):
    return df.to_csv(index=False).encode("utf-8")

def altura_tabla(df, max_height=500):
    return min(35 * (len(df) + 1), max_height)

def leer_csv_seguro(f):
    for sep in [",", ";"]:
        try:
            f.seek(0)
            return pl.read_csv(f, separator=sep, ignore_errors=True).to_pandas()
        except Exception:
            continue
    raise ValueError("No se pudo leer el CSV")

@st.cache_data(show_spinner=False, max_entries=3, ttl=3600)
def cargar_archivo(file):
    nombre = file.name.lower()
    if nombre.endswith(".csv"):
        return leer_csv_seguro(file)
    if nombre.endswith(".zip"):
        dfs_zip = []
        with zipfile.ZipFile(file) as z:
            for n in z.namelist():
                with z.open(n) as f:
                    contenido = io.BytesIO(f.read())
                    if n.lower().endswith(".csv"):
                        df_zip = leer_csv_seguro(contenido)
                    elif n.lower().endswith((".xlsx", ".xls")):
                        df_zip = pd.read_excel(contenido, engine="calamine")
                    else:
                        continue
                    df_zip.columns = df_zip.columns.str.lower().str.strip()
                    dfs_zip.append(df_zip)
        if dfs_zip:
            return pd.concat(dfs_zip, ignore_index=True)
        raise ValueError("ZIP sin archivos válidos")
    return pd.read_excel(file, engine="calamine")

def construir_reporte(detalle):
    return pd.DataFrame({
        "FECHA":               detalle.get("x_create_date_gmt_peru", ""),
        "COMERCIO":            detalle.get("com_nombre",              ""),
        "MONEDA":              detalle.get("tx_currency_code",        ""),
        "CLIENTE":             detalle.get("deb_nombre",              ""),
        "psp_tin":             detalle["psp_tin"],
        "tipo":                detalle.get("tipo",                    ""),
        "PY_operation_no":     detalle["PY_operation_no"],
        "SF_operation_no":     detalle["SF_operation_no"],
        "RECAUDO":             detalle["RECAUDO"],
        "COMISION":            detalle["COMISION"].abs(),
        "SET_referencia":      detalle.get("set_referencia",          ""),
        "Fecha Transferencia": detalle.get("fecha transferencia",     ""),
    }).fillna(0)

# ─────────────────────────────────────────────────────────────────────────────
# PASO 1 — SUBIR ARCHIVOS
# ─────────────────────────────────────────────────────────────────────────────
st.divider()
archivos = st.file_uploader(
    "📂 Sube tu archivo Excel, CSV o ZIP",
    type=["xlsx", "csv", "zip"],
    accept_multiple_files=True,
)

if not archivos:
    st.info("👆 Sube un archivo para comenzar.")
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# PASO 2 — CARGAR Y VALIDAR
# ─────────────────────────────────────────────────────────────────────────────
with st.spinner("⏳ Procesando..."):
    dfs, errores = [], []
    for archivo in archivos:
        try:
            tmp = cargar_archivo(archivo)
            tmp.columns = tmp.columns.str.lower().str.strip()
            dfs.append(tmp)
        except Exception as e:
            errores.append(f"{archivo.name}: {e}")

    if errores:
        st.warning("Errores al cargar:\n" + "\n".join(errores))
    if not dfs:
        st.error("❌ No se pudo cargar ningún archivo.")
        st.stop()

    df_base = pd.concat(dfs, ignore_index=True)
    del dfs; gc.collect()

requeridas = {"tx_currency_code", "tx_reference", "psp_tin", "tx_amount", "x_create_date_gmt_peru"}
faltantes  = requeridas - set(df_base.columns)
if faltantes:
    st.error(f"⚠️ Columnas faltantes: {', '.join(sorted(faltantes))}")
    st.stop()

st.success(f"✅ {len(df_base):,} filas · {len(df_base.columns)} columnas")

df_base["tx_currency_code"] = (
    df_base["tx_currency_code"].astype(str).str.upper()
    .replace({"BOLÍGRAFO": "PEN", "DÓLAR ESTADOUNIDENSE": "USD", "DOLAR ESTADOUNIDENSE": "USD"})
)
df_base["tx_reference"] = df_base["tx_reference"].astype(str).str.upper()
df_base["fecha"]        = pd.to_datetime(df_base["x_create_date_gmt_peru"], errors="coerce")
df_base["mes"]          = df_base["fecha"].dt.strftime("%Y-%m")

# ─────────────────────────────────────────────────────────────────────────────
# PASO 3 — FILTROS (siempre visibles, sin condicionales anidados)
# ─────────────────────────────────────────────────────────────────────────────
st.divider()

meses = sorted(df_base["mes"].dropna().unique())
if not meses:
    st.error("❌ No hay fechas válidas en el archivo.")
    st.stop()

col1, col2, col3 = st.columns(3)
mes_sel      = col1.selectbox("📅 Mes",     meses,          key="sel_mes")
moneda_sel   = col2.selectbox("💱 Moneda",  ["PEN", "USD"], key="sel_moneda")
opcion       = col3.selectbox(
    "📋 Reporte",
    ["Comparación de comisiones", "Reporte detallado", "Ambas"],
    key="sel_reporte",
)
simbolo = "S/" if moneda_sel == "PEN" else "$"

df_mes = df_base[
    (df_base["mes"] == mes_sel) &
    (df_base["tx_currency_code"] == moneda_sel)
].copy()

st.caption(f"Registros filtrados: **{len(df_mes):,}**")

if df_mes.empty:
    st.warning("⚠️ No hay datos para ese mes y moneda.")
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# PASO 4A — COMPARACIÓN DE COMISIONES
# ─────────────────────────────────────────────────────────────────────────────
if opcion in ["Comparación de comisiones", "Ambas"]:

    st.divider()
    st.subheader(f"📊 Comparación de comisiones — {moneda_sel} · {mes_sel}")

    col_p, col_f = st.columns(2)
    porcentaje = col_p.number_input("Porcentaje comisión (%)", value=2.30, min_value=0.0, step=0.01, key="pct")
    fee_fijo   = col_f.number_input(f"Fee fijo ({simbolo})",  value=0.90, min_value=0.0, step=0.01, key="fee")

    pagos_c = df_mes[df_mes["tx_reference"].str.startswith("PY", na=False)].copy()
    fees_c  = df_mes[df_mes["tx_reference"].str.startswith("SF", na=False)].copy()

    if pagos_c.empty:
        st.warning("⚠️ No hay pagos PY en este período.")
    else:
        com = pagos_c.merge(fees_c[["psp_tin", "tx_amount"]], on="psp_tin", how="left", suffixes=("_pago", "_comision"))
        com["tx_amount_pago"]     = pd.to_numeric(com["tx_amount_pago"],     errors="coerce")
        com["tx_amount_comision"] = pd.to_numeric(com["tx_amount_comision"], errors="coerce")
        com["comision_real"]      = com["tx_amount_comision"].abs()
        com["comision_base"]      = (com["tx_amount_pago"] * (porcentaje / 100) + fee_fijo).round(2)
        com["igv"]                = (com["comision_base"] * 0.18).round(2)
        com["comision_final"]     = (com["comision_base"] + com["igv"]).round(2)
        com["diferencia"]         = (com["comision_real"] - com["comision_final"]).round(2)
        com["total_neto"]         = (com["tx_amount_pago"] - com["comision_real"]).round(2)

        tabla = com[["psp_tin","tx_amount_pago","comision_real","comision_base","igv","comision_final","diferencia","total_neto"]].fillna(0)

        if len(tabla) > 500:
            st.info(f"ℹ️ Mostrando 500 de {len(tabla):,} filas. Descarga el CSV para ver todas.")
        st.dataframe(tabla.head(500), use_container_width=True, hide_index=True, height=altura_tabla(tabla.head(500)))
        st.download_button("📥 Descargar comparación CSV", exportar_csv(tabla), "comisiones.csv", mime="text/csv", key="dl_com")

        # Dashboard
        st.subheader("📊 Dashboard comparación")
        tr  = round(tabla["tx_amount_pago"].sum(),  2)
        tb  = round(tabla["comision_base"].sum(),   2)
        tig = round(tb * 0.18,                      2)
        tf  = round(tb + tig,                       2)
        tc  = round(tabla["comision_real"].sum(),   2)
        tn  = round(tabla["total_neto"].sum(),      2)
        td  = round(tc - tf,                        2)
        ops = tabla["psp_tin"].nunique()

        r1c1, r1c2, r1c3, r1c4 = st.columns(4)
        r1c1.metric("💰 Recaudado",  f"{simbolo} {tr:,.2f}")
        r1c2.metric("💸 Comisiones", f"{simbolo} {tc:,.2f}")
        r1c3.metric("🧾 Base",       f"{simbolo} {tb:,.2f}")
        r1c4.metric("🏛 IGV",        f"{simbolo} {tig:,.2f}")

        r2c1, r2c2, r2c3, r2c4 = st.columns(4)
        r2c1.metric("📑 Total final", f"{simbolo} {tf:,.2f}")
        r2c2.metric("⚖️ Diferencia",  f"{simbolo} {td:,.2f}")
        r2c3.metric("🔢 Operaciones", f"{ops:,}")
        r2c4.metric("🧮 Neto",        f"{simbolo} {tn:,.2f}")

# ─────────────────────────────────────────────────────────────────────────────
# PASO 4B — REPORTE DETALLADO (MES)
# ─────────────────────────────────────────────────────────────────────────────
if opcion in ["Reporte detallado", "Ambas"]:

    st.divider()
    st.subheader(f"📄 Reporte detallado — {moneda_sel} · {mes_sel}")

    pagos_d = df_mes[df_mes["tx_reference"].str.startswith("PY", na=False)].copy()
    fees_d  = df_mes[df_mes["tx_reference"].str.startswith("SF", na=False)].copy()

    pagos_d.rename(columns={"tx_amount": "RECAUDO",  "tx_reference": "PY_operation_no"}, inplace=True)
    fees_d.rename( columns={"tx_amount": "COMISION", "tx_reference": "SF_operation_no"}, inplace=True)

    detalle = pagos_d.merge(fees_d[["psp_tin","COMISION","SF_operation_no"]], on="psp_tin", how="left")
    reporte = construir_reporte(detalle)

    if len(reporte) > 500:
        st.info(f"ℹ️ Mostrando 500 de {len(reporte):,} filas.")
    st.dataframe(reporte.head(500), use_container_width=True, hide_index=True, height=altura_tabla(reporte.head(500)))
    st.download_button("📥 Descargar reporte mes CSV", exportar_csv(reporte), "reporte_mes.csv", mime="text/csv", key="dl_rep_mes")

    # Dashboard detallado
    st.divider()
    st.subheader("📊 Dashboard reporte detallado")

    dtr  = round(reporte["RECAUDO"].sum(),  2)
    dtc  = round(reporte["COMISION"].sum(), 2)
    dops = reporte["psp_tin"].nunique()
    dnet = round(dtr - dtc, 2)
    dtkt = round(dtr / dops, 2) if dops > 0 else 0

    da1, da2, da3, da4 = st.columns(4)
    da1.metric("💰 Recaudo total",   f"{simbolo} {dtr:,.2f}")
    da2.metric("💸 Comisión total",  f"{simbolo} {dtc:,.2f}")
    da3.metric("🔢 Operaciones",     f"{dops:,}")
    da4.metric("🧾 Ticket promedio", f"{simbolo} {dtkt:,.2f}")

    da5, da6, da7, da8 = st.columns(4)
    da5.metric("🧮 Neto", f"{simbolo} {dnet:,.2f}")
    da6.metric("", "")
    da7.metric("", "")
    da8.metric("", "")

    # Comisiones por comercio
    st.divider()
    st.subheader("🏪 Comisiones por comercio")
    res_com = (
        reporte.groupby("COMERCIO", as_index=False)["COMISION"]
        .sum().sort_values("COMISION", ascending=False)
    )
    res_com["COMISION"] = res_com["COMISION"].round(2)
    st.dataframe(res_com.head(500), use_container_width=True, hide_index=True, height=altura_tabla(res_com.head(500)))
    st.download_button("📥 Descargar comisiones por comercio", exportar_csv(res_com), "comercios.csv", mime="text/csv", key="dl_com_comercio")

# ─────────────────────────────────────────────────────────────────────────────
# PASO 5 — REPORTE TODOS LOS MESES (siempre visible)
# ─────────────────────────────────────────────────────────────────────────────
st.divider()
st.subheader("📦 Reporte detallado (todos los meses)")

pf = df_base[df_base["tx_reference"].str.startswith("PY", na=False)].copy()
ff = df_base[df_base["tx_reference"].str.startswith("SF", na=False)].copy()
pf.rename(columns={"tx_amount": "RECAUDO",  "tx_reference": "PY_operation_no"}, inplace=True)
ff.rename( columns={"tx_amount": "COMISION", "tx_reference": "SF_operation_no"}, inplace=True)
det_full     = pf.merge(ff[["psp_tin","COMISION","SF_operation_no"]], on="psp_tin", how="left")
reporte_full = construir_reporte(det_full)

st.caption(f"📋 {len(reporte_full):,} registros en total")
st.download_button("📥 Descargar todos los meses", exportar_csv(reporte_full), "reporte_todos.csv", mime="text/csv", key="dl_todos")
