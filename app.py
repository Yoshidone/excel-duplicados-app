import streamlit as st
import polars as pl
import pandas as pd
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
st.caption("v2.0 · Payin Analytics — optimizado para archivos grandes")

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS — todo en Polars para mínimo uso de RAM
# ─────────────────────────────────────────────────────────────────────────────

def exportar_csv(df_pd: pd.DataFrame) -> bytes:
    return df_pd.to_csv(index=False).encode("utf-8")

def altura_tabla(n_filas: int, max_height: int = 500) -> int:
    return min(35 * (n_filas + 1), max_height)

def leer_csv_seguro(f) -> pl.DataFrame:
    """Lee CSV en Polars (más rápido y consume menos RAM que pandas)."""
    for sep in [",", ";"]:
        try:
            f.seek(0)
            return pl.read_csv(f, separator=sep, ignore_errors=True, infer_schema_length=1000)
        except Exception:
            continue
    raise ValueError("No se pudo leer el CSV")

def normalizar_columnas(df: pl.DataFrame) -> pl.DataFrame:
    return df.rename({c: c.strip().lower() for c in df.columns})

@st.cache_data(show_spinner=False, max_entries=2, ttl=1800)
def cargar_y_procesar(file_bytes: bytes, file_name: str) -> bytes:
    """
    Carga el archivo, normaliza columnas y devuelve bytes CSV comprimido.
    Se guarda como CSV en caché para no mantener DataFrames en memoria.
    """
    nombre = file_name.lower()
    dfs = []

    if nombre.endswith(".csv"):
        df = leer_csv_seguro(io.BytesIO(file_bytes))
        dfs.append(normalizar_columnas(df))

    elif nombre.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            for n in z.namelist():
                with z.open(n) as f:
                    contenido = f.read()
                    if n.lower().endswith(".csv"):
                        df = leer_csv_seguro(io.BytesIO(contenido))
                    elif n.lower().endswith((".xlsx", ".xls")):
                        df_pd = pd.read_excel(io.BytesIO(contenido), engine="calamine")
                        df    = pl.from_pandas(df_pd)
                        del df_pd
                    else:
                        continue
                    dfs.append(normalizar_columnas(df))
                    del df

    else:  # Excel
        df_pd = pd.read_excel(io.BytesIO(file_bytes), engine="calamine")
        dfs.append(normalizar_columnas(pl.from_pandas(df_pd)))
        del df_pd

    if not dfs:
        raise ValueError("Sin datos válidos")

    resultado = pl.concat(dfs, how="diagonal")
    del dfs; gc.collect()

    # Devolver como CSV bytes — ocupa mucho menos RAM en caché que un DataFrame
    return resultado.write_csv().encode("utf-8")


def cargar_df(archivos) -> pl.DataFrame:
    """Carga todos los archivos y los une en un solo DataFrame Polars."""
    dfs, errores = [], []
    for archivo in archivos:
        try:
            csv_bytes = cargar_y_procesar(archivo.read(), archivo.name)
            df        = pl.read_csv(io.BytesIO(csv_bytes), ignore_errors=True, infer_schema_length=500)
            dfs.append(df)
        except Exception as e:
            errores.append(f"{archivo.name}: {e}")

    if errores:
        st.warning("Errores al cargar:\n" + "\n".join(errores))
    if not dfs:
        st.error("❌ No se pudo cargar ningún archivo.")
        st.stop()

    resultado = pl.concat(dfs, how="diagonal")
    del dfs; gc.collect()
    return resultado


