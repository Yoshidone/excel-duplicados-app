import streamlit as st
import pandas as pd
import polars as pl
import zipfile
import io

st.set_page_config(
    page_title="Analizador Financiero Payin",
    layout="wide"
)

st.markdown("""
<style>

/* ================= FONDO GENERAL ================= */
.stApp{
    background:
    radial-gradient(circle at top left,#FFE7D6 0%,transparent 25%),
    radial-gradient(circle at top right,#DDEBFF 0%,transparent 25%),
    radial-gradient(circle at bottom left,#FFF4C7 0%,transparent 25%),
    #F8FAFC;

    color:#334155;
}

/* ================= CONTENEDOR ================= */
.block-container{
    padding-top:2rem;
    padding-bottom:2rem;
    padding-left:2rem;
    padding-right:2rem;
}

/* ================= TITULOS ================= */
h1,h2,h3{
    color:#1E293B;
    font-weight:700;
    letter-spacing:-0.5px;
}

/* ================= TEXTO ================= */
html, body, p, label, span{
    color:#475569;
    font-family:'Inter',sans-serif;
}

/* ================= METRICAS ================= */
[data-testid="metric-container"]{

    background:rgba(255,255,255,0.65);

    backdrop-filter:blur(18px);

    border:1px solid rgba(255,255,255,0.7);

    border-radius:24px;

    padding:22px;

    box-shadow:
    0 8px 30px rgba(0,0,0,0.06);

    transition:0.3s;
}

/* HOVER METRICAS */
[data-testid="metric-container"]:hover{

    transform:translateY(-3px);

    box-shadow:
    0 12px 35px rgba(0,0,0,0.08);
}

/* LABEL METRICAS */
[data-testid="metric-container"] label{

    color:#64748B !important;

    font-size:14px;

    font-weight:500;
}

/* VALORES */
[data-testid="metric-container"] div{

    color:#1E293B !important;

    font-weight:700;
}

/* ================= TABLAS ================= */
div[data-testid="stDataFrame"]{

    background:rgba(255,255,255,0.70);

    backdrop-filter:blur(18px);

    border-radius:24px;

    border:1px solid rgba(255,255,255,0.7);

    overflow:hidden;

    box-shadow:
    0 8px 30px rgba(0,0,0,0.05);
}

/* TEXTO TABLAS */
[data-testid="stDataFrame"] *{
    color:#475569 !important;
}

/* ================= BOTONES ================= */
.stButton>button,
.stDownloadButton>button{

    background:rgba(255,255,255,0.75);

    color:#334155;

    border:none;

    border-radius:18px;

    padding:0.7rem 1.4rem;

    font-weight:600;

    backdrop-filter:blur(18px);

    box-shadow:
    0 4px 15px rgba(0,0,0,0.05);

    transition:0.3s;
}

/* HOVER BOTONES */
.stButton>button:hover,
.stDownloadButton>button:hover{

    transform:translateY(-2px);

    background:#FFFFFF;

    color:#2563EB;

    box-shadow:
    0 8px 20px rgba(37,99,235,0.15);
}

/* ================= INPUTS ================= */
input{

    background:rgba(255,255,255,0.75) !important;

    border:none !important;

    border-radius:16px !important;

    color:#334155 !important;

    backdrop-filter:blur(18px);

    box-shadow:
    0 4px 15px rgba(0,0,0,0.04);
}

/* ================= SELECTBOX ================= */
div[data-baseweb="select"]{

    background:rgba(255,255,255,0.75);

    border-radius:18px;

    backdrop-filter:blur(18px);

    box-shadow:
    0 4px 15px rgba(0,0,0,0.04);
}

/* ================= RADIO ================= */
div[role="radiogroup"]{

    background:rgba(255,255,255,0.70);

    padding:12px;

    border-radius:22px;

    backdrop-filter:blur(18px);

    box-shadow:
    0 4px 15px rgba(0,0,0,0.04);
}

/* ================= SIDEBAR ================= */
section[data-testid="stSidebar"]{

    background:rgba(255,255,255,0.60);

    backdrop-filter:blur(18px);

    border-right:1px solid rgba(255,255,255,0.5);
}

/* TEXTO SIDEBAR */
section[data-testid="stSidebar"] *{
    color:#475569 !important;
}

/* ================= SCROLL ================= */
::-webkit-scrollbar{
    width:10px;
}

::-webkit-scrollbar-thumb{
    background:#CBD5E1;
    border-radius:10px;
}

/* ================= EFECTOS GLOW ================= */
.stMetric{

    position:relative;
}

.stMetric::after{

    content:"";

    position:absolute;

    width:120px;

    height:120px;

    background:rgba(255,255,255,0.25);

    filter:blur(40px);

    border-radius:50%;

    top:-30px;

    right:-20px;

    z-index:0;
}

</style>
""",unsafe_allow_html=True)

