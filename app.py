import dash
from dash import dcc, html, dash_table, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import pandas as pd
import polars as pl
import zipfile
import base64
import io

# ================= APP =================
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True
)
server = app.server  # Para deploy con gunicorn

# ================= ESTILOS =================
CARD_STYLE = {
    "backgroundColor": "#111827",
    "border": "1px solid #374151",
    "borderRadius": "12px",
    "padding": "20px",
    "marginBottom": "16px"
}

METRIC_STYLE = {
    "backgroundColor": "#1F2937",
    "border": "1px solid #374151",
    "borderRadius": "12px",
    "padding": "16px",
    "textAlign": "center"
}

LABEL_STYLE = {
    "color": "#9CA3AF",
    "fontSize": "13px",
    "marginBottom": "4px"
}

VALUE_STYLE = {
    "color": "#F9FAFB",
    "fontSize": "22px",
    "fontWeight": "600",
    "margin": "0"
}

TABLE_STYLE = {
    "backgroundColor": "#1F2937",
    "color": "#F9FAFB",
    "border": "none"
}

# ================= LAYOUT =================
app.layout = html.Div(
    style={"backgroundColor": "#0F172A", "minHeight": "100vh", "fontFamily": "Inter, sans-serif"},
    children=[

        # Header
        html.Div(
            style={"backgroundColor": "#111827", "borderBottom": "1px solid #374151",
                   "padding": "20px 40px", "marginBottom": "32px"},
            children=[
                html.H1("Analizador Financiero Payin",
                        style={"color": "#F9FAFB", "margin": "0", "fontSize": "24px", "fontWeight": "700"}),
                html.P("Sube tus archivos para comenzar el análisis",
                       style={"color": "#6B7280", "margin": "4px 0 0", "fontSize": "14px"})
            ]
        ),

        html.Div(
            style={"maxWidth": "1400px", "margin": "0 auto", "padding": "0 40px 40px"},
            children=[

                # ================= UPLOAD =================
                html.Div(
                    style=CARD_STYLE,
                    children=[
                        html.H3("📂 Cargar archivos", style={"color": "#F9FAFB", "marginBottom": "16px", "fontSize": "16px"}),
                        dcc.Upload(
                            id="upload-data",
                            children=html.Div([
                                html.I(className="", style={"fontSize": "32px", "marginBottom": "8px", "display": "block"}),
                                html.Span("Arrastra archivos aquí o ", style={"color": "#9CA3AF"}),
                                html.Span("haz clic para seleccionar", style={"color": "#3B82F6", "cursor": "pointer"}),
                                html.Br(),
                                html.Small("Excel (.xlsx), CSV o ZIP", style={"color": "#6B7280"})
                            ]),
                            style={
                                "border": "2px dashed #374151",
                                "borderRadius": "12px",
                                "padding": "40px",
                                "textAlign": "center",
                                "cursor": "pointer",
                                "backgroundColor": "#1F2937",
                                "transition": "border-color 0.2s"
                            },
                            multiple=True,
                            accept=".xlsx,.csv,.zip"
                        ),
                        html.Div(id="upload-status", style={"marginTop": "12px"})
                    ]
                ),

                # ================= CONTROLES =================
                html.Div(id="controles-section"),

                # ================= RESULTADOS =================
                html.Div(id="resultados-section"),

                # Store para datos
                dcc.Store(id="store-data"),
                dcc.Store(id="store-data-original"),
            ]
        )
    ]
)

# ================= HELPERS =================
def leer_csv_seguro(f):
    for sep in [",", ";"]:
        try:
            if hasattr(f, "seek"):
                f.seek(0)
            df = pl.read_csv(f, separator=sep, ignore_errors=True)
            return df.to_pandas()
        except Exception:
            continue
    raise ValueError("No se pudo leer el CSV")


