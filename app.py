import streamlit as st
import pandas as pd
import polars as pl
import zipfile
import io

st.set_page_config(page_title="Analizador Financiero Payin",layout="wide")

st.markdown("""
<style>

/* Fondo general */
.stApp{
background:#f5f7fb;
}

/* Contenedor */
.block-container{
padding-top:1.5rem;
padding-bottom:2rem;
max-width:1450px;
}

/* Header */
h1{
font-size:52px !important;
font-weight:800 !important;
color:#111827 !important;
margin-bottom:5px;
}

h2,h3{
color:#111827 !important;
font-weight:700 !important;
}

/* Texto */
label,p,span{
color:#374151 !important;
}

/* Upload */
[data-testid="stFileUploader"]{
background:white;
border:2px dashed #cbd5e1;
padding:25px;
border-radius:22px;
box-shadow:0 4px 18px rgba(0,0,0,0.05);
}

/* Cards métricas */
[data-testid="metric-container"]{
background:white;
border-radius:22px;
padding:22px;
border:1px solid #e5e7eb;
box-shadow:0 4px 18px rgba(0,0,0,0.05);
transition:0.3s;
}

[data-testid="metric-container"]:hover{
transform:translateY(-2px);
box-shadow:0 8px 24px rgba(0,0,0,0.08);
}

[data-testid="metric-container"] label{
color:#6b7280 !important;
font-size:14px;
font-weight:600;
}

[data-testid="metric-container"] div{
color:#111827 !important;
font-weight:700;
}

/* Dataframes */
[data-testid="stDataFrame"]{
background:white;
border-radius:20px;
padding:10px;
border:1px solid #e5e7eb;
box-shadow:0 4px 18px rgba(0,0,0,0.05);
overflow:hidden;
}

/* Selectbox */
.stSelectbox div[data-baseweb="select"]{
background:white;
border-radius:16px;
border:1px solid #d1d5db;
min-height:48px;
}

/* Inputs */
.stNumberInput input{
background:white !important;
border-radius:14px !important;
border:1px solid #d1d5db !important;
}

/* Radio */
.stRadio > div{
background:white;
padding:15px;
border-radius:18px;
border:1px solid #e5e7eb;
box-shadow:0 4px 18px rgba(0,0,0,0.05);
}

/* Botones */
.stDownloadButton button,
.stButton button{
background:linear-gradient(135deg,#2563eb,#3b82f6);
color:white;
border:none;
padding:12px 22px;
border-radius:14px;
font-weight:700;
transition:0.3s;
}

.stDownloadButton button:hover,
.stButton button:hover{
transform:scale(1.02);
background:linear-gradient(135deg,#1d4ed8,#2563eb);
}

/* Success */
.stSuccess{
background:#ecfdf5;
border-radius:18px;
padding:15px;
}

/* Divider */
hr{
margin-top:2rem;
margin-bottom:2rem;
}

/* Scroll */
::-webkit-scrollbar{
width:10px;
height:10px;
}

::-webkit-scrollbar-thumb{
background:#cbd5e1;
border-radius:10px;
}

</style>
""",unsafe_allow_html=True)

st.title("💳 Analizador Financiero Payin")
st.caption("Dashboard financiero y análisis de comisiones")

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

    if nombre.endswith(".csv"):

        return leer_csv_seguro(file)

    elif nombre.endswith(".zip"):

        dfs_zip=[]

        with zipfile.ZipFile(file) as z:

            for nombre_archivo in z.namelist():

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

    else:

        return pd.read_excel(
            file,
            engine="calamine"
        )

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

        df_original=df

        st.success("✅ Archivo cargado correctamente")

        df["tx_currency_code"]=(
            df["tx_currency_code"]
            .astype(str)
            .str.upper()
        )

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
                "📅 Selecciona un mes",
                sorted(df["mes"].dropna().unique())
            )

            moneda_sel=col2.selectbox(
                "💵 Selecciona moneda",
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
                    f"💰 Comparación de comisiones ({moneda_sel})"
                )

                col3,col4=st.columns(2)

                porcentaje=col3.number_input(
                    "Porcentaje comisión (%)",
                    value=2.30
                )

                fee_fijo=col4.number_input(
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

                comisiones["tx_amount_pago"]=pd.to_numeric(
                    comisiones["tx_amount_pago"],
                    errors="coerce"
                )

                comisiones["tx_amount_comision"]=pd.to_numeric(
                    comisiones["tx_amount_comision"],
                    errors="coerce"
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

                st.dataframe(
                    tabla.head(100),
                    use_container_width=True
                )

                st.download_button(
                    "📥 Descargar comparación de comisiones",
                    exportar_csv(tabla),
                    "comisiones.csv"
                )

                st.subheader("📊 Resumen financiero")

                total_recaudo=tabla["tx_amount_pago"].sum()
                total_base=tabla["comision_base"].sum()
                total_igv=round(total_base*0.18,2)
                total_final=round(total_base+total_igv,2)
                total_comisiones=round(tabla["comision_real"].sum(),2)
                total_neto=round(tabla["total_neto"].sum(),2)
                total_diferencia=round(total_comisiones-total_final,2)
                operaciones=tabla["psp_tin"].nunique()

                c1,c2,c3,c4=st.columns(4)

                c1.metric("💰 Recaudado",f"{simbolo} {total_recaudo:,.2f}")
                c2.metric("💸 Comisiones",f"{simbolo} {total_comisiones:,.2f}")
                c3.metric("🧾 Base",f"{simbolo} {total_base:,.2f}")
                c4.metric("🏛 IGV",f"{simbolo} {total_igv:,.2f}")

                c5,c6,c7,c8=st.columns(4)

                c5.metric("📑 Final",f"{simbolo} {total_final:,.2f}")
                c6.metric("⚖️ Diferencia",f"{simbolo} {total_diferencia:,.2f}")
                c7.metric("🔢 Operaciones",f"{operaciones:,}")
                c8.metric("🧮 Neto",f"{simbolo} {total_neto:,.2f}")
