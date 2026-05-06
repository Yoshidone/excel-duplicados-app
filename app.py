# ================= IMPORTS =================
import streamlit as st
import pandas as pd
import polars as pl
import zipfile
import io
import time

# ================= CONFIG =================
st.set_page_config(
    page_title="Analizador Financiero Payin",
    layout="wide"
)

# ================= ESTILOS =================
st.markdown("""
<style>

.stApp {
    background-color: #0F172A;
    color: white;
}

.block-container {
    padding-top: 1rem;
}

div[data-testid="metric-container"] {
    background-color: #111827;
    border: 1px solid #374151;
    padding: 15px;
    border-radius: 12px;
}

section[data-testid="stSidebar"] {
    background-color: #111827;
}

</style>
""", unsafe_allow_html=True)

# ================= TITULO =================
st.title("📊 Analizador Financiero Payin")
st.caption("Carga archivos Excel, CSV o ZIP para comenzar el análisis")

# ================= CACHE =================
@st.cache_data(show_spinner=False)
def leer_csv_seguro(file):

    for sep in [",", ";"]:

        try:

            file.seek(0)

            df = pl.read_csv(
                file,
                separator=sep,
                ignore_errors=True
            )

            return df

        except:
            continue

    return None


@st.cache_data(show_spinner=True)
def cargar_archivo(uploaded_file):

    nombre = uploaded_file.name.lower()

    # ================= CSV =================
    if nombre.endswith(".csv"):

        return leer_csv_seguro(uploaded_file)

    # ================= ZIP =================
    elif nombre.endswith(".zip"):

        dfs = []

        with zipfile.ZipFile(uploaded_file) as z:

            for archivo in z.namelist():

                # CSV
                if archivo.lower().endswith(".csv"):

                    with z.open(archivo) as f:

                        df_temp = leer_csv_seguro(
                            io.BytesIO(f.read())
                        )

                        if df_temp is not None:
                            dfs.append(df_temp)

                # EXCEL
                elif archivo.lower().endswith((".xlsx", ".xls")):

                    with z.open(archivo) as f:

                        pdf = pd.read_excel(
                            io.BytesIO(f.read()),
                            engine="openpyxl"
                        )

                        dfs.append(
                            pl.from_pandas(pdf)
                        )

        if dfs:
            return pl.concat(dfs)

    # ================= EXCEL =================
    else:

        pdf = pd.read_excel(
            uploaded_file,
            engine="openpyxl"
        )

        return pl.from_pandas(pdf)

    return None


# ================= UPLOAD =================
uploaded_files = st.file_uploader(
    "📂 Subir archivos",
    type=["xlsx", "csv", "zip"],
    accept_multiple_files=True
)

