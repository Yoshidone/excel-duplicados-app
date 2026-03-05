# ---------------------------
# Conciliación PY vs SF
# ---------------------------

tabla["estado_conciliacion"] = "OK"

tabla.loc[
    (tabla["tx_amount_pago"] == 0) & (tabla["comision"] > 0),
    "estado_conciliacion"
] = "COMISION SIN PAGO"

tabla.loc[
    (tabla["tx_amount_pago"] > 0) & (tabla["comision"] == 0),
    "estado_conciliacion"
] = "PAGO SIN COMISION"

# Mostrar resumen
st.subheader("Conciliación PY vs SF")

c1, c2, c3 = st.columns(3)

c1.metric(
    "Operaciones correctas",
    len(tabla[tabla["estado_conciliacion"] == "OK"])
)

c2.metric(
    "Pagos sin comisión",
    len(tabla[tabla["estado_conciliacion"] == "PAGO SIN COMISION"])
)

c3.metric(
    "Comisiones sin pago",
    len(tabla[tabla["estado_conciliacion"] == "COMISION SIN PAGO"])
)

# Mostrar errores
errores = tabla[tabla["estado_conciliacion"] != "OK"]

if len(errores) > 0:
    st.subheader("Errores detectados")
    st.dataframe(errores)
