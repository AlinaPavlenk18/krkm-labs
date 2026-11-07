"""Каталог «фрагментів знань» (розділи документів корпусу ЛР14), їхні атрибути якості й граф для рекомендацій."""
import csv
import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

import networkx as nx

LAB = Path(__file__).resolve().parents[1]
REPO = LAB.parent
STORE = REPO / "lab14" / "data_after"
DATA = LAB / "data"
REF_DATE = date(2026, 11, 7)
MIN_WORDS = 15

SUB = re.compile(r"(?:підстанці\w*|ПС)\s*№\s*(\d{1,2})\b|Substation_(\d{1,2})\b", re.I)
MOD = re.compile(r"\b(LSTM|GRU|VAR|ARIMA)\s*(?:№\s*)?_?(\d)\b")
DISP = re.compile(r"диспетчер\w*\s*№\s*(\d{1,2})\b|Dispatcher_(\d{1,2})\b", re.I)
REGIONS = ["Львівськ", "Волинськ", "Рівненськ", "Тернопільськ", "Закарпатськ", "Івано-Франківськ"]
REGION_IRI = {"Львівськ": "Region_Lviv", "Волинськ": "Region_Volyn", "Рівненськ": "Region_Rivne",
              "Тернопільськ": "Region_Ternopil", "Закарпатськ": "Region_Zakarpattia", "Івано-Франківськ": "Region_IF"}
CONCEPTS = {  
    "перевантаж": "C:перевантаження", "рів(ень|ні|ня) завантаж": "C:рівні завантаження", "перерозпод": "C:перерозподіл",
    "прогноз": "C:прогноз", "похибк|MAPE|WAPE": "C:похибка прогнозу", "перенавч": "C:перенавчання",
    "погод|температур|хмарн": "C:погода", "лічильник|AMI": "C:лічильники", "несправн": "C:несправності",
    "якіст\\w* даних|пропуск": "C:якість даних", "онтолог": "C:онтологія", "граф знань|Neo4j|Cypher|SPARQL": "C:граф знань",
    "PageRank|центральн": "C:PageRank", "Louvain|спільнот": "C:спільноти", "доступ|конфіденц|restricted": "C:доступ",
    "ланцюг\\w* живлення|каскад": "C:ланцюг живлення", "договір|договір|ліміт": "C:договірний ліміт",
    "споживач": "C:споживачі", "архітектур|Hub": "C:архітектура", "суперечн": "C:суперечності",
}
CONCEPT_RE = {v: re.compile(k, re.I) for k, v in CONCEPTS.items()}
TYPE_FRESH_DAYS = {"forecast_log": 30, "register": 60, "model_card": 60}   


def entities_of(text):
    ents = set()
    for a, b in SUB.findall(text):
        ents.add(f"Substation_{int(a or b)}")
    for m, n in MOD.findall(text):
        ents.add(f"ForecastModel_{m.upper()}{n}")
    for a, b in DISP.findall(text):
        ents.add(f"Dispatcher_{int(a or b)}")
    for r in REGIONS:
        if r in text:
            ents.add(REGION_IRI[r])
    ents |= {c for c, rx in CONCEPT_RE.items() if rx.search(text)}
    return ents


def _unverified_sections():
    """(doc, назва розділу) з альтернативними (нечинними) значеннями за рішеннями ЛР14."""
    p = STORE / "store" / "alternatives.ttl"
    if not p.exists():
        return set()
    txt = p.read_text(encoding="utf-8")
    out = set()
    for blk in txt.split(" .\n"):
        if 'q:status "alternative"' in blk:
            d = re.search(r'q:sourceDoc "([^"]+)"', blk)
            s = re.search(r'q:sourceSection "([^"]+)"', blk)
            if d and s:
                out.add((d.group(1), s.group(1)))
    return out