st.title("Analizador Financiero Payin")

# ================= SUBIR ARCHIVOS =================
archivos=st.file_uploader(
    "Sube tu archivo Excel, CSV o ZIP",
    type=["xlsx","csv","zip"],
    accept_multiple_files=True
)

# ================= EXPORTAR =================
def exportar_csv(df):
    return df.to_csv(index=False).encode("utf-8")

# ================= LEER CSV =================
def leer_csv_seguro(f):

    for sep in [",",";"]:

        try:

            f.seek(0)

            df=pl.read_csv(
                f,
                separator=sep,
                ignore_errors=True
            )

            return df.to_pandas()

        except:
            continue

    raise ValueError("No se pudo leer el CSV")

# ================= CARGAR ARCHIVOS =================
@st.cache_data
def cargar_archivo(file):

    nombre=file.name.lower()

    # ================= CSV =================
    if nombre.endswith(".csv"):

        return leer_csv_seguro(file)

    # ================= ZIP =================
    elif nombre.endswith(".zip"):

        dfs_zip=[]

        with zipfile.ZipFile(file) as z:

            for nombre_archivo in z.namelist():

                # ================= CSV EN ZIP =================
                if nombre_archivo.lower().endswith(".csv"):

                    with z.open(nombre_archivo) as f:

                        df_zip=leer_csv_seguro(
                            io.BytesIO(f.read())
                        )

                        df_zip.columns=(
                            df_zip.columns
                            .str.lower()
                            .str.strip()
                        )

                        dfs_zip.append(df_zip)

                # ================= EXCEL EN ZIP =================
                elif nombre_archivo.lower().endswith((".xlsx",".xls")):

                    with z.open(nombre_archivo) as f:

                        df_zip=pd.read_excel(
                            io.BytesIO(f.read()),
                            engine="calamine"
                        )

                        df_zip.columns=(
                            df_zip.columns
                            .str.lower()
                            .str.strip()
                        )

                        dfs_zip.append(df_zip)

        if dfs_zip:
            return pd.concat(dfs_zip,ignore_index=True)

        raise ValueError("ZIP sin CSV ni Excel")

    # ================= EXCEL =================
    else:

        return pd.read_excel(
            file,
            engine="calamine"
        )

# ================= ALTURA DINAMICA =================
def altura_tabla(df,max_height=500):
    filas=len(df)+1
    return min(35*filas,max_height)

