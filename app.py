import streamlit as st
import pandas as pd
import zipfile
from io import BytesIO

st.set_page_config(page_title="Analizador Financiero", layout="wide")

st.title("Dashboard financiero")

# -------------------------
# CONFIGURACIÓN COMISIONES
# -------------------------

porcentaje = st.number_input("Porcentaje comisión (%)", value=2.30)
fee_fijo = st.number_input("Fee fijo", value=0.90)
aplicar_igv = st.checkbox("Aplicar IGV (18%)", value=True)

porcentaje = porcentaje / 100


# -------------------------
# SUBIR ARCHIVO
# -------------------------

archivo = st.file_uploader(
    "Subir archivo CSV, Excel o ZIP",
    type=["csv","xlsx","zip"]
)

if archivo:

    # -------------------------
    # LEER ARCHIVO
    # -------------------------

    if archivo.name.endswith(".zip"):

        with zipfile.ZipFile(archivo) as z:

            lista_archivos = z.namelist()

            nombre_archivo = lista_archivos[0]

            with z.open(nombre_archivo) as f:

                if nombre_archivo.endswith(".csv"):
                    try:
                        df = pd.read_csv(f, sep=";")
                    except:
                        df = pd.read_csv(f)

                elif nombre_archivo.endswith(".xlsx"):
                    df = pd.read_excel(f)

    elif archivo.name.endswith(".csv"):

        try:
            df = pd.read_csv(archivo, sep=";")
        except:
            df = pd.read_csv(archivo)

    else:

        df = pd.read_excel(archivo)


    # -------------------------
    # LIMPIAR COLUMNAS
    # -------------------------

    df.columns = df.columns.str.strip()

    st.subheader("Preview datos")
    st.dataframe(df.head())


    # -------------------------
    # VALIDAR COLUMNAS
    # -------------------------

    columnas_necesarias = ["Deuda_external_id","OP_amount"]

    for col in columnas_necesarias:
        if col not in df.columns:
            st.error(f"Falta la columna {col}")
            st.stop()


# LIMPIAR Y CONVERTIR MONTO

df["OP_amount"] = pd.to_numeric(df["OP_amount"], errors="coerce")

# SEPARAR PAGOS Y COMISIONES

pagos = df[df["OP_amount"] > 0]
comisiones = df[df["OP_amount"] < 0]


    # -------------------------
    # CALCULAR COMISIÓN
    # -------------------------

    resultado["comision"] = (resultado["tx_amount_pago"] * porcentaje) + fee_fijo

    if aplicar_igv:
        resultado["comision"] = resultado["comision"] * 1.18

    resultado["comision"] = resultado["comision"].round(2)
   df = df.dropna(subset=["OP_amount"])


    # -------------------------
    # DIFERENCIAS
    # -------------------------

    resultado["diferencia"] = resultado["comision_contrato"] - resultado["comision"]

    resultado["total_neto"] = resultado["tx_amount_pago"] - resultado["comision_contrato"]


    # -------------------------
    # DASHBOARD
    # -------------------------

    st.subheader("Dashboard financiero")

    col1,col2 = st.columns(2)

    with col1:
        st.metric("Total registros", len(df))

    with col2:
        st.metric("Transacciones únicas", len(resultado))


    # -------------------------
    # TABLA
    # -------------------------

    st.dataframe(resultado)


    # -------------------------
    # CONTROL COMISIONES
    # -------------------------

    st.subheader("Control de comisiones")

    no_coinciden = resultado[resultado["diferencia"].abs() > 0.01]

    col1,col2 = st.columns(2)

    with col1:
        st.metric("Total comisiones analizadas", len(resultado))

    with col2:
        st.metric("Comisiones que NO coinciden", len(no_coinciden))


    # -------------------------
    # DESCARGAR RESULTADO
    # -------------------------

    csv = resultado.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Descargar comparación de comisiones",
        csv,
        "comparacion_comisiones.csv",
        "text/csv"
    )

