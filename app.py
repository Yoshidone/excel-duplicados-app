comisiones = pagos.merge(
    fees[["psp_tin", "tx_amount"]],
    on="psp_tin",
    how="left",
    suffixes=("_pago", "_comision")
)

# AGREGADO (para traer la moneda PEN / USD al análisis)
comisiones["tx_currency_code"] = pagos["tx_currency_code"].values

comisiones["tx_amount_pago"] = pd.to_numeric(comisiones["tx_amount_pago"], errors="coerce")
comisiones["tx_amount_comision"] = pd.to_numeric(comisiones["tx_amount_comision"], errors="coerce")

comisiones["comision_real"] = comisiones["tx_amount_comision"].abs()

comisiones["comision_base"] = (
    (comisiones["tx_amount_pago"] * (porcentaje / 100)) + fee_fijo
)

comisiones["igv"] = comisiones["comision_base"] * 0.18

if aplicar_igv:
    comisiones["comision_final"] = comisiones["comision_base"] + comisiones["igv"]
else:
    comisiones["comision_final"] = comisiones["comision_base"]
    comisiones["igv"] = 0

# ==============================
# REDONDEO POR OPERACIÓN
# ==============================
comisiones["tx_amount_pago"] = comisiones["tx_amount_pago"].round(2)
comisiones["comision_real"] = comisiones["comision_real"].round(2)
comisiones["comision_base"] = comisiones["comision_base"].round(2)
comisiones["igv"] = comisiones["igv"].round(2)
comisiones["comision_final"] = comisiones["comision_final"].round(2)

comisiones["diferencia"] = (comisiones["comision_real"] - comisiones["comision_final"]).round(2)
comisiones["total_neto"] = (comisiones["tx_amount_pago"] - comisiones["comision_real"]).round(2)

tabla = comisiones[
    [
        "psp_tin",
        "tx_amount_pago",
        "tx_currency_code",  # AGREGADO
        "comision_real",
        "comision_base",
        "igv",
        "comision_final",
        "diferencia",
        "total_neto"
    ]
].fillna(0)

# ✅ AGREGAR FECHA SIMPLE (SIN CAMBIAR LÓGICA)
if "x_create_date_gmt_peru" in pagos.columns:
    tabla["x_create_date_gmt_peru"] = pagos["x_create_date_gmt_peru"].values

st.dataframe(tabla)

st.download_button(
    "📥 Descargar comparación de comisiones",
    exportar_csv(tabla),
    "comparacion_comisiones.csv",
    mime="text/csv"
)

# ========= DESCARGA POR MESES =========
if "x_create_date_gmt_peru" in tabla.columns:

    tabla_descarga = tabla.copy()
    tabla_descarga["fecha"] = pd.to_datetime(
        tabla_descarga["x_create_date_gmt_peru"],
        errors="coerce"
    )
    tabla_descarga["periodo"] = tabla_descarga["fecha"].dt.to_period("M")

    buffer_zip = BytesIO()

    with zipfile.ZipFile(buffer_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for periodo, datos_mes in tabla_descarga.groupby("periodo"):
            nombre_archivo = f"comparacion_{periodo}.csv"
            z.writestr(nombre_archivo, exportar_csv(datos_mes.drop(columns=["fecha","periodo"])))

    buffer_zip.seek(0)

    st.download_button(
        "📥 Descargar comparaciones por meses (ZIP)",
        data=buffer_zip,
        file_name="comparaciones_mensuales.zip",
        mime="application/zip"
    )

# ================= RESUMEN =================
st.subheader("Resumen financiero")

total_recaudo = tabla["tx_amount_pago"].sum()
total_comisiones = tabla["comision_real"].sum()
total_base = tabla["comision_base"].sum()
total_igv = tabla["igv"].sum()
total_final = tabla["comision_final"].sum()
total_neto = tabla["total_neto"].sum()
total_diferencia = tabla["diferencia"].sum()
operaciones = len(tabla)

c1, c2, c3 = st.columns(3)
c4, c5, c6 = st.columns(3)
c7, _, _ = st.columns(3)

c1.metric("💰 Total Recaudado", f"S/ {total_recaudo:,.2f}")
c2.metric("💸 Comisiones Reales", f"S/ {total_comisiones:,.2f}")
c3.metric("🧾 Comisión Base", f"S/ {total_base:,.2f}")
c4.metric("🏛 IGV Total", f"S/ {total_igv:,.2f}")
c5.metric("📑 Comisión Final", f"S/ {total_final:,.2f}")
c6.metric("🔢 Número de Operaciones", f"{operaciones:,}")
st.metric("🧮 Total Neto", f"S/ {total_neto:,.2f}")
c7.metric("⚖️ Diferencia Total", f"S/ {total_diferencia:,.2f}")

# ================= REPORTE MENSUAL =================
st.divider()
st.subheader("📊 Reporte mensual")

if "x_create_date_gmt_peru" in tabla.columns:
    tabla["fecha"] = pd.to_datetime(
        tabla["x_create_date_gmt_peru"],
        errors="coerce"
    )
    tabla["periodo"] = tabla["fecha"].dt.to_period("M")

    meses_nombres = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                     "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

    tipo_cambio = st.number_input("Tipo de cambio PEN → USD", value=3.75, step=0.01)

    for periodo, datos_mes in tabla.groupby("periodo"):
        año, mes = str(periodo).split("-")
        nombre_mes = meses_nombres[int(mes)-1]

        recaudado_mes = datos_mes["tx_amount_pago"].sum()
        neto_mes = datos_mes["total_neto"].sum()
        diferencia_mes = datos_mes["diferencia"].sum()
        operaciones_mes = len(datos_mes)
        usd_mes = recaudado_mes / tipo_cambio

        st.markdown(f"### 📅 {nombre_mes} {año}")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("💰 Recaudado", f"S/ {recaudado_mes:,.2f}")
        c2.metric("💵 USD", f"US$ {usd_mes:,.2f}")
        c3.metric("🔢 Operaciones", f"{operaciones_mes:,}")
        c4.metric("🧮 Neto", f"S/ {neto_mes:,.2f}")
        c5.metric("⚖️ Diferencia", f"S/ {diferencia_mes:,.2f}")
        st.markdown("---")
