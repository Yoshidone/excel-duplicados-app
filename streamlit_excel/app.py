import streamlit as st
import pandas as pd
from io import BytesIO

st.title("Detector de Duplicados y Separador por Moneda")

archivo = st.file_uploader("Sube tu archivo Excel", type=["xlsx"])

if archivo is not None:

    df = pd.read_excel(archivo)

    duplicados = df[df.duplicated(keep=False)]

    st.subheader("Registros duplicados encontrados")

    if not duplicados.empty:
        st.dataframe(duplicados)
        st.warning(f"Se encontraron {len(duplicados)} registros duplicados")
    else:
        st.success("No se encontraron duplicados")

    if "Moneda" in df.columns:
        soles = df[df["Moneda"] == "PEN"]
        dolares = df[df["Moneda"] == "USD"]
    else:
        soles = pd.DataFrame()
        dolares = pd.DataFrame()

    def convertir_excel(dataframe):
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            dataframe.to_excel(writer, index=False)
        return output.getvalue()

    st.subheader("Descargar archivos")

    st.download_button(
        "Descargar Excel completo",
        convertir_excel(df),
        "archivo_completo.xlsx"
    )

    st.download_button(
        "Descargar duplicados",
        convertir_excel(duplicados),
        "duplicados.xlsx"
    )

    if not soles.empty:
        st.download_button(
            "Descargar Soles",
            convertir_excel(soles),
            "soles.xlsx"
        )

    if not dolares.empty:
        st.download_button(
            "Descargar Dólares",
            convertir_excel(dolares),
            "dolares.xlsx"
        )