def cargar_archivo_bytes(content, filename):
    content_type, content_string = content.split(",")
    decoded = base64.b64decode(content_string)
    nombre = filename.lower()

    if nombre.endswith(".csv"):
        return leer_csv_seguro(io.BytesIO(decoded))

    elif nombre.endswith(".zip"):
        dfs_zip = []
        with zipfile.ZipFile(io.BytesIO(decoded)) as z:
            for nombre_archivo in z.namelist():
                if nombre_archivo.lower().endswith(".csv"):
                    with z.open(nombre_archivo) as f:
                        df_zip = leer_csv_seguro(f)
                        df_zip.columns = df_zip.columns.str.lower().str.strip()
                        dfs_zip.append(df_zip)
                elif nombre_archivo.lower().endswith((".xlsx", ".xls")):
                    with z.open(nombre_archivo) as f:
                        df_zip = pl.from_pandas(pd.read_excel(f, engine="openpyxl")).to_pandas()
                        df_zip.columns = df_zip.columns.str.lower().str.strip()
                        dfs_zip.append(df_zip)
        if dfs_zip:
            return pd.concat(dfs_zip, ignore_index=True)
        raise ValueError("ZIP sin CSV ni Excel")

    else:
        return pl.from_pandas(pd.read_excel(io.BytesIO(decoded), engine="openpyxl")).to_pandas()


def exportar_csv(df):
    return df.to_csv(index=False)


# ================= CALLBACK: CARGAR DATOS =================
@app.callback(
    Output("store-data", "data"),
    Output("store-data-original", "data"),
    Output("upload-status", "children"),
    Input("upload-data", "contents"),
    State("upload-data", "filename"),
    prevent_initial_call=True
)
def cargar_datos(list_of_contents, list_of_names):
    if not list_of_contents:
        return None, None, ""

    try:
        dfs = []
        for content, filename in zip(list_of_contents, list_of_names):
            df_temp = cargar_archivo_bytes(content, filename)
            df_temp.columns = df_temp.columns.str.lower().str.strip()
            dfs.append(df_temp)

        df = pd.concat(dfs, ignore_index=True)

        df["tx_currency_code"] = df["tx_currency_code"].astype(str).str.upper()
        df["tx_reference"] = df["tx_reference"].astype(str).str.upper()

        nombres = ", ".join(list_of_names)
        status = dbc.Alert(
            f"✅ Archivos cargados: {nombres} — {len(df):,} filas",
            color="success",
            style={"backgroundColor": "#064E3B", "border": "1px solid #065F46",
                   "color": "#D1FAE5", "borderRadius": "8px"}
        )

        return df.to_json(date_format="iso", orient="split"), df.to_json(date_format="iso", orient="split"), status

    except Exception as e:
        status = dbc.Alert(f"❌ Error al cargar: {str(e)}", color="danger")
        return None, None, status


