import streamlit as st
import pandas as pd
import polars as pl
import zipfile
import io

st.set_page_config(page_title="Analizador Financiero Payin", layout="wide")

st.markdown("""
<style>

/* Fondo */
.stApp{
background-color:#0f172a;
}

/* Contenedor */
.block-container{
padding-top:2rem;
padding-bottom:2rem;
max-width:1400px;
}

/* Titulo */
h1{
color:white !important;
font-size:52px !important;
font-weight:800 !important;
letter-spacing:-1px;
}

/* Subtitulos */
h2,h3{
color:white !important;
font-weight:700 !important;
}

/* Textos */
label,p,span{
color:#e5e7eb !important;
}

/* Upload moderno */
[data-testid="stFileUploader"]{
background:linear-gradient(135deg,#111827,#1f2937);
padding:30px;
border-radius:20px;
border:2px dashed #3b82f6;
box-shadow:0 4px 15px rgba(0,0,0,0.25);
}

/* Hover uploader */
[data-testid="stFileUploader"]:hover{
border:2px dashed #60a5fa;
}

/* Cards metrics */
[data-testid="metric-container"]{
background:linear-gradient(135deg,#111827,#1f2937);
border:1px solid #374151;
padding:18px;
border-radius:18px;
box-shadow:0 4px 15px rgba(0,0,0,0.25);
transition:0.3s;
}

[data-testid="metric-container"]:hover{
transform:translateY(-2px);
box-shadow:0 8px 20px rgba(0,0,0,0.35);
}

[data-testid="metric-container"] label{
color:#9ca3af !important;
font-size:14px;
}

[data-testid="metric-container"] div{
color:white !important;
}

/* Dataframes */
[data-testid="stDataFrame"]{
border-radius:16px;
overflow:hidden;
border:1px solid #374151;
margin-top:10px;
margin-bottom:10px;
}

/* Selectbox */
.stSelectbox div[data-baseweb="select"]{
background-color:#111827;
border-radius:12px;
border:1px solid #374151;
}

/* Radio */
.stRadio > div{
background-color:#111827;
padding:12px;
border-radius:14px;
border:1px solid #374151;
}

/* Botones */
.stDownloadButton button,
.stButton button{
background:linear-gradient(135deg,#2563eb,#1d4ed8);
color:white;
border:none;
border-radius:12px;
padding:10px 18px;
font-weight:600;
transition:0.3s;
}

.stDownloadButton button:hover,
.stButton button:hover{
transform:scale(1.02);
background:linear-gradient(135deg,#1d4ed8,#1e40af);
}

/* Inputs */
.stNumberInput input{
background-color:#111827 !important;
color:white !important;
border-radius:10px !important;
}

/* Success */
.stSuccess{
border-radius:14px;
}

/* Sidebar */
section[data-testid="stSidebar"]{
background:#111827;
}

/* Divider elegante */
hr{
border:0;
height:1px;
background:#374151;
margin-top:30px;
margin-bottom:30px;
}

/* Scroll */
::-webkit-scrollbar{
width:10px;
height:10px;
}

::-webkit-scrollbar-thumb{
background:#374151;
border-radius:10px;
}

</style>
""", unsafe_allow_html=True)

st.title("💳 Analizador Financiero Payin")
st.caption("Dashboard financiero y análisis de comisiones")

# ================= SUBIR ARCHIVOS =================
archivos = st.file_uploader(
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

            df = pl.read_csv(
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

    nombre = file.name.lower()

    # CSV
    if nombre.endswith(".csv"):

        return leer_csv_seguro(file)

    # ZIP
    elif nombre.endswith(".zip"):

        dfs_zip = []

        with zipfile.ZipFile(file) as z:

            for nombre_archivo in z.namelist():

                # CSV EN ZIP
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

                        dfs_zip.append(df_zip)

                # EXCEL EN ZIP
                elif nombre_archivo.lower().endswith((".xlsx",".xls")):

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

                        dfs_zip.append(df_zip)

        if dfs_zip:
            return pd.concat(dfs_zip, ignore_index=True)

        raise ValueError("ZIP sin CSV ni Excel")

    # EXCEL
    else:

        return pd.read_excel(
            file,
            engine="calamine"
        )

# ================= PROCESAR =================
if archivos:

    with st.spinner("⏳ Procesando archivos grandes..."):

        dfs = []

        for archivo in archivos:

            df_temp = cargar_archivo(archivo)

            df_temp.columns = (
                df_temp.columns
                .str.lower()
                .str.strip()
            )

            dfs.append(df_temp)

        df = pd.concat(dfs, ignore_index=True)

        # Optimización RAM
        df_original = df

        st.success("✅ Archivo cargado correctamente")

        df["tx_currency_code"] = (
            df["tx_currency_code"]
            .astype(str)
            .str.upper()
        )

        # Corregir monedas
        df["tx_currency_code"] = (
            df["tx_currency_code"]
            .replace({
                "BOLÍGRAFO":"PEN",
                "DÓLAR ESTADOUNIDENSE":"USD",
                "DOLAR ESTADOUNIDENSE":"USD"
            })
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
                ["PEN","USD"]
            )

            df = df[
                (df["mes"] == mes_sel) &
                (df["tx_currency_code"] == moneda_sel)
            ]

            simbolo = "S/" if moneda_sel == "PEN" else "$"

            # ================= COMPARACION =================
            if opcion_reporte in [
                "Comparación de comisiones",
                "Ambas"
            ]:

                st.divider()

                st.subheader(
                    f"Comparación de comisiones ({moneda_sel})"
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
                    fees[
                        [
                            "psp_tin",
                            "tx_amount"
                        ]
                    ],
                    on="psp_tin",
                    how="left",
                    suffixes=(
                        "_pago",
                        "_comision"
                    )
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
                        "total_neto"
                    ]
                ].fillna(0)

                st.dataframe(
                    tabla.head(100),
                    use_container_width=True
                )

                st.download_button(
                    "📥 Descargar comparación de comisiones",
                    exportar_csv(tabla),
                    "comisiones.csv"
                )