# ================= PROCESAMIENTO =================
if uploaded_files:

    with st.spinner("Procesando archivos..."):

        inicio = time.time()

        dfs = []

        for file in uploaded_files:

            df_temp = cargar_archivo(file)

            if df_temp is not None:

                # ================= NORMALIZAR COLUMNAS =================
                df_temp.columns = [
                    c.lower().strip()
                    for c in df_temp.columns
                ]

                dfs.append(df_temp)

        if dfs:

            # ================= CONCAT =================
            df = pl.concat(dfs)

            # ================= NORMALIZAR =================
            if "tx_currency_code" in df.columns:

                df = df.with_columns(
                    pl.col("tx_currency_code")
                    .cast(pl.Utf8)
                    .str.to_uppercase()
                )

            if "tx_reference" in df.columns:

                df = df.with_columns(
                    pl.col("tx_reference")
                    .cast(pl.Utf8)
                    .str.to_uppercase()
                )

            # ================= FECHA =================
            if "x_create_date_gmt_peru" in df.columns:

                df = df.with_columns(
                    pl.col("x_create_date_gmt_peru")
                    .cast(pl.Utf8)
                    .str.slice(0, 7)
                    .alias("mes")
                )

            # ================= ELIMINAR DUPLICADOS =================
            if "psp_tin" in df.columns:

                df = df.unique(
                    subset=["psp_tin"]
                )

            # ================= SIDEBAR =================
            st.sidebar.header("⚙️ Configuración")

            # Meses
            meses = []

            if "mes" in df.columns:

                meses = (
                    df["mes"]
                    .drop_nulls()
                    .unique()
                    .sort()
                    .to_list()
                )

            mes_sel = st.sidebar.selectbox(
                "Mes",
                meses
            ) if meses else None

            moneda = st.sidebar.selectbox(
                "Moneda",
                ["PEN", "USD"]
            )

            porcentaje = st.sidebar.number_input(
                "Comisión %",
                value=2.30
            )

            fee_fijo = st.sidebar.number_input(
                "Fee fijo",
                value=0.90
            )

            opcion = st.sidebar.radio(
                "Tipo de reporte",
                [
                    "Comparación de comisiones",
                    "Reporte detallado",
                    "Ambos"
                ]
            )

            # ================= FILTROS =================
            if mes_sel:

                df = df.filter(
                    pl.col("mes") == mes_sel
                )

            df = df.filter(
                pl.col("tx_currency_code") == moneda
            )

            # ================= PY / SF =================
            pagos = df.filter(
                pl.col("tx_reference")
                .str.starts_with("PY")
            )

            fees = df.filter(
                pl.col("tx_reference")
                .str.starts_with("SF")
            )

            # ================= JOIN =================
            merge = pagos.join(
                fees.select([
                    "psp_tin",
                    "tx_amount",
                    "tx_reference"
                ]),
                on="psp_tin",
                how="left"
            )

            merge = merge.rename({
                "tx_amount": "monto_pago",
                "tx_amount_right": "comision_real",
                "tx_reference": "PY_operation_no",
                "tx_reference_right": "SF_operation_no"
            })

            # ================= NUMERICOS =================
            merge = merge.with_columns([

                pl.col("monto_pago")
                .cast(pl.Float64),

                pl.col("comision_real")
                .cast(pl.Float64)
                .abs()

            ])

            # ================= CALCULOS =================
            merge = merge.with_columns([

                (
                    (pl.col("monto_pago") * (porcentaje / 100))
                    + fee_fijo
                ).alias("comision_base"),

            ])

            merge = merge.with_columns([

                (
                    pl.col("comision_base") * 0.18
                ).alias("igv")

            ])

            merge = merge.with_columns([

                (
                    pl.col("comision_base")
                    + pl.col("igv")
                ).alias("comision_final")

            ])

            merge = merge.with_columns([

                (
                    pl.col("comision_real")
                    - pl.col("comision_final")
                ).alias("diferencia")

            ])

            merge = merge.with_columns([

                (
                    pl.col("monto_pago")
                    - pl.col("comision_real")
                ).alias("total_neto")

            ])

            # ================= METRICAS =================
            total_recaudo = merge["monto_pago"].sum()
            total_comisiones = merge["comision_real"].sum()
            total_igv = merge["igv"].sum()
            total_neto = merge["total_neto"].sum()
            total_operaciones = merge.height

            c1, c2, c3, c4, c5 = st.columns(5)

            with c1:
                st.metric(
                    "💰 Recaudado",
                    f"{total_recaudo:,.2f}"
                )

            with c2:
                st.metric(
                    "💸 Comisiones",
                    f"{total_comisiones:,.2f}"
                )

            with c3:
                st.metric(
                    "🏛 IGV",
                    f"{total_igv:,.2f}"
                )

            with c4:
                st.metric(
                    "🧮 Neto",
                    f"{total_neto:,.2f}"
                )

            with c5:
                st.metric(
                    "🔢 Operaciones",
                    f"{total_operaciones:,}"
                )

            # ================= COMPARACION =================
            if opcion in [
                "Comparación de comisiones",
                "Ambos"
            ]:

                st.subheader("📋 Comparación de Comisiones")

                columnas_comisiones = [

                    "psp_tin",
                    "monto_pago",
                    "comision_real",
                    "comision_base",
                    "igv",
                    "comision_final",
                    "diferencia",
                    "total_neto"

                ]

                columnas_existentes = [
                    c for c in columnas_comisiones
                    if c in merge.columns
                ]

                tabla_comisiones = (
                    merge
                    .select(columnas_existentes)
                    .to_pandas()
                )

                st.dataframe(
                    tabla_comisiones,
                    use_container_width=True,
                    height=500
                )

                csv_comisiones = (
                    tabla_comisiones
                    .to_csv(index=False)
                    .encode("utf-8")
                )

                st.download_button(
                    "📥 Descargar comisiones CSV",
                    csv_comisiones,
                    file_name="comisiones.csv",
                    mime="text/csv"
                )

            # ================= DETALLADO =================
            if opcion in [
                "Reporte detallado",
                "Ambos"
            ]:

                st.subheader("📄 Reporte Detallado")

                columnas_detalle = [

                    "x_create_date_gmt_peru",
                    "com_nombre",
                    "tx_currency_code",
                    "deb_nombre",
                    "psp_tin",
                    "PY_operation_no",
                    "SF_operation_no",
                    "monto_pago",
                    "comision_real"

                ]

                columnas_detalle_existentes = [
                    c for c in columnas_detalle
                    if c in merge.columns
                ]

                detalle = (
                    merge
                    .select(columnas_detalle_existentes)
                    .to_pandas()
                )

                st.dataframe(
                    detalle,
                    use_container_width=True,
                    height=500
                )

                csv_detalle = (
                    detalle
                    .to_csv(index=False)
                    .encode("utf-8")
                )

                st.download_button(
                    "📥 Descargar reporte detallado",
                    csv_detalle,
                    file_name="reporte_detallado.csv",
                    mime="text/csv"
                )

                # ================= RESUMEN COMERCIOS =================
                if "com_nombre" in merge.columns:

                    st.subheader("🏪 Resumen por Comercio")

                    resumen = (
                        merge
                        .group_by("com_nombre")
                        .agg([
                            pl.col("comision_real")
                            .sum()
                            .alias("TOTAL_COMISION")
                        ])
                        .sort(
                            "TOTAL_COMISION",
                            descending=True
                        )
                        .to_pandas()
                    )

                    st.dataframe(
                        resumen,
                        use_container_width=True,
                        height=400
                    )

                    csv_resumen = (
                        resumen
                        .to_csv(index=False)
                        .encode("utf-8")
                    )

                    st.download_button(
                        "📥 Descargar resumen comercios",
                        csv_resumen,
                        file_name="resumen_comercios.csv",
                        mime="text/csv"
                    )

            # ================= TIEMPO =================
            fin = time.time()

            st.success(
                f"✅ Procesado en {round(fin - inicio, 2)} segundos"
            )