# ================= CALLBACK: MOSTRAR CONTROLES =================
@app.callback(
    Output("controles-section", "children"),
    Input("store-data", "data"),
    prevent_initial_call=True
)
def mostrar_controles(data):
    if not data:
        return ""

    df = pd.read_json(io.StringIO(data), orient="split")
    df["fecha"] = pd.to_datetime(df["x_create_date_gmt_peru"], errors="coerce")
    df["mes"] = df["fecha"].dt.strftime("%Y-%m")
    meses = sorted(df["mes"].dropna().unique())

    return html.Div(
        style=CARD_STYLE,
        children=[
            html.H3("⚙️ Configuración del reporte", style={"color": "#F9FAFB", "marginBottom": "20px", "fontSize": "16px"}),

            dbc.Row([
                dbc.Col([
                    html.Label("Tipo de reporte", style=LABEL_STYLE),
                    dcc.RadioItems(
                        id="opcion-reporte",
                        options=[
                            {"label": " Comparación de comisiones", "value": "comisiones"},
                            {"label": " Reporte detallado", "value": "detallado"},
                            {"label": " Ambas", "value": "ambas"},
                        ],
                        inline=True,
                        style={"color": "#F9FAFB", "gap": "20px", "display": "flex"},
                        inputStyle={"marginRight": "6px"}
                    )
                ], md=12, style={"marginBottom": "16px"}),

                dbc.Col([
                    html.Label("Mes", style=LABEL_STYLE),
                    dcc.Dropdown(
                        id="mes-sel",
                        options=[{"label": m, "value": m} for m in meses],
                        value=meses[-1] if meses else None,
                        style={"backgroundColor": "#1F2937", "color": "#F9FAFB", "border": "1px solid #374151"},
                        className="dark-dropdown"
                    )
                ], md=4),

                dbc.Col([
                    html.Label("Moneda", style=LABEL_STYLE),
                    dcc.Dropdown(
                        id="moneda-sel",
                        options=[{"label": "PEN (S/)", "value": "PEN"}, {"label": "USD ($)", "value": "USD"}],
                        value="PEN",
                        style={"backgroundColor": "#1F2937", "color": "#F9FAFB", "border": "1px solid #374151"}
                    )
                ], md=3),

                dbc.Col([
                    html.Label("Comisión (%)", style=LABEL_STYLE),
                    dcc.Input(id="porcentaje", type="number", value=2.30, step=0.01,
                              style={"backgroundColor": "#1F2937", "color": "#F9FAFB",
                                     "border": "1px solid #374151", "borderRadius": "8px",
                                     "padding": "8px 12px", "width": "100%"})
                ], md=2),

                dbc.Col([
                    html.Label("Fee fijo", style=LABEL_STYLE),
                    dcc.Input(id="fee-fijo", type="number", value=0.90, step=0.01,
                              style={"backgroundColor": "#1F2937", "color": "#F9FAFB",
                                     "border": "1px solid #374151", "borderRadius": "8px",
                                     "padding": "8px 12px", "width": "100%"})
                ], md=3),
            ]),

            html.Div(style={"marginTop": "16px"}, children=[
                html.Button("🔍 Generar reporte", id="btn-generar",
                            style={"backgroundColor": "#3B82F6", "color": "white", "border": "none",
                                   "borderRadius": "8px", "padding": "10px 24px", "cursor": "pointer",
                                   "fontSize": "14px", "fontWeight": "600"})
            ])
        ]
    )


