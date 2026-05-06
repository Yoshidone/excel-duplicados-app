import streamlit as st
import pandas as pd
import polars as pl
import zipfile
import io

st.set_page_config(
    page_title="Analizador Financiero Payin",
    layout="wide"
)

# ================= ESTILO =================
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

st.title("📊 Analizador Financiero Payin")

# ================= SUBIR ARCHIVOS =================
archivos = st.file_uploader(
    "Sube tu archivo Excel, CSV o ZIP",
    type=["xlsx", "csv", "zip"],
    accept_multiple_files=True
)

# ================= EXPORTAR CSV =================
def exportar_csv(df):
    return df.to_csv(index=False).encode("utf-8")

# ================= COLUMNAS NECESARIAS =================
columnas_necesarias = [
    "x_create_date_gmt_peru",
    "tx_currency_code",
    "tx_reference",
    "tx_amount",
    "psp_tin",
    "deb_nombre",
    "com_nombre",
    "tipo",
    "set_referencia",
    "fecha transferencia"
]

# ================= LEER CSV RAPIDO =================
def leer_csv_seguro(f):

    for sep in [",", ";"]:

        try:

            f.seek(0)

            df = pl.read_csv(
                f,
                separator=sep,
                ignore_errors=True
            )

            return df.to_pandas()

        except:
            continue

    raise ValueError("No se pudo leer el CSV")

# ================= CARGAR ARCHIVO =================
@st.cache_data
def cargar_archivo(file):

    nombre = file.name.lower()

    # ================= CSV =================
    if nombre.endswith(".csv"):

        df_csv = leer_csv_seguro(file)

        df_csv.columns = (
            df_csv.columns
            .str.lower()
            .str.strip()
        )

        df_csv = df_csv[
            [
                c for c in columnas_necesarias
                if c in df_csv.columns
            ]
        ]

        return df_csv

    # ================= ZIP =================
    elif nombre.endswith(".zip"):

        dfs_zip = []

        with zipfile.ZipFile(file) as z:

            for nombre_archivo in z.namelist():

                # ================= CSV EN ZIP =================
                if nombre_archivo.lower().endswith(".csv"):

                    with z.open(nombre_archivo) as f:

                        df_zip = leer_csv_seguro(
                            io.BytesIO(f.read())
                        )

                        df_zip.columns = (
                            df_zip.columns
                            .str.lower()
                            .str.strip()
                        )

                        df_zip = df_zip[
                            [
                                c for c in columnas_necesarias
                                if c in df_zip.columns
                            ]
                        ]

                        dfs_zip.append(df_zip)

                # ================= EXCEL EN ZIP =================
                elif nombre_archivo.lower().endswith((".xlsx", ".xls")):

                    with z.open(nombre_archivo) as f:

                        df_zip = pd.read_excel(
                            io.BytesIO(f.read()),
                            engine="calamine"
                        )

                        df_zip.columns = (
                            df_zip.columns
                            .str.lower()
                            .str.strip()
                        )

                        df_zip = df_zip[
                            [
                                c for c in columnas_necesarias
                                if c in df_zip.columns
                            ]
                        ]

                        dfs_zip.append(df_zip)

        if dfs_zip:

            return pd.concat(
                dfs_zip,
                ignore_index=True,
                copy=False
            )

        raise ValueError("ZIP sin archivos válidos")

    # ================= EXCEL =================
    else:

        df_excel = pd.read_excel(
            file,
            engine="calamine"
        )

        df_excel.columns = (
            df_excel.columns
            .str.lower()
            .str.strip()
        )

        df_excel = df_excel[
            [
                c for c in columnas_necesarias
                if c in df_excel.columns
            ]
        ]

        return df_excel

