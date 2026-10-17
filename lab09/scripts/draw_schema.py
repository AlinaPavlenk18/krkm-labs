import html
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NODES = { 
    "Consumer": (60, 200, "#dae8fc", ["id 🔑", "category", "contractLimit", "+ :Residential | :Commercial | :Industrial"]),
    "Meter": (60, 470, "#dae8fc", ["id 🔑", "status (idx)", "meterType", "readingInterval"]),
    "Measurement": (400, 640, "#d5e8d4", ["id 🔑", "timestamp (idx)", "consumptionValue", "voltage"]),
    "WeatherCondition": (820, 760, "#d5e8d4", ["id 🔑", "temperature", "cloudCover"]),
    "ForecastModel": (720, 470, "#ffe6cc", ["id 🔑", "modelType", "accuracy", "trainingDate", "+ :MLModel | :StatisticalModel"]),
    "Forecast": (1090, 470, "#ffe6cc", ["id 🔑", "errorPercentage (idx)", "predictedConsumption", "forecastPeriod"]),
    "Dispatcher": (1090, 200, "#e1d5e7", ["id 🔑", "qualification", "shift"]),
    "Substation": (560, 200, "#f8cecc", ["id 🔑", "nominalCapacity", "currentLoad", "pagerank, community (GDS)"]),
    "Region": (560, 20, "#f8cecc", ["id 🔑", "name"]),
}
EDGES = [("Consumer", "Meter", "HAS_METER"), ("Consumer", "Substation", "CONNECTED_TO"),
         ("Meter", "Measurement", "RECORDED"), ("WeatherCondition", "Measurement", "INFLUENCES"),
         ("WeatherCondition", "ForecastModel", "AFFECTS_MODEL"), ("ForecastModel", "Measurement", "TRAINED_ON"),
         ("ForecastModel", "Forecast", "GENERATED"), ("Dispatcher", "Forecast", "USES_FORECAST"),
         ("Dispatcher", "Substation", "MANAGES"), ("Substation", "Substation", "FEEDS"),
         ("Substation", "Region", "LOCATED_IN"), ("Forecast", "Substation", "FORECAST_FOR")]
W, H = 260, 130


cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
for i, (lab, (x, y, col, props)) in enumerate(NODES.items()):
    val = html.escape(f"<b>:{lab}</b><hr>" + "<br>".join(props))
    cells.append(f'<mxCell id="n{i}" value="{val}" style="rounded=1;whiteSpace=wrap;html=1;fillColor={col};'
                 f'strokeColor=#555555;align=left;spacingLeft=8;verticalAlign=top;fontSize=12;" vertex="1" parent="1">'
                 f'<mxGeometry x="{x}" y="{y}" width="{W}" height="{H}" as="geometry"/></mxCell>')
ids = {lab: f"n{i}" for i, lab in enumerate(NODES)}
for j, (a, b, t) in enumerate(EDGES):
    extra = "loop=1;" if a == b else ""
    cells.append(f'<mxCell id="e{j}" value="{t}" style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=block;'
                 f'fontSize=11;labelBackgroundColor=#ffffff;{extra}" edge="1" parent="1" source="{ids[a]}" target="{ids[b]}">'
                 f'<mxGeometry relative="1" as="geometry"/></mxCell>')
note = html.escape("<b>Властивості походження на ВСІХ зв'язках:</b><br>source (lab08:data.ttl | synthetic:gen_v1(seed=42) | derived:lab09)"
                   "<br>confidence (0..1)<br>validFrom (date)<br><br>🔑 — унікальне обмеження; (idx) — індекс")
cells.append(f'<mxCell id="note" value="{note}" style="shape=note;whiteSpace=wrap;html=1;align=left;spacingLeft=8;'
             f'fillColor=#fff2cc;strokeColor=#d6b656;fontSize=12;" vertex="1" parent="1">'
             f'<mxGeometry x="40" y="700" width="330" height="140" as="geometry"/></mxCell>')
xml = ('<mxfile host="app.diagrams.net"><diagram name="LPG schema ЛР9"><mxGraphModel dx="1400" dy="900" grid="1" '
       'gridSize="10" page="1" pageScale="1" pageWidth="1400" pageHeight="950"><root>' + "".join(cells) +
       '</root></mxGraphModel></diagram></mxfile>')
(ROOT / "docs" / "graph_schema.drawio").write_text(xml, encoding="utf-8")


lines = ['digraph G {', 'graph [rankdir=LR, splines=true, nodesep=0.6, ranksep=1.0, pad=0.3, fontname="DejaVu Sans", '
         'label="Графова схема (LPG) ЛР9 · на всіх зв\'язках: source, confidence, validFrom · (UNIQUE) унікальне обмеження, (idx) індекс", '
         'labelloc=b, fontsize=12];',
         'node [shape=plain, fontname="DejaVu Sans", fontsize=11];',
         'edge [fontname="DejaVu Sans", fontsize=10, color="#444444", arrowsize=0.8];']
for lab, (x, y, col, props) in NODES.items():
    rows = "".join(f'<TR><TD ALIGN="LEFT">{html.escape(p.replace("🔑", "(UNIQUE)"))}</TD></TR>' for p in props)
    lines.append(f'{lab} [label=<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4" BGCOLOR="{col}" '
                 f'STYLE="ROUNDED"><TR><TD><B>:{lab}</B></TD></TR><HR/>{rows}</TABLE>>];')
for a, b, t in EDGES:
    lines.append(f'{a} -> {b} [label="{t}"];')
lines.append("}")
dot = "\n".join(lines)
(ROOT / "docs" / "graph_schema.dot").write_text(dot, encoding="utf-8")
subprocess.run(["dot", "-Tpng", "-Gdpi=150", "-o", str(ROOT / "docs" / "graph_schema.png")], input=dot.encode(), check=True)
print("ok")