@lru_cache(maxsize=1)
def load_items():
    unver = _unverified_sections()
    items = {}
    for line in open(STORE / "corpus" / "docs.jsonl", encoding="utf-8"):
        d = json.loads(line)
        for i, s in enumerate(d["sections"]):
            words = len(s["text"].split())
            if words < MIN_WORDS:
                continue
            iid = f"{d['doc_id']}#s{i:02d}"
            age = (REF_DATE - date.fromisoformat(d["date"])).days
            items[iid] = {"id": iid, "doc": d["doc_id"], "title": d["title"], "section": s["section"], "text": s["text"],
                          "type": d.get("type", ""), "date": d["date"], "sensitivity": d["sensitivity"],
                          "verified": (d["doc_id"], s["section"]) not in unver, "age_days": age,
                          "fresh": age <= TYPE_FRESH_DAYS.get(d.get("type", ""), 10_000),
                          "entities": sorted(entities_of(s["section"] + " " + s["text"])), "pos": i}
    return items


KG_PRED = {"upstreamOf": "живить", "managedByDispatcher": "у зоні", "region": "у регіоні"}


@lru_cache(maxsize=1)
def kg_edges():
    """Зв'язки між сутностями з графа ЛР9 (без персональних даних)."""
    rows = list(csv.DictReader(open(STORE / "store" / "triples.csv", encoding="utf-8-sig")))
    edges, f_sub, f_mod = [], {}, {}
    reg = {}
    for r in rows:
        p = r["predicate"]
        if p in ("upstreamOf", "managedByDispatcher"):
            edges.append((r["subject"], r["object"], KG_PRED[p]))
        elif p == "region" and r["subject"].startswith("Substation_"):
            reg[r["subject"]] = r["object"]
        elif p == "forecastForSubstation":
            f_sub[r["subject"]] = r["object"]
        elif p == "generatedByModel":
            f_mod[r["subject"]] = r["object"]
    for s, rname in reg.items():
        for stem, iri in REGION_IRI.items():
            if stem in rname:
                edges.append((s, iri, "у регіоні"))
    for f, s in f_sub.items():
        if f in f_mod:
            edges.append((s, f_mod[f], "прогнозується моделлю"))
    return sorted(set(edges))


@lru_cache(maxsize=1)
def build_graph():
    items = load_items()
    g = nx.Graph()
    for iid, it in items.items():
        g.add_node(iid, kind="item")
        for e in it["entities"]:
            g.add_node(e, kind="concept" if e.startswith("C:") else "entity")
            g.add_edge(iid, e, rel="згадує")
    for a, b, rel in kg_edges():
        if a in g and b in g:
            g.add_edge(a, b, rel=rel)
    by_doc = {}
    for iid, it in items.items():
        by_doc.setdefault(it["doc"], []).append(iid)
    for ids in by_doc.values():
        ids.sort(key=lambda x: items[x]["pos"])
        for a, b in zip(ids, ids[1:]):
            g.add_edge(a, b, rel="наступний розділ")
    return g


def label(node):
    if node.startswith("Substation_"):
        return f"підстанція №{node.split('_')[1]}"
    if node.startswith("Dispatcher_"):
        return f"диспетчер №{node.split('_')[1]}"
    if node.startswith("ForecastModel_"):
        m = re.match(r"ForecastModel_([A-Z]+)(\d)", node)
        return f"модель {m.group(1)} №{m.group(2)}" if m else node
    if node.startswith("Region_"):
        return {"Region_Lviv": "Львівська область", "Region_Volyn": "Волинська область", "Region_Rivne": "Рівненська область",
                "Region_Ternopil": "Тернопільська область", "Region_Zakarpattia": "Закарпатська область",
                "Region_IF": "Івано-Франківська область"}[node]
    if node.startswith("C:"):
        return f"«{node[2:]}»"
    it = load_items().get(node)
    return f"«{it['title']} › {it['section']}»" if it else node


def zone(dispatcher):
    """Підстанції зони диспетчера (для профілю нового користувача)."""
    return sorted(a for a, b, rel in kg_edges() if rel == "у зоні" and b == dispatcher)


if __name__ == "__main__":
    it = load_items()
    g = build_graph()
    print(f"елементів {len(it)}, документів {len({x['doc'] for x in it.values()})}, вузлів {g.number_of_nodes()}, "
          f"ребер {g.number_of_edges()}; restricted {sum(x['sensitivity'] == 'restricted' for x in it.values())}, "
          f"неперевірених {sum(not x['verified'] for x in it.values())}, без сутностей {sum(not x['entities'] for x in it.values())}")
    print("зона Dispatcher_1:", zone("Dispatcher_1"), "| ребер КГ:", len(kg_edges()))
