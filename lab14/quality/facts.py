"""Числові факти з корпусу для перевірки узгодженості (Р1, метрика consistency) і пошуку суперечностей значень (Р3).

Величини (ключ — сутність + властивість), шаблони — регулярні вирази, вивчені на корпусі:
  Substation_N · load_pct        «№5 (93,6 %)» у реченні про завантаження; «коефіцієнт завантаження 90 %» у паспорті
  ForecastModel_X · accuracy     «LSTM №2 (точність 78 %)», «моделі LSTM: №1 (точність 92 %), №2 (78 %)»
  Louvain · communities          «Louvain знайшов 12 спільнот», «Знайдено 10 спільнот»
  Louvain · modularity           «модулярність 0,6204» (порівняння з точністю 3 знаки)
  Louvain · weather_communities  «Ще 4 спільноти групують вимірювання», «5 – часові кластери»
  ForecastModel_GRU1 · pagerank  «GRU1 3.2789», рядок таблиці «ForecastModel_GRU1; …; 14; 3.3032» (2 знаки)
Еталон із графа: load_pct = currentLoad / nominalCapacity · 100, accuracy — властивість моделі.
"""
import re
from collections import defaultdict

from common import load_graph, sections

SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[А-ЯҐЄІЇA-Z«(])|\n+")
NUM = r"(\d+(?:[.,]\d+)?)"
WORDS = {"чотири": 4, "п'ять": 5, "п’ять": 5, "шість": 6, "три": 3}
PRECISION = {"load_pct": 1, "accuracy": 1, "communities": 0, "weather_communities": 0, "modularity": 3, "pagerank": 2}
FAMILY = r"(LSTM|GRU|VAR|ARIMA)"


def num(x):
    x = WORDS.get(x.lower(), x) if isinstance(x, str) else x
    return float(str(x).replace(",", "."))


def graph_values():
    nodes, _ = load_graph()
    ref = {}
    for s in nodes["substation"]:
        ref[(s["id"], "load_pct")] = round(float(s["currentLoad"]) / float(s["nominalCapacity"]) * 100, 1)
    for m in nodes["forecastmodel"]:
        ref[(m["id"], "accuracy")] = float(m["accuracy"])
    return ref


def _sentence_facts(sent, section_title):
    out = []
    low = sent.lower()
    if re.search(r"перевантаж|завантаж", low):
        for m in re.finditer(r"№\s?(\d{1,2})\s?\(" + NUM + r"\s?%", sent):
            out.append((f"Substation_{m.group(1)}", "load_pct", num(m.group(2))))
        m = re.search(r"коефіцієнт завантаження " + NUM + r"\s?%", sent)
        t = re.match(r"Підстанція №(\d+)", section_title or "")
        if m and t:
            out.append((f"Substation_{t.group(1)}", "load_pct", num(m.group(1))))
    if "точн" in low or re.search(FAMILY + r":\s*№", sent):
        fam = None
        for m in re.finditer(FAMILY + r"|№\s?(\d)\s?\((?:точність\s)?" + NUM + r"\s?%", sent):
            if m.group(1):
                fam = m.group(1)
            elif fam:
                out.append((f"ForecastModel_{fam}{m.group(2)}", "accuracy", num(m.group(3))))
        for m in re.finditer(FAMILY + r" №\s?(\d)\s?\(точність\s" + NUM + r"\s?%", sent):
            out.append((f"ForecastModel_{m.group(1)}{m.group(2)}", "accuracy", num(m.group(3))))
    for m in re.finditer(r"(?:Louvain[^.\n]{0,40}?|Знайдено |\()(\d+) спільнот", sent):
        if "групують" not in sent[m.end():m.end() + 30]:
            out.append(("Louvain", "communities", num(m.group(1))))
    for m in re.finditer(r"модулярн\w*\s*(?:—\s*|=\s*)?(0[.,]\d{3,4})", sent):
        out.append(("Louvain", "modularity", num(m.group(1))))
    for m in re.finditer(r"(?:Ще\s)?(\d+|[Чч]отири|[Пп][’']ять) спільнот\w* групують вимірювання|(\d+) [–—-] часов\w* кластер", sent):
        out.append(("Louvain", "weather_communities", num(m.group(1) or m.group(2))))
    for m in re.finditer(r"GRU1 (\d\.\d{3,4})|ForecastModel_GRU1;[^;\n]*;[^;\n]*;\s*\d+;\s*(\d\.\d{4})", sent):
        out.append(("ForecastModel_GRU1", "pagerank", num(m.group(1) or m.group(2))))
    return out


def extract(docs):
    """Усі згадки величин: список dict(key, prop, value, doc, section, sentence)."""
    facts = []
    for d, i, title, text in sections(docs):
        for sent in SENT_RE.split(text):
            for key, prop, val in _sentence_facts(sent, title):
                facts.append({"key": key, "prop": prop, "value": round(val, PRECISION[prop]), "doc": d,
                              "section": title, "sentence": sent.strip()})
    return facts


def consistency(docs):
    """Частка величин з одним значенням, що збігається з графом (якщо в графі воно є); список суперечностей."""
    ref = graph_values()
    by = defaultdict(list)
    for f in extract(docs):
        by[(f["key"], f["prop"])].append(f)
    rows, conflicts = [], []
    for q, fs in sorted(by.items()):
        vals = sorted({f["value"] for f in fs})
        g = ref.get(q)
        ok = len(vals) == 1 and (g is None or abs(vals[0] - g) <= 10 ** -PRECISION[q[1]] + 1e-9)
        rows.append({"quantity": f"{q[0]}.{q[1]}", "values": vals, "graph": g, "mentions": len(fs), "consistent": ok})
        if not ok:
            conflicts.append({"quantity": f"{q[0]}.{q[1]}", "graph": g,
                              "variants": [{"value": v, "docs": sorted({f["doc"]["doc_id"] for f in fs if f["value"] == v}),
                                            "examples": [(f["doc"], f["section"], f["sentence"]) for f in fs if f["value"] == v][:2]}
                                           for v in vals]})
    share = sum(r["consistent"] for r in rows) / len(rows) if rows else None
    return share, rows, conflicts