# ================= PROCESAR =================
if archivos:

    with st.spinner("⏳ Procesando archivos grandes..."):

        dfs = []

        for archivo in archivos:

            df_temp = cargar_archivo(archivo)

            dfs.append(df_temp)

        df = pd.concat(
            dfs,
            ignore_index=True,
            copy=False
        )

        # EVITAR DUPLICAR RAM
        df_original = df

        st.success("✅ Archivo cargado correctamente")

        # ================= LIMPIEZA =================
        df["tx_currency_code"] = (
            df["tx_currency_code"]
            .astype(str)
            .str.upper()
        )

        df["tx_reference"] = (
            df["tx_reference"]
            .astype(str)
            .str.upper()
        )

        # ================= OPCION REPORTE =================
        st.divider()

        opcion_reporte = st.radio(
            "Selecciona qué deseas visualizar:",
            [
                "Comparación de comisiones",
                "Reporte detallado",
                "Ambas"
            ],
            horizontal=True,
            index=None
        )

        if opcion_reporte:

            # ================= FILTROS =================
            st.divider()

            col1, col2 = st.columns(2)

            df["fecha"] = pd.to_datetime(
                df["x_create_date_gmt_peru"],
                errors="coerce"
            )

            df["mes"] = (
                df["fecha"]
                .dt.strftime("%Y-%m")
            )

            mes_sel = col1.selectbox(
                "Selecciona un mes",
                sorted(df["mes"].dropna().unique())
            )

            moneda_sel = col2.selectbox(
                "Selecciona moneda",
                ["PEN", "USD"]
            )

            df = df[
                (df["mes"] == mes_sel) &
                (df["tx_currency_code"] == moneda_sel)
            ]

            simbolo = (
                "S/"
                if moneda_sel == "PEN"
                else "$"
            )

            # ================= COMPARACION =================
            if opcion_reporte in [
                "Comparación de comisiones",
                "Ambas"
            ]:

                st.divider()

                st.subheader(
                    f"📋 Comparación de comisiones ({moneda_sel})"
                )

                porcentaje = st.number_input(
                    "Porcentaje comisión (%)",
                    value=2.30
                )

                fee_fijo = st.number_input(
                    f"Fee fijo ({simbolo})",
                    value=0.90
                )

                pagos = df[
                    df["tx_reference"]
                    .str.startswith("PY", na=False)
                ].copy()

                fees = df[
                    df["tx_reference"]
                    .str.startswith("SF", na=False)
                ].copy()

                comisiones = pagos.merge(
                    fees[[
                        "psp_tin",
                        "tx_amount",
                        "tx_reference"
                    ]],
                    on="psp_tin",
                    how="left",
                    suffixes=(
                        "_pago",
                        "_comision"
                    )
                )

                comisiones.rename(
                    columns={
                        "tx_reference": "SF_operation_no"
                    },
                    inplace=True
                )

                comisiones["tx_amount_pago"] = pd.to_numeric(
                    comisiones["tx_amount_pago"],
                    errors="coerce"
                )

                comisiones["tx_amount_comision"] = pd.to_numeric(
                    comisiones["tx_amount_comision"],
                    errors="coerce"
                )

                comisiones["comision_real"] = (
                    comisiones["tx_amount_comision"]
                    .abs()
                )

                comisiones["comision_base"] = (
                    (
                        comisiones["tx_amount_pago"]
                        * (porcentaje / 100)
                    )
                    + fee_fijo
                )

                comisiones["igv"] = (
                    comisiones["comision_base"]
                    * 0.18
                ).round(2)

                comisiones["comision_final"] = (
                    comisiones["comision_base"]
                    + comisiones["igv"]
                ).round(2)

                comisiones["diferencia"] = (
                    comisiones["comision_real"]
                    - comisiones["comision_final"]
                ).round(2)

                comisiones["total_neto"] = (
                    comisiones["tx_amount_pago"]
                    - comisiones["comision_real"]
                ).round(2)

                tabla = comisiones[
                    [
                        "psp_tin",
                        "tx_amount_pago",
                        "comision_real",
                        "comision_base",
                        "igv",
                        "comision_final",
                        "diferencia",
                        "total_neto",
                        "SF_operation_no"
                    ]
                ].fillna(0)

                st.dataframe(
                    tabla.head(500),
                    use_container_width=True,
                    height=500
                )

                st.download_button(
                    "📥 Descargar comparación",
                    exportar_csv(tabla),
                    "comparacion_comisiones.csv"
                )

                # ================= METRICAS =================
                st.divider()

                total_recaudo = tabla["tx_amount_pago"].sum()
                total_comisiones = tabla["comision_real"].sum()
                total_igv = tabla["igv"].sum()
                total_neto = tabla["total_neto"].sum()
                total_operaciones = tabla["psp_tin"].nunique()

                c1, c2, c3, c4, c5 = st.columns(5)

                c1.metric(
                    "💰 Recaudado",
                    f"{simbolo} {total_recaudo:,.2f}"
                )

                c2.metric(
                    "💸 Comisiones",
                    f"{simbolo} {total_comisiones:,.2f}"
                )

                c3.metric(
                    "🏛️ IGV",
                    f"{simbolo} {total_igv:,.2f}"
                )

                c4.metric(
                    "🧾 Neto",
                    f"{simbolo} {total_neto:,.2f}"
                )

                c5.metric(
                    "🔢 Operaciones",
                    total_operaciones
                )

            # ================= REPORTE DETALLADO =================
            if opcion_reporte in [
                "Reporte detallado",
                "Ambas"
            ]:

                st.divider()

                st.subheader(
                    "📄 Reporte detallado"
                )

                pagos = df[
                    df["tx_reference"]
                    .str.startswith("PY", na=False)
                ].copy()

                fees = df[
                    df["tx_reference"]
                    .str.startswith("SF", na=False)
                ].copy()

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
                    fees[[
                        "psp_tin",
                        "COMISION",
                        "SF_operation_no"
                    ]],
                    on="psp_tin",
                    how="left"
                )

                reporte = pd.DataFrame({
                    "FECHA": detalle.get(
                        "x_create_date_gmt_peru",
                        ""
                    ),
                    "COMERCIO": detalle.get(
                        "com_nombre",
                        ""
                    ),
                    "MONEDA": detalle.get(
                        "tx_currency_code",
                        ""
                    ),
                    "CLIENTE": detalle.get(
                        "deb_nombre",
                        ""
                    ),
                    "psp_tin": detalle["psp_tin"],
                    "tipo": detalle.get(
                        "tipo",
                        ""
                    ),
                    "PY_operation_no": detalle[
                        "PY_operation_no"
                    ],
                    "SF_operation_no": detalle[
                        "SF_operation_no"
                    ],
                    "RECAUDO": detalle[
                        "RECAUDO"
                    ],
                    "COMISION": (
                        detalle["COMISION"]
                        .abs()
                    ),
                    "SET_referencia": detalle.get(
                        "set_referencia",
                        ""
                    ),
                    "Fecha Transferencia": detalle.get(
                        "fecha transferencia",
                        ""
                    )
                }).fillna(0)

                st.dataframe(
                    reporte.head(500),
                    use_container_width=True,
                    height=500
                )

                st.download_button(
                    "📥 Descargar reporte detallado",
                    exportar_csv(reporte),
                    "reporte_detallado.csv"
                )

                # ================= RESUMEN COMERCIOS =================
                st.divider()

                st.subheader(
                    "🏪 Total de comisiones por comercio"
                )

                resumen_comercios = (
                    reporte.groupby(
                        "COMERCIO",
                        as_index=False
                    )["COMISION"]
                    .sum()
                    .sort_values(
                        "COMISION",
                        ascending=False
                    )
                )

                resumen_comercios["COMISION"] = (
                    resumen_comercios["COMISION"]
                    .round(2)
                )

                st.dataframe(
                    resumen_comercios.head(500),
                    use_container_width=True,
                    height=400
                )

                st.download_button(
                    "📥 Descargar resumen comercios",
                    exportar_csv(
                        resumen_comercios
                    ),
                    "resumen_comercios.csv"
                )