def normalizar_base(df: pl.DataFrame) -> pl.DataFrame:
    """Limpia monedas, referencias y genera columna mes."""

    # Corregir nombres de moneda
    df = df.with_columns(
        pl.col("tx_currency_code")
        .cast(pl.Utf8)
        .str.to_uppercase()
        .str.replace("BOLÍGRAFO",            "PEN")
        .str.replace("DÓLAR ESTADOUNIDENSE", "USD")
        .str.replace("DOLAR ESTADOUNIDENSE", "USD")
        .alias("tx_currency_code")
    )

    df = df.with_columns(
        pl.col("tx_reference").cast(pl.Utf8).str.to_uppercase().alias("tx_reference")
    )

    # Parsear fecha y extraer mes
    df = df.with_columns(
        pl.col("x_create_date_gmt_peru")
        .str.to_datetime(strict=False)
        .alias("fecha")
    )

    df = df.with_columns(
        pl.col("fecha").dt.strftime("%Y-%m").alias("mes")
    )

    return df


def construir_reporte_pl(pagos: pl.DataFrame, fees: pl.DataFrame) -> pl.DataFrame:
    """Merge pagos + fees en Polars y devuelve el reporte estructurado."""

    pagos = pagos.rename({"tx_amount": "RECAUDO", "tx_reference": "PY_operation_no"})
    fees  = fees.rename( {"tx_amount": "COMISION","tx_reference": "SF_operation_no"})

    fees_sel = fees.select(["psp_tin", "COMISION", "SF_operation_no"])

    detalle = pagos.join(fees_sel, on="psp_tin", how="left")

    # Columnas opcionales — si no existen se crean vacías
    def get_col(df, col):
        return pl.col(col) if col in df.columns else pl.lit("").alias(col)

    return detalle.select([
        get_col(detalle, "x_create_date_gmt_peru").alias("FECHA"),
        get_col(detalle, "com_nombre").alias("COMERCIO"),
        get_col(detalle, "tx_currency_code").alias("MONEDA"),
        get_col(detalle, "deb_nombre").alias("CLIENTE"),
        pl.col("psp_tin"),
        get_col(detalle, "tipo").alias("tipo"),
        pl.col("PY_operation_no"),
        pl.col("SF_operation_no"),
        pl.col("RECAUDO").cast(pl.Float64).fill_null(0),
        pl.col("COMISION").cast(pl.Float64).abs().fill_null(0),
        get_col(detalle, "set_referencia").alias("SET_referencia"),
        get_col(detalle, "fecha transferencia").alias("Fecha_Transferencia"),
    ])


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
# PASO 2 — CARGAR
# ─────────────────────────────────────────────────────────────────────────────
with st.spinner("⏳ Cargando archivos..."):
    df_base = cargar_df(archivos)

requeridas = {"tx_currency_code", "tx_reference", "psp_tin", "tx_amount", "x_create_date_gmt_peru"}
faltantes  = requeridas - set(df_base.columns)
if faltantes:
    st.error(f"⚠️ Columnas faltantes: {', '.join(sorted(faltantes))}")
    st.stop()

with st.spinner("⚙️ Normalizando datos..."):
    df_base = normalizar_base(df_base)
    # Mantener solo columnas necesarias → menos RAM
    cols_utiles = [c for c in [
        "tx_currency_code","tx_reference","psp_tin","tx_amount",
        "x_create_date_gmt_peru","fecha","mes",
        "com_nombre","deb_nombre","tipo","set_referencia",
        "fecha transferencia",
    ] if c in df_base.columns]
    df_base = df_base.select(cols_utiles)
    gc.collect()

st.success(f"✅ {len(df_base):,} filas · {len(df_base.columns)} columnas")

# ─────────────────────────────────────────────────────────────────────────────
# PASO 3 — FILTROS
# ─────────────────────────────────────────────────────────────────────────────
st.divider()

meses = sorted(df_base["mes"].drop_nulls().unique().to_list())
if not meses:
    st.error("❌ No hay fechas válidas en el archivo.")
    st.stop()

col1, col2, col3 = st.columns(3)
mes_sel    = col1.selectbox("📅 Mes",    meses,          key="sel_mes")
moneda_sel = col2.selectbox("💱 Moneda", ["PEN", "USD"], key="sel_moneda")
opcion     = col3.selectbox("📋 Reporte",
    ["Comparación de comisiones", "Reporte detallado", "Ambas"], key="sel_reporte")