# ================= CALLBACK: GENERAR RESULTADOS =================
@app.callback(
    Output("resultados-section", "children"),
    Input("btn-generar", "n_clicks"),
    State("store-data", "data"),
    State("store-data-original", "data"),
    State("opcion-reporte", "value"),
    State("mes-sel", "value"),
    State("moneda-sel", "value"),
    State("porcentaje", "value"),
    State("fee-fijo", "value"),
    prevent_initial_call=True
)
def generar_reporte(n_clicks, data, data_original, opcion, mes_sel, moneda_sel, porcentaje, fee_fijo):
    if not data or not opcion:
        return dbc.Alert("⚠️ Selecciona todas las opciones", color="warning")

    df = pd.read_json(io.StringIO(data), orient="split")
    df_original = pd.read_json(io.StringIO(data_original), orient="split")

    df["fecha"] = pd.to_datetime(df["x_create_date_gmt_peru"], errors="coerce")
    df["mes"] = df["fecha"].dt.strftime("%Y-%m")
    df["tx_currency_code"] = df["tx_currency_code"].astype(str).str.upper()
    df["tx_reference"] = df["tx_reference"].astype(str).str.upper()

    df = df[(df["mes"] == mes_sel) & (df["tx_currency_code"] == moneda_sel)]
    simbolo = "S/" if moneda_sel == "PEN" else "$"

    secciones = []

    # ================= COMPARACION DE COMISIONES =================
    if opcion in ["comisiones", "ambas"]:
        pagos = df[df["tx_reference"].str.startswith("PY", na=False)].copy()
        fees = df[df["tx_reference"].str.startswith("SF", na=False)].copy()

        comisiones = pagos.merge(
            fees[["psp_tin", "tx_amount"]], on="psp_tin", how="left", suffixes=("_pago", "_comision")
        )
        comisiones["tx_amount_pago"] = pd.to_numeric(comisiones["tx_amount_pago"], errors="coerce")
        comisiones["tx_amount_comision"] = pd.to_numeric(comisiones["tx_amount_comision"], errors="coerce")
        comisiones["comision_real"] = comisiones["tx_amount_comision"].abs()
        comisiones["comision_base"] = (comisiones["tx_amount_pago"] * (porcentaje / 100)) + fee_fijo
        comisiones["igv"] = (comisiones["comision_base"] * 0.18).round(2)
        comisiones["comision_final"] = (comisiones["comision_base"] + comisiones["igv"]).round(2)
        comisiones["diferencia"] = (comisiones["comision_real"] - comisiones["comision_final"]).round(2)
        comisiones["total_neto"] = (comisiones["tx_amount_pago"] - comisiones["comision_real"]).round(2)

        tabla = comisiones[[
            "psp_tin", "tx_amount_pago", "comision_real",
            "comision_base", "igv", "comision_final", "diferencia", "total_neto"
        ]].fillna(0).head(500)

        total_recaudo = tabla["tx_amount_pago"].sum()
        total_base = tabla["comision_base"].sum()
        total_igv = round(total_base * 0.18, 2)
        total_final = round(total_base + total_igv, 2)
        total_comisiones = round(tabla["comision_real"].sum(), 2)
        total_neto = round(tabla["total_neto"].sum(), 2)
        total_diferencia = round(total_comisiones - total_final, 2)
        operaciones = tabla["psp_tin"].nunique()

        metricas = html.Div([
            html.H4("📊 Resumen financiero", style={"color": "#F9FAFB", "marginBottom": "16px"}),
            dbc.Row([
                dbc.Col(html.Div([html.P("💰 Recaudado", style=LABEL_STYLE), html.H3(f"{simbolo} {total_recaudo:,.2f}", style=VALUE_STYLE)], style=METRIC_STYLE), md=3),
                dbc.Col(html.Div([html.P("💸 Comisiones", style=LABEL_STYLE), html.H3(f"{simbolo} {total_comisiones:,.2f}", style=VALUE_STYLE)], style=METRIC_STYLE), md=3),
                dbc.Col(html.Div([html.P("🧾 Base", style=LABEL_STYLE), html.H3(f"{simbolo} {total_base:,.2f}", style=VALUE_STYLE)], style=METRIC_STYLE), md=3),
                dbc.Col(html.Div([html.P("🏛 IGV", style=LABEL_STYLE), html.H3(f"{simbolo} {total_igv:,.2f}", style=VALUE_STYLE)], style=METRIC_STYLE), md=3),
            ], style={"marginBottom": "12px"}),
            dbc.Row([
                dbc.Col(html.Div([html.P("📑 Final", style=LABEL_STYLE), html.H3(f"{simbolo} {total_final:,.2f}", style=VALUE_STYLE)], style=METRIC_STYLE), md=3),
                dbc.Col(html.Div([html.P("⚖️ Diferencia", style=LABEL_STYLE), html.H3(f"{simbolo} {total_diferencia:,.2f}", style=VALUE_STYLE)], style=METRIC_STYLE), md=3),
                dbc.Col(html.Div([html.P("🔢 Operaciones", style=LABEL_STYLE), html.H3(f"{operaciones:,}", style=VALUE_STYLE)], style=METRIC_STYLE), md=3),
                dbc.Col(html.Div([html.P("🧮 Neto", style=LABEL_STYLE), html.H3(f"{simbolo} {total_neto:,.2f}", style=VALUE_STYLE)], style=METRIC_STYLE), md=3),
            ])
        ])

        csv_comisiones = exportar_csv(tabla)

        seccion_comisiones = html.Div(style=CARD_STYLE, children=[
            html.H3(f"📋 Comparación de comisiones ({moneda_sel})",
                    style={"color": "#F9FAFB", "marginBottom": "16px", "fontSize": "16px"}),
            metricas,
            html.Hr(style={"borderColor": "#374151", "margin": "20px 0"}),
            dash_table.DataTable(
                data=tabla.to_dict("records"),
                columns=[{"name": c, "id": c} for c in tabla.columns],
                page_size=20,
                style_table={"overflowX": "auto", "borderRadius": "8px"},
                style_cell={"backgroundColor": "#1F2937", "color": "#F9FAFB",
                            "border": "1px solid #374151", "padding": "8px 12px",
                            "fontSize": "13px", "fontFamily": "monospace"},
                style_header={"backgroundColor": "#111827", "color": "#9CA3AF",
                              "fontWeight": "600", "border": "1px solid #374151"},
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": "#1a2332"},
                    {"if": {"filter_query": "{diferencia} > 0", "column_id": "diferencia"},
                     "color": "#34D399"},
                    {"if": {"filter_query": "{diferencia} < 0", "column_id": "diferencia"},
                     "color": "#F87171"},
                ]
            ),
            html.Div(style={"marginTop": "16px"}, children=[
                html.A("📥 Descargar comisiones CSV",
                       id="download-comisiones",
                       download="comisiones.csv",
                       href="data:text/csv;charset=utf-8," + csv_comisiones,
                       style={"backgroundColor": "#374151", "color": "#F9FAFB", "padding": "8px 16px",
                              "borderRadius": "8px", "textDecoration": "none", "fontSize": "13px"})
            ])
        ])
        secciones.append(seccion_comisiones)

    # ================= REPORTE DETALLADO =================
    if opcion in ["detallado", "ambas"]:
        pagos = df[df["tx_reference"].str.startswith("PY", na=False)].copy()
        fees = df[df["tx_reference"].str.startswith("SF", na=False)].copy()

        pagos.rename(columns={"tx_amount": "RECAUDO", "tx_reference": "PY_operation_no"}, inplace=True)
        fees.rename(columns={"tx_amount": "COMISION", "tx_reference": "SF_operation_no"}, inplace=True)

        detalle = pagos.merge(fees[["psp_tin", "COMISION", "SF_operation_no"]], on="psp_tin", how="left")

        reporte = pd.DataFrame({
            "FECHA": detalle.get("x_create_date_gmt_peru", ""),
            "COMERCIO": detalle.get("com_nombre", ""),
            "MONEDA": detalle.get("tx_currency_code", ""),
            "CLIENTE": detalle.get("deb_nombre", ""),
            "psp_tin": detalle["psp_tin"],
            "tipo": detalle.get("tipo", ""),
            "PY_operation_no": detalle["PY_operation_no"],
            "SF_operation_no": detalle["SF_operation_no"],
            "RECAUDO": detalle["RECAUDO"],
            "COMISION": pd.to_numeric(detalle["COMISION"], errors="coerce").abs(),
            "SET_referencia": detalle.get("set_referencia", ""),
            "Fecha Transferencia": detalle.get("fecha transferencia", "")
        }).fillna(0)

        resumen_comercios = (
            reporte.groupby("COMERCIO", as_index=False)["COMISION"]
            .sum()
            .sort_values("COMISION", ascending=False)
        )
        resumen_comercios["COMISION"] = resumen_comercios["COMISION"].round(2)

        csv_detalle = exportar_csv(reporte)
        csv_comercios = exportar_csv(resumen_comercios)

        # Reporte todos los meses
        df_original["tx_reference"] = df_original["tx_reference"].astype(str).str.upper()
        pagos_full = df_original[df_original["tx_reference"].str.startswith("PY", na=False)].copy()
        fees_full = df_original[df_original["tx_reference"].str.startswith("SF", na=False)].copy()
        pagos_full.rename(columns={"tx_amount": "RECAUDO", "tx_reference": "PY_operation_no"}, inplace=True)
        fees_full.rename(columns={"tx_amount": "COMISION", "tx_reference": "SF_operation_no"}, inplace=True)
        detalle_full = pagos_full.merge(fees_full[["psp_tin", "COMISION", "SF_operation_no"]], on="psp_tin", how="left")
        reporte_full = pd.DataFrame({
            "FECHA": detalle_full.get("x_create_date_gmt_peru", ""),
            "COMERCIO": detalle_full.get("com_nombre", ""),
            "MONEDA": detalle_full.get("tx_currency_code", ""),
            "CLIENTE": detalle_full.get("deb_nombre", ""),
            "psp_tin": detalle_full["psp_tin"],
            "PY_operation_no": detalle_full["PY_operation_no"],
            "SF_operation_no": detalle_full["SF_operation_no"],
            "RECAUDO": detalle_full["RECAUDO"],
            "COMISION": pd.to_numeric(detalle_full["COMISION"], errors="coerce").abs(),
        }).fillna(0)
        csv_full = exportar_csv(reporte_full)

        seccion_detalle = html.Div(style=CARD_STYLE, children=[
            html.H3("📄 Reporte detallado (mes seleccionado)",
                    style={"color": "#F9FAFB", "marginBottom": "16px", "fontSize": "16px"}),
            dash_table.DataTable(
                data=reporte.head(500).to_dict("records"),
                columns=[{"name": c, "id": c} for c in reporte.columns],
                page_size=20,
                style_table={"overflowX": "auto"},
                style_cell={"backgroundColor": "#1F2937", "color": "#F9FAFB",
                            "border": "1px solid #374151", "padding": "8px 12px", "fontSize": "13px"},
                style_header={"backgroundColor": "#111827", "color": "#9CA3AF",
                              "fontWeight": "600", "border": "1px solid #374151"},
                style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "#1a2332"}]
            ),
            html.Div(style={"marginTop": "16px", "display": "flex", "gap": "12px"}, children=[
                html.A("📥 Reporte detallado (mes)", download="reporte_detallado_mes.csv",
                       href="data:text/csv;charset=utf-8," + csv_detalle,
                       style={"backgroundColor": "#374151", "color": "#F9FAFB", "padding": "8px 16px",
                              "borderRadius": "8px", "textDecoration": "none", "fontSize": "13px"}),
                html.A("📥 Reporte todos los meses", download="reporte_todos.csv",
                       href="data:text/csv;charset=utf-8," + csv_full,
                       style={"backgroundColor": "#1D4ED8", "color": "#F9FAFB", "padding": "8px 16px",
                              "borderRadius": "8px", "textDecoration": "none", "fontSize": "13px"}),
            ]),

            html.Hr(style={"borderColor": "#374151", "margin": "20px 0"}),
            html.H4("🏪 Total de comisiones por comercio",
                    style={"color": "#F9FAFB", "marginBottom": "12px", "fontSize": "15px"}),
            dash_table.DataTable(
                data=resumen_comercios.head(100).to_dict("records"),
                columns=[{"name": c, "id": c} for c in resumen_comercios.columns],
                page_size=15,
                style_table={"overflowX": "auto"},
                style_cell={"backgroundColor": "#1F2937", "color": "#F9FAFB",
                            "border": "1px solid #374151", "padding": "8px 12px", "fontSize": "13px"},
                style_header={"backgroundColor": "#111827", "color": "#9CA3AF",
                              "fontWeight": "600", "border": "1px solid #374151"},
                style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "#1a2332"}]
            ),
            html.Div(style={"marginTop": "12px"}, children=[
                html.A("📥 Descargar resumen comercios", download="resumen_comercios.csv",
                       href="data:text/csv;charset=utf-8," + csv_comercios,
                       style={"backgroundColor": "#374151", "color": "#F9FAFB", "padding": "8px 16px",
                              "borderRadius": "8px", "textDecoration": "none", "fontSize": "13px"}),
            ])
        ])
        secciones.append(seccion_detalle)

    return html.Div(secciones)


# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)
