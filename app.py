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

st.markdown(
    """
    <style>
    /* ── Layout ── */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* ── Métricas ── */
    [data-testid="metric-container"] {
        background-color: #111827;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #374151;
        transition: border-color 0.2s ease;
    }
    [data-testid="metric-container"]:hover {
        border-color: #6B7280;
    }
    [data-testid="metric-container"] label { color: #9CA3AF; }
    [data-testid="metric-container"] div   { color: white; }

    /* ── Upload zone ── */
    [data-testid="stFileUploader"] {
        border: 2px dashed #374151;
        border-radius: 12px;
        padding: 1rem;
        background-color: #0f172a;
    }

    /* ── Botones de descarga ── */
    [data-testid="stDownloadButton"] button {
        width: 100%;
        border-radius: 8px;
        border: 1px solid #374151;
        background-color: #1f2937;
        color: white;
        font-weight: 600;
        transition: background-color 0.2s ease;
    }
    [data-testid="stDownloadButton"] button:hover {
        background-color: #374151;
        border-color: #6B7280;
    }

    /* ── Tablas ── */
    [data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
    }

    /* ── Alertas ── */
    [data-testid="stAlert"] {
        border-radius: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────
col_titulo, col_info = st.columns([5, 1])
col_titulo.title("💳 Analizador Financiero Payin")
col_info.markdown("<br>", unsafe_allow_html=True)
col_info.caption("v1.0 · Payin Analytics")


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def exportar_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def altura_tabla(df: pd.DataFrame, max_height: int = 500) -> int:
    return min(35 * (len(df) + 1), max_height)


def leer_csv_seguro(f) -> pd.DataFrame:
    for sep in [",", ";"]:
        try:
            f.seek(0)
            df = pl.read_csv(f, separator=sep, ignore_errors=True)
            return df.to_pandas()
        except Exception:
            continue
    raise ValueError("No se pudo leer el CSV")


@st.cache_data(show_spinner=False, max_entries=5, ttl=3600)
def cargar_archivo(file) -> pd.DataFrame:
    nombre = file.name.lower()

    # ── CSV ──────────────────────────────────────────────────────────────────
    if nombre.endswith(".csv"):
        return leer_csv_seguro(file)

    # ── ZIP ──────────────────────────────────────────────────────────────────
    if nombre.endswith(".zip"):
        dfs_zip = []
        with zipfile.ZipFile(file) as z:
            for nombre_archivo in z.namelist():
                with z.open(nombre_archivo) as f:
                    contenido = io.BytesIO(f.read())
                    if nombre_archivo.lower().endswith(".csv"):
                        df_zip = leer_csv_seguro(contenido)
                    elif nombre_archivo.lower().endswith((".xlsx", ".xls")):
                        df_zip = pd.read_excel(contenido, engine="calamine")
                    else:
                        continue
                    df_zip.columns = df_zip.columns.str.lower().str.strip()
                    dfs_zip.append(df_zip)
        if dfs_zip:
            return pd.concat(dfs_zip, ignore_index=True)
        raise ValueError("ZIP sin CSV ni Excel")

    # ── EXCEL ─────────────────────────────────────────────────────────────────
    return pd.read_excel(file, engine="calamine")


def mostrar_info_archivo(archivos: list) -> None:
    """Muestra métricas básicas de los archivos subidos."""
    total_size = sum(getattr(f, "size", 0) for f in archivos)
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("📁 Archivos cargados", len(archivos))
    col_b.metric("⚖️ Tamaño total",
                 f"{total_size / 1_048_576:.1f} MB" if total_size > 1_048_576
                 else f"{total_size / 1024:.1f} KB")
    col_c.metric("📋 Formatos",
                 ", ".join({f.name.split(".")[-1].upper() for f in archivos}))


def validar_columnas_requeridas(df: pd.DataFrame) -> bool:
    """Valida que el DataFrame tenga las columnas mínimas necesarias."""
    requeridas = {"tx_currency_code", "tx_reference", "psp_tin",
                  "tx_amount", "x_create_date_gmt_peru"}
    faltantes = requeridas - set(df.columns)
    if faltantes:
        st.error(
            f"⚠️ Columnas faltantes en el archivo: `{'`, `'.join(sorted(faltantes))}`\n\n"
            "Verifica que el archivo tenga el formato correcto."
        )
        return False
    return True


def construir_reporte(detalle: pd.DataFrame) -> pd.DataFrame:
    """Construye el DataFrame de reporte detallado (reutilizable)."""
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
# SUBIR ARCHIVOS
# ─────────────────────────────────────────────────────────────────────────────
st.divider()

archivos = st.file_uploader(
    "📂 Sube tu archivo Excel, CSV o ZIP (máx. 2 GB)",
    type=["xlsx", "csv", "zip"],
    accept_multiple_files=True,
    help="Puedes subir múltiples archivos. Se unirán automáticamente.",
)

# ─────────────────────────────────────────────────────────────────────────────
# PROCESAMIENTO PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────
if archivos:

    mostrar_info_archivo(archivos)
    st.divider()

    # ── Carga ─────────────────────────────────────────────────────────────────
    with st.spinner("⏳ Procesando archivos, por favor espera..."):
        dfs = []
        errores = []

        for archivo in archivos:
            try:
                df_temp = cargar_archivo(archivo)
                df_temp.columns = df_temp.columns.str.lower().str.strip()
                dfs.append(df_temp)
            except Exception as e:
                errores.append(f"**{archivo.name}**: {e}")

        if errores:
            st.warning("⚠️ Algunos archivos no pudieron cargarse:\n" + "\n".join(errores))

        if not dfs:
            st.error("❌ No se pudo cargar ningún archivo. Verifica el formato.")
            st.stop()

        df = pd.concat(dfs, ignore_index=True)
        df_original = df.copy()
        del dfs
        gc.collect()

    col_ok1, col_ok2 = st.columns([3, 1])
    col_ok1.success(f"✅ Archivo cargado correctamente — **{len(df):,} filas** procesadas")
    col_ok2.caption(f"Columnas detectadas: {len(df.columns)}")

    # ── Validación ────────────────────────────────────────────────────────────
    if not validar_columnas_requeridas(df):
        st.stop()

    # ── Normalizar columnas clave ──────────────────────────────────────────────
    df["tx_currency_code"] = (
        df["tx_currency_code"]
        .astype(str)
        .str.upper()
        .replace({
            "BOLÍGRAFO":            "PEN",
            "DÓLAR ESTADOUNIDENSE": "USD",
            "DOLAR ESTADOUNIDENSE": "USD",
        })
    )
    df["tx_reference"] = df["tx_reference"].astype(str).str.upper()

    # ─────────────────────────────────────────────────────────────────────────
    # OPCIÓN DE REPORTE
    # ─────────────────────────────────────────────────────────────────────────
    st.divider()

    opcion_reporte = st.radio(
        "¿Qué deseas visualizar?",
        ["Comparación de comisiones", "Reporte detallado", "Ambas"],
        horizontal=True,
        index=None,
        help="Elige el tipo de análisis que quieres generar.",
    )

    if opcion_reporte:

        # ── Filtros ───────────────────────────────────────────────────────────
        st.divider()

        df["fecha"] = pd.to_datetime(df["x_create_date_gmt_peru"], errors="coerce")
        df["mes"]   = df["fecha"].dt.strftime("%Y-%m")

        meses_disponibles = sorted(df["mes"].dropna().unique())

        if not meses_disponibles:
            st.error("❌ No se encontraron fechas válidas en la columna `x_create_date_gmt_peru`.")
            st.stop()

        col1, col2, col3 = st.columns([2, 2, 3])
        mes_sel    = col1.selectbox("📅 Mes",    meses_disponibles)
        moneda_sel = col2.selectbox("💱 Moneda", ["PEN", "USD"])
        simbolo    = "S/" if moneda_sel == "PEN" else "$"

        df_filtrado = df[
            (df["mes"] == mes_sel) &
            (df["tx_currency_code"] == moneda_sel)
        ]

        col3.metric(
            "📊 Registros en este filtro",
            f"{len(df_filtrado):,}",
            help="Total de filas luego de aplicar mes y moneda",
        )

        if df_filtrado.empty:
            st.warning("⚠️ No hay datos para el mes y moneda seleccionados.")
            st.stop()

        # ── Reasignar df al filtrado para el resto ─────────────────────────
        df = df_filtrado.copy()

        # ─────────────────────────────────────────────────────────────────────
        # COMPARACIÓN DE COMISIONES
        # ─────────────────────────────────────────────────────────────────────
        if opcion_reporte in ["Comparación de comisiones", "Ambas"]:

            st.divider()
            st.subheader(f"📊 Comparación de comisiones — {moneda_sel} · {mes_sel}")

            col_p, col_f, _ = st.columns([2, 2, 3])
            porcentaje = col_p.number_input(
                "Porcentaje comisión (%)",
                value=2.30,
                min_value=0.0,
                max_value=100.0,
                step=0.01,
                help="Porcentaje aplicado sobre el monto del pago",
            )
            fee_fijo = col_f.number_input(
                f"Fee fijo ({simbolo})",
                value=0.90,
                min_value=0.0,
                step=0.01,
                help="Monto fijo que se suma a la comisión porcentual",
            )

            pagos = df[df["tx_reference"].str.startswith("PY", na=False)].copy()
            fees  = df[df["tx_reference"].str.startswith("SF", na=False)].copy()

            if pagos.empty:
                st.warning("⚠️ No se encontraron pagos (referencia PY) en este período.")
            else:
                comisiones = pagos.merge(
                    fees[["psp_tin", "tx_amount"]],
                    on="psp_tin",
                    how="left",
                    suffixes=("_pago", "_comision"),
                )

                comisiones["tx_amount_pago"]     = pd.to_numeric(comisiones["tx_amount_pago"],     errors="coerce")
                comisiones["tx_amount_comision"] = pd.to_numeric(comisiones["tx_amount_comision"], errors="coerce")

                comisiones["comision_real"]  = comisiones["tx_amount_comision"].abs()
                comisiones["comision_base"]  = comisiones["tx_amount_pago"] * (porcentaje / 100) + fee_fijo
                comisiones["igv"]            = (comisiones["comision_base"] * 0.18).round(2)
                comisiones["comision_final"] = (comisiones["comision_base"] + comisiones["igv"]).round(2)
                comisiones["diferencia"]     = (comisiones["comision_real"] - comisiones["comision_final"]).round(2)
                comisiones["total_neto"]     = (comisiones["tx_amount_pago"] - comisiones["comision_real"]).round(2)

                tabla = comisiones[[
                    "psp_tin", "tx_amount_pago", "comision_real",
                    "comision_base", "igv", "comision_final",
                    "diferencia", "total_neto",
                ]].fillna(0)

                # Aviso si la tabla es muy grande
                if len(tabla) > 500:
                    st.info(
                        f"ℹ️ Se muestran las primeras 500 filas de {len(tabla):,} totales. "
                        "Descarga el CSV para ver todas."
                    )

                tabla_preview = tabla.head(500)
                st.dataframe(
                    tabla_preview,
                    use_container_width=True,
                    hide_index=True,
                    height=altura_tabla(tabla_preview),
                )

                st.download_button(
                    "📥 Descargar comparación de comisiones",
                    exportar_csv(tabla),
                    "comisiones.csv",
                    mime="text/csv",
                )

                # ── Dashboard comparación ──────────────────────────────────
                st.subheader("📊 Dashboard comparación de comisiones")

                total_recaudo    = tabla["tx_amount_pago"].sum()
                total_base       = tabla["comision_base"].sum()
                total_igv        = round(total_base * 0.18, 2)
                total_final      = round(total_base + total_igv, 2)
                total_comisiones = round(tabla["comision_real"].sum(), 2)
                total_neto       = round(tabla["total_neto"].sum(), 2)
                total_diferencia = round(total_comisiones - total_final, 2)
                operaciones      = tabla["psp_tin"].nunique()

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("💰 Recaudado",   f"{simbolo} {total_recaudo:,.2f}")
                c2.metric("💸 Comisiones",  f"{simbolo} {total_comisiones:,.2f}")
                c3.metric("🧾 Base",        f"{simbolo} {total_base:,.2f}")
                c4.metric("🏛 IGV (18%)",   f"{simbolo} {total_igv:,.2f}")

                c5, c6, c7, c8 = st.columns(4)
                c5.metric("📑 Total final",  f"{simbolo} {total_final:,.2f}")
                c6.metric(
                    "⚖️ Diferencia",
                    f"{simbolo} {total_diferencia:,.2f}",
                    delta=f"{total_diferencia:,.2f}",
                    delta_color="inverse",
                )
                c7.metric("🔢 Operaciones", f"{operaciones:,}")
                c8.metric("🧮 Neto",        f"{simbolo} {total_neto:,.2f}")

        # ─────────────────────────────────────────────────────────────────────
        # REPORTE DETALLADO (MES)
        # ─────────────────────────────────────────────────────────────────────
        if opcion_reporte in ["Reporte detallado", "Ambas"]:

            st.divider()
            st.subheader(f"📄 Reporte detallado — {moneda_sel} · {mes_sel}")

            pagos = df[df["tx_reference"].str.startswith("PY", na=False)].copy()
            fees  = df[df["tx_reference"].str.startswith("SF", na=False)].copy()

            pagos.rename(columns={"tx_amount": "RECAUDO",  "tx_reference": "PY_operation_no"}, inplace=True)
            fees.rename( columns={"tx_amount": "COMISION", "tx_reference": "SF_operation_no"}, inplace=True)

            detalle = pagos.merge(
                fees[["psp_tin", "COMISION", "SF_operation_no"]],
                on="psp_tin",
                how="left",
            )

            reporte = construir_reporte(detalle)

            if len(reporte) > 500:
                st.info(
                    f"ℹ️ Se muestran las primeras 500 filas de {len(reporte):,} totales. "
                    "Descarga el CSV para ver todas."
                )

            reporte_preview = reporte.head(500)
            st.dataframe(
                reporte_preview,
                use_container_width=True,
                hide_index=True,
                height=altura_tabla(reporte_preview),
            )

            st.download_button(
                "📥 Descargar reporte detallado (mes)",
                exportar_csv(reporte),
                "reporte_detallado_mes.csv",
                mime="text/csv",
            )

            # ── Dashboard reporte detallado ────────────────────────────────
            st.divider()
            st.subheader("📊 Dashboard reporte detallado")

            total_recaudo_det        = round(reporte["RECAUDO"].sum(), 2)
            total_comision_det       = round(reporte["COMISION"].sum(), 2)
            cantidad_operaciones_det = reporte["psp_tin"].nunique()
            ticket_promedio          = (
                round(total_recaudo_det / cantidad_operaciones_det, 2)
                if cantidad_operaciones_det > 0 else 0
            )
            neto_det = round(total_recaudo_det - total_comision_det, 2)

            d1, d2, d3, d4 = st.columns(4)
            d1.metric("💰 Recaudo total",   f"{simbolo} {total_recaudo_det:,.2f}")
            d2.metric("💸 Comisión total",  f"{simbolo} {total_comision_det:,.2f}")
            d3.metric("🔢 Operaciones",     f"{cantidad_operaciones_det:,}")
            d4.metric("🧾 Ticket promedio", f"{simbolo} {ticket_promedio:,.2f}")

            d5 = st.columns(1)[0]
            d5.metric("🧮 Neto", f"{simbolo} {neto_det:,.2f}")

            # ── Comisiones por comercio ────────────────────────────────────
            st.divider()
            st.subheader("🏪 Total de comisiones por comercio")

            resumen_comercios = (
                reporte
                .groupby("COMERCIO", as_index=False)["COMISION"]
                .sum()
                .sort_values("COMISION", ascending=False)
            )
            resumen_comercios["COMISION"] = resumen_comercios["COMISION"].round(2)

            resumen_preview = resumen_comercios.head(500)
            st.dataframe(
                resumen_preview,
                use_container_width=True,
                hide_index=True,
                height=altura_tabla(resumen_preview),
            )

            st.download_button(
                "📥 Descargar total comisiones por comercio",
                exportar_csv(resumen_comercios),
                "total_comisiones_comercio.csv",
                mime="text/csv",
            )

    # ─────────────────────────────────────────────────────────────────────────
    # REPORTE DETALLADO (TODOS LOS MESES)
    # ─────────────────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("📦 Reporte detallado (todos los meses)")

    df_full = df_original.copy()

    pagos_full = df_full[df_full["tx_reference"].str.startswith("PY", na=False)].copy()
    fees_full  = df_full[df_full["tx_reference"].str.startswith("SF", na=False)].copy()

    pagos_full.rename(columns={"tx_amount": "RECAUDO",  "tx_reference": "PY_operation_no"}, inplace=True)
    fees_full.rename( columns={"tx_amount": "COMISION", "tx_reference": "SF_operation_no"}, inplace=True)

    detalle_full = pagos_full.merge(
        fees_full[["psp_tin", "COMISION", "SF_operation_no"]],
        on="psp_tin",
        how="left",
    )

    reporte_full = construir_reporte(detalle_full)

    col_full1, col_full2 = st.columns([3, 1])
    col_full1.caption(f"📋 Total de registros en todos los meses: **{len(reporte_full):,}**")

    col_full2.download_button(
        "📥 Descargar todos los meses",
        exportar_csv(reporte_full),
        "reporte_detallado_todos.csv",
        mime="text/csv",
    )