# ================= PROCESAR =================
if archivos:

    with st.spinner("⏳ Procesando archivos grandes..."):

        dfs=[]

        for archivo in archivos:

            df_temp=cargar_archivo(archivo)

            df_temp.columns=(
                df_temp.columns
                .str.lower()
                .str.strip()
            )

            dfs.append(df_temp)

        df=pd.concat(dfs,ignore_index=True)

        df_original=df.copy()

        st.success("Archivo cargado correctamente")

        df["tx_currency_code"]=(
            df["tx_currency_code"]
            .astype(str)
            .str.upper()
        )

        # ================= CORREGIR MONEDAS =================
        df["tx_currency_code"]=(
            df["tx_currency_code"]
            .replace({
                "BOLÍGRAFO":"PEN",
                "DÓLAR ESTADOUNIDENSE":"USD",
                "DOLAR ESTADOUNIDENSE":"USD"
            })
        )

        df["tx_reference"]=(
            df["tx_reference"]
            .astype(str)
            .str.upper()
        )

        # ================= OPCION REPORTE =================
        st.divider()

        opcion_reporte=st.radio(
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

            col1,col2=st.columns(2)

            df["fecha"]=pd.to_datetime(
                df["x_create_date_gmt_peru"],
                errors="coerce"
            )

            df["mes"]=(
                df["fecha"]
                .dt.strftime("%Y-%m")
            )

            mes_sel=col1.selectbox(
                "Selecciona un mes",
                sorted(df["mes"].dropna().unique())
            )

            moneda_sel=col2.selectbox(
                "Selecciona moneda",
                ["PEN","USD"]
            )

            df=df[
                (df["mes"]==mes_sel) &
                (df["tx_currency_code"]==moneda_sel)
            ]

            simbolo="S/" if moneda_sel=="PEN" else "$"

            # ================= COMPARACION =================
            if opcion_reporte in [
                "Comparación de comisiones",
                "Ambas"
            ]:

                st.divider()

                st.subheader(
                    f"Comparación de comisiones ({moneda_sel})"
                )

                porcentaje=st.number_input(
                    "Porcentaje comisión (%)",
                    value=2.30
                )

                fee_fijo=st.number_input(
                    f"Fee fijo ({simbolo})",
                    value=0.90
                )

                pagos=df[
                    df["tx_reference"]
                    .str.startswith("PY",na=False)
                ].copy()

                fees=df[
                    df["tx_reference"]
                    .str.startswith("SF",na=False)
                ].copy()

                comisiones=pagos.merge(
                    fees[[
                        "psp_tin",
                        "tx_amount"
                    ]],
                    on="psp_tin",
                    how="left",
                    suffixes=(
                        "_pago",
                        "_comision"
                    )
                )

                comisiones["tx_amount_pago"]=(
                    pd.to_numeric(
                        comisiones["tx_amount_pago"],
                        errors="coerce"
                    )
                )

                comisiones["tx_amount_comision"]=(
                    pd.to_numeric(
                        comisiones["tx_amount_comision"],
                        errors="coerce"
                    )
                )

                comisiones["comision_real"]=(
                    comisiones["tx_amount_comision"]
                    .abs()
                )

                comisiones["comision_base"]=(
                    (
                        comisiones["tx_amount_pago"]
                        *(porcentaje/100)
                    )
                    +fee_fijo
                )

                comisiones["igv"]=(
                    comisiones["comision_base"]
                    *0.18
                ).round(2)

                comisiones["comision_final"]=(
                    comisiones["comision_base"]
                    +comisiones["igv"]
                ).round(2)

                comisiones["diferencia"]=(
                    comisiones["comision_real"]
                    -comisiones["comision_final"]
                ).round(2)

                comisiones["total_neto"]=(
                    comisiones["tx_amount_pago"]
                    -comisiones["comision_real"]
                ).round(2)

                tabla=comisiones[
                    [
                        "psp_tin",
                        "tx_amount_pago",
                        "comision_real",
                        "comision_base",
                        "igv",
                        "comision_final",
                        "diferencia",
                        "total_neto"
                    ]
                ].fillna(0)

                tabla_preview=tabla.head(500)

                st.dataframe(
                    tabla_preview,
                    use_container_width=True,
                    hide_index=True,
                    height=altura_tabla(tabla_preview)
                )

                st.download_button(
                    "📥 Descargar comparación de comisiones",
                    exportar_csv(tabla),
                    "comisiones.csv"
                )

                # ================= RESUMEN =================
                st.subheader("📊 Resumen financiero")

                total_recaudo=tabla["tx_amount_pago"].sum()
                total_base=tabla["comision_base"].sum()

                total_igv=round(
                    total_base*0.18,
                    2
                )

                total_final=round(
                    total_base+total_igv,
                    2
                )

                total_comisiones=round(
                    tabla["comision_real"].sum(),
                    2
                )

                total_neto=round(
                    tabla["total_neto"].sum(),
                    2
                )

                total_diferencia=round(
                    total_comisiones-total_final,
                    2
                )

                operaciones=(
                    tabla["psp_tin"]
                    .nunique()
                )

                c1,c2,c3,c4=st.columns(4)

                c1.metric(
                    "💰 Recaudado",
                    f"{simbolo} {total_recaudo:,.2f}"
                )

                c2.metric(
                    "💸 Comisiones",
                    f"{simbolo} {total_comisiones:,.2f}"
                )

                c3.metric(
                    "🧾 Base",
                    f"{simbolo} {total_base:,.2f}"
                )

                c4.metric(
                    "🏛 IGV",
                    f"{simbolo} {total_igv:,.2f}"
                )

                c5,c6,c7,c8=st.columns(4)

                c5.metric(
                    "📑 Final",
                    f"{simbolo} {total_final:,.2f}"
                )

                c6.metric(
                    "⚖️ Diferencia",
                    f"{simbolo} {total_diferencia:,.2f}"
                )

                c7.metric(
                    "🔢 Operaciones",
                    f"{operaciones:,}"
                )

                c8.metric(
                    "🧮 Neto",
                    f"{simbolo} {total_neto:,.2f}"
                )

            # ================= REPORTE DETALLADO =================
            if opcion_reporte in [
                "Reporte detallado",
                "Ambas"
            ]:

                st.divider()

                st.subheader(
                    "📄 Reporte detallado (mes seleccionado)"
                )

                pagos=df[
                    df["tx_reference"]
                    .str.startswith("PY",na=False)
                ].copy()

                fees=df[
                    df["tx_reference"]
                    .str.startswith("SF",na=False)
                ].copy()

                pagos.rename(
                    columns={
                        "tx_amount":"RECAUDO",
                        "tx_reference":"PY_operation_no"
                    },
                    inplace=True
                )

                fees.rename(
                    columns={
                        "tx_amount":"COMISION",
                        "tx_reference":"SF_operation_no"
                    },
                    inplace=True
                )

                detalle=pagos.merge(
                    fees[[
                        "psp_tin",
                        "COMISION",
                        "SF_operation_no"
                    ]],
                    on="psp_tin",
                    how="left"
                )

                reporte=pd.DataFrame({
                    "FECHA":detalle.get(
                        "x_create_date_gmt_peru",
                        ""
                    ),
                    "COMERCIO":detalle.get(
                        "com_nombre",
                        ""
                    ),
                    "MONEDA":detalle.get(
                        "tx_currency_code",
                        ""
                    ),
                    "CLIENTE":detalle.get(
                        "deb_nombre",
                        ""
                    ),
                    "psp_tin":detalle["psp_tin"],
                    "tipo":detalle.get(
                        "tipo",
                        ""
                    ),
                    "PY_operation_no":detalle[
                        "PY_operation_no"
                    ],
                    "SF_operation_no":detalle[
                        "SF_operation_no"
                    ],
                    "RECAUDO":detalle[
                        "RECAUDO"
                    ],
                    "COMISION":(
                        detalle["COMISION"]
                        .abs()
                    ),
                    "SET_referencia":detalle.get(
                        "set_referencia",
                        ""
                    ),
                    "Fecha Transferencia":detalle.get(
                        "fecha transferencia",
                        ""
                    )
                }).fillna(0)

                reporte_preview=reporte.head(500)

                st.dataframe(
                    reporte_preview,
                    use_container_width=True,
                    hide_index=True,
                    height=altura_tabla(reporte_preview)
                )

                st.download_button(
                    "📥 Descargar reporte detallado (mes)",
                    exportar_csv(reporte),
                    "reporte_detallado_mes.csv"
                )

                # ================= TOTAL COMISIONES =================
                st.divider()

                st.subheader(
                    "🏪 Total de comisiones por comercio"
                )

                resumen_comercios=(
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

                resumen_comercios["COMISION"]=(
                    resumen_comercios["COMISION"]
                    .round(2)
                )

                resumen_preview=resumen_comercios.head(500)

                    resumen_preview=resumen_comercios.head(500)

                st.dataframe(
                    resumen_preview,
                    use_container_width=True,
                    hide_index=True,
                    height=altura_tabla(resumen_preview),

                    column_config={
                        "COMISION": st.column_config.NumberColumn(
                            "COMISION",
                            format="%.2f",
                            width="medium"
                        )
                    }
                )

                st.download_button(
                    "📥 Descargar total comisiones por comercio",
                    exportar_csv(
                        resumen_comercios
                    ),
                    "total_comisiones_comercio.csv"
                )
               
# ================= TODOS LOS MESES =================
if archivos:

    st.subheader(
        "📦 Reporte detallado (todos los meses)"
    )

    df_full=df_original.copy()

    pagos_full=df_full[
        df_full["tx_reference"]
        .str.startswith("PY",na=False)
    ].copy()

    fees_full=df_full[
        df_full["tx_reference"]
        .str.startswith("SF",na=False)
    ].copy()

    pagos_full.rename(
        columns={
            "tx_amount":"RECAUDO",
            "tx_reference":"PY_operation_no"
        },
        inplace=True
    )

    fees_full.rename(
        columns={
            "tx_amount":"COMISION",
            "tx_reference":"SF_operation_no"
        },
        inplace=True
    )

    detalle_full=pagos_full.merge(
        fees_full[[
            "psp_tin",
            "COMISION",
            "SF_operation_no"
        ]],
        on="psp_tin",
        how="left"
    )

    reporte_full=pd.DataFrame({
        "FECHA":detalle_full.get(
            "x_create_date_gmt_peru",
            ""
        ),
        "COMERCIO":detalle_full.get(
            "com_nombre",
            ""
        ),
        "MONEDA":detalle_full.get(
            "tx_currency_code",
            ""
        ),
        "CLIENTE":detalle_full.get(
            "deb_nombre",
            ""
        ),
        "psp_tin":detalle_full["psp_tin"],
        "tipo":detalle_full.get(
            "tipo",
            ""
        ),
        "PY_operation_no":detalle_full[
            "PY_operation_no"
        ],
        "SF_operation_no":detalle_full[
            "SF_operation_no"
        ],
        "RECAUDO":detalle_full[
            "RECAUDO"
        ],
        "COMISION":(
            detalle_full["COMISION"]
            .abs()
        ),
        "SET_referencia":detalle_full.get(
            "set_referencia",
            ""
        ),
        "Fecha Transferencia":detalle_full.get(
            "fecha transferencia",
            ""
        )
    }).fillna(0)

    st.download_button(
        "📥 Descargar reporte detallado (todos)",
        exportar_csv(reporte_full),
        "reporte_detallado_todos.csv"
    )