# ================= TODOS LOS MESES =================
if archivos:

    st.divider()

    st.subheader(
        "📦 Reporte detallado (todos los meses)"
    )

    pagos_full = df_original[
        df_original["tx_reference"]
        .str.startswith("PY", na=False)
    ].copy()

    fees_full = df_original[
        df_original["tx_reference"]
        .str.startswith("SF", na=False)
    ].copy()

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
        fees_full[[
            "psp_tin",
            "COMISION",
            "SF_operation_no"
        ]],
        on="psp_tin",
        how="left"
    )

    reporte_full = pd.DataFrame({
        "FECHA": detalle_full.get(
            "x_create_date_gmt_peru",
            ""
        ),
        "COMERCIO": detalle_full.get(
            "com_nombre",
            ""
        ),
        "MONEDA": detalle_full.get(
            "tx_currency_code",
            ""
        ),
        "CLIENTE": detalle_full.get(
            "deb_nombre",
            ""
        ),
        "psp_tin": detalle_full["psp_tin"],
        "tipo": detalle_full.get(
            "tipo",
            ""
        ),
        "PY_operation_no": detalle_full[
            "PY_operation_no"
        ],
        "SF_operation_no": detalle_full[
            "SF_operation_no"
        ],
        "RECAUDO": detalle_full[
            "RECAUDO"
        ],
        "COMISION": (
            detalle_full["COMISION"]
            .abs()
        ),
        "SET_referencia": detalle_full.get(
            "set_referencia",
            ""
        ),
        "Fecha Transferencia": detalle_full.get(
            "fecha transferencia",
            ""
        )
    }).fillna(0)

    st.download_button(
        "📥 Descargar reporte detallado completo",
        exportar_csv(reporte_full),
        "reporte_detallado_todos.csv"
    )