simbolo = "S/" if moneda_sel == "PEN" else "$"

# Filtrar en Polars (rápido, sin copiar a pandas)
df_mes = df_base.filter(
    (pl.col("mes") == mes_sel) &
    (pl.col("tx_currency_code") == moneda_sel)
)

st.caption(f"Registros filtrados: **{len(df_mes):,}**")

if len(df_mes) == 0:
    st.warning("⚠️ No hay datos para ese mes y moneda.")
    st.stop()

# Separar pagos y fees una sola vez (se reutilizan abajo)
pagos_df = df_mes.filter(pl.col("tx_reference").str.starts_with("PY"))
fees_df  = df_mes.filter(pl.col("tx_reference").str.starts_with("SF"))

# ─────────────────────────────────────────────────────────────────────────────
# PASO 4A — COMPARACIÓN DE COMISIONES
# ─────────────────────────────────────────────────────────────────────────────
if opcion in ["Comparación de comisiones", "Ambas"]:

    st.divider()
    st.subheader(f"📊 Comparación de comisiones — {moneda_sel} · {mes_sel}")

    col_p, col_f = st.columns(2)
    porcentaje = col_p.number_input("Porcentaje comisión (%)", value=2.30, min_value=0.0, step=0.01, key="pct")
    fee_fijo   = col_f.number_input(f"Fee fijo ({simbolo})",  value=0.90, min_value=0.0, step=0.01, key="fee")

    if len(pagos_df) == 0:
        st.warning("⚠️ No hay pagos PY en este período.")
    else:
        # Merge en Polars
        fees_sel = fees_df.select(["psp_tin", "tx_amount"]).rename({"tx_amount": "tx_amount_comision"})
        com = pagos_df.rename({"tx_amount": "tx_amount_pago"}).join(fees_sel, on="psp_tin", how="left")

        com = com.with_columns([
            pl.col("tx_amount_pago").cast(pl.Float64).fill_null(0),
            pl.col("tx_amount_comision").cast(pl.Float64).fill_null(0),
        ])
        com = com.with_columns([
            pl.col("tx_amount_comision").abs().alias("comision_real"),
            (pl.col("tx_amount_pago") * (porcentaje / 100) + fee_fijo).round(2).alias("comision_base"),
        ])
        com = com.with_columns([
            (pl.col("comision_base") * 0.18).round(2).alias("igv"),
        ])
        com = com.with_columns([
            (pl.col("comision_base") + pl.col("igv")).round(2).alias("comision_final"),
            (pl.col("comision_real") - (pl.col("comision_base") + (pl.col("comision_base") * 0.18))).round(2).alias("diferencia"),
            (pl.col("tx_amount_pago") - pl.col("tx_amount_comision").abs()).round(2).alias("total_neto"),
        ])

        tabla_pl = com.select(["psp_tin","tx_amount_pago","comision_real",
                               "comision_base","igv","comision_final","diferencia","total_neto"])

        # Convertir a pandas SOLO para mostrar (500 filas máximo)
        tabla_preview = tabla_pl.head(500).to_pandas()

        if len(tabla_pl) > 500:
            st.info(f"ℹ️ Mostrando 500 de {len(tabla_pl):,} filas.")
        st.dataframe(tabla_preview, use_container_width=True, hide_index=True, height=altura_tabla(len(tabla_preview)))

        # Descargar: convertir completo a pandas solo cuando el usuario hace clic
        csv_com = tabla_pl.write_csv().encode("utf-8")
        st.download_button("📥 Descargar comparación CSV", csv_com, "comisiones.csv", mime="text/csv", key="dl_com")
        del tabla_preview; gc.collect()

        # Dashboard — calcular desde Polars directamente
        tr  = round(tabla_pl["tx_amount_pago"].sum(),  2)
        tb  = round(tabla_pl["comision_base"].sum(),   2)
        tig = round(tb * 0.18,                         2)
        tf  = round(tb + tig,                          2)
        tc  = round(tabla_pl["comision_real"].sum(),   2)
        tn  = round(tabla_pl["total_neto"].sum(),      2)
        td  = round(tc - tf,                           2)
        ops = tabla_pl["psp_tin"].n_unique()
        del tabla_pl; gc.collect()

        st.subheader("📊 Dashboard comparación")
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

    if len(pagos_df) == 0:
        st.warning("⚠️ No hay pagos PY en este período.")
    else:
        reporte_pl = construir_reporte_pl(pagos_df.clone(), fees_df.clone())

        reporte_preview = reporte_pl.head(500).to_pandas()
        if len(reporte_pl) > 500:
            st.info(f"ℹ️ Mostrando 500 de {len(reporte_pl):,} filas.")
        st.dataframe(reporte_preview, use_container_width=True, hide_index=True, height=altura_tabla(len(reporte_preview)))

        csv_rep = reporte_pl.write_csv().encode("utf-8")
        st.download_button("📥 Descargar reporte mes CSV", csv_rep, "reporte_mes.csv", mime="text/csv", key="dl_rep_mes")
        del reporte_preview; gc.collect()

        # Dashboard detallado
        st.divider()
        st.subheader("📊 Dashboard reporte detallado")

        dtr  = round(reporte_pl["RECAUDO"].sum(),  2)
        dtc  = round(reporte_pl["COMISION"].sum(), 2)
        dops = reporte_pl["psp_tin"].n_unique()
        dnet = round(dtr - dtc, 2)
        dtkt = round(dtr / dops, 2) if dops > 0 else 0

        da1, da2, da3, da4 = st.columns(4)
        da1.metric("💰 Recaudo total",   f"{simbolo} {dtr:,.2f}")
        da2.metric("💸 Comisión total",  f"{simbolo} {dtc:,.2f}")
        da3.metric("🔢 Operaciones",     f"{dops:,}")
        da4.metric("🧾 Ticket promedio", f"{simbolo} {dtkt:,.2f}")

        da5, da6, da7, da8 = st.columns(4)
        da5.metric("🧮 Neto", f"{simbolo} {dnet:,.2f}")
        da6.metric("", ""); da7.metric("", ""); da8.metric("", "")

        # Comisiones por comercio
        st.divider()
        st.subheader("🏪 Comisiones por comercio")
        res_com = (
            reporte_pl
            .group_by("COMERCIO")
            .agg(pl.col("COMISION").sum().round(2))
            .sort("COMISION", descending=True)
        )
        st.dataframe(res_com.head(500).to_pandas(), use_container_width=True, hide_index=True, height=altura_tabla(min(len(res_com), 500)))

        csv_res = res_com.write_csv().encode("utf-8")
        st.download_button("📥 Descargar comisiones por comercio", csv_res, "comercios.csv", mime="text/csv", key="dl_comercio")
        del reporte_pl, res_com; gc.collect()

# ─────────────────────────────────────────────────────────────────────────────
# PASO 5 — REPORTE TODOS LOS MESES
# ─────────────────────────────────────────────────────────────────────────────
st.divider()
st.subheader("📦 Reporte detallado (todos los meses)")

pf = df_base.filter(pl.col("tx_reference").str.starts_with("PY"))
ff = df_base.filter(pl.col("tx_reference").str.starts_with("SF"))
reporte_full = construir_reporte_pl(pf, ff)

st.caption(f"📋 {len(reporte_full):,} registros en total")
csv_full = reporte_full.write_csv().encode("utf-8")
st.download_button("📥 Descargar todos los meses", csv_full, "reporte_todos.csv", mime="text/csv", key="dl_todos")
del reporte_full, pf, ff, csv_full; gc.collect()
