"""Р4. Автоматичні перевірки якості сховища: 26 правил, 4 типи інструментів.

  SHACL (pySHACL)   SH-LR8, SH1–SH10   — форми ЛР8 + quality/shapes.ttl на RDF-трійках
  SPARQL (rdflib)   SP1–SP5            — інваріанти графа (цикли, диспетчер, дати навчання, прогнози, класи)
  Python/pytest     PY1–PY7            — ключі, посилальна цілісність, provenance, суперечності, витік restricted,
                                         актуальність статусів, реєстр сутностей ER
  JSON Schema       JS1–JS3            — корпус, реєстр суперечностей, реєстр сутностей
Кожна перевірка повертає список порушень (рядки). Порушення, описані у quality/waivers.json (відомі, з власником
і терміном), не блокують CI, але показуються у звіті.
"""
import csv
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

from common import DATA, EX, LAB, OUT, QUALITY, load_corpus, load_graph, load_triples, read_jsonl, sections, to_rdf

SCHEMAS = QUALITY / "schemas"


class Ctx:
    """Що перевіряємо: каталог сховища (store), корпус, реєстр сутностей; ледачі кеші RDF і SHACL."""

    def __init__(self, store, corpus, entities=OUT / "entities_resolved.json", ref_date=None):
        self.store, self.corpus, self.entities = Path(store), Path(corpus), Path(entities)
        self.ref = date.fromisoformat(ref_date) if ref_date else date.today()
        self._rdf = self._shacl = None

    @property
    def rdf(self):
        if self._rdf is None:
            self._rdf = to_rdf(load_triples(self.store), store=self.store)
        return self._rdf

    def shacl(self):
        if self._shacl is None:
            from pyshacl import validate
            from rdflib import Graph, Namespace
            sh = Graph().parse(self.store / "ontology" / "lab08_shapes.ttl")
            sh.parse(QUALITY / "shapes.ttl")
            _, rg, _ = validate(self.rdf, shacl_graph=sh, inference="rdfs")
            SH = Namespace("http://www.w3.org/ns/shacl#")
            res = []
            for r in rg.subjects(None, SH.ValidationResult):
                msg = str(rg.value(r, SH.resultMessage))
                m = re.match(r"(SH\d+):", msg)
                res.append((m.group(1) if m else "SH-LR8", f"{str(rg.value(r, SH.focusNode)).split('#')[-1]}: {msg}"))
            self._shacl = res
        return self._shacl


# SHACL
def shacl_check(cid):
    def f(c):
        return [v for k, v in c.shacl() if k == cid]
    return f


# SPARQL
P = f"PREFIX : <{EX}>\n"


def sp1_no_cycles(c):
    q = P + "SELECT DISTINCT ?s WHERE { ?s :upstreamOf+ ?s }"
    return [f"{str(r.s).split('#')[-1]}: цикл у ланцюгу живлення upstreamOf" for r in c.rdf.query(q)]


def sp2_dispatcher(c):
    q = P + "SELECT ?s WHERE { ?s a :Substation . FILTER NOT EXISTS { ?s :managedByDispatcher ?d } }"
    return [f"{str(r.s).split('#')[-1]}: немає відповідального диспетчера" for r in c.rdf.query(q)]


def sp3_training_date(c):
    q = P + """SELECT ?m ?td (MAX(?ts) AS ?last) WHERE { ?m :trainingDate ?td ; :trainedOnMeasurement ?x . ?x :timestamp ?ts . }
               GROUP BY ?m ?td"""
    return [f"{str(r.m).split('#')[-1]}: trainingDate {str(r.td)[:10]} раніша за навчальне вимірювання {str(r.last)[:10]}"
            for r in c.rdf.query(q) if str(r.td)[:10] < str(r.last)[:10]]


def sp4_forecast_links(c):
    q = P + """SELECT ?f WHERE { ?f a :Forecast .
               FILTER (NOT EXISTS { ?f :generatedByModel ?m } || NOT EXISTS { ?f :forecastForSubstation ?s }) }"""
    return [f"{str(r.f).split('#')[-1]}: прогноз без моделі або підстанції" for r in c.rdf.query(q)]


def sp5_disjoint_consumers(c):
    q = P + """SELECT ?s ?a ?b WHERE { ?a <http://www.w3.org/2002/07/owl#disjointWith> ?b . ?s a ?a , ?b . }"""
    return [f"{str(r.s).split('#')[-1]}: одночасно {str(r.a).split('#')[-1]} і {str(r.b).split('#')[-1]}" for r in c.rdf.query(q)]


# ---------- Python / pytest ----------
def py1_unique_ids(c):
    nodes, _ = load_graph(c.store)
    cnt = Counter(n["id"] for rows in nodes.values() for n in rows)
    return [f"{k}: id повторюється {v} рази" for k, v in cnt.items() if v > 1]


def py2_referential(c):
    nodes, rels = load_graph(c.store)
    ids = {n["id"] for rows in nodes.values() for n in rows}
    return [f"{t}: {r['start']} → {r['end']} — немає вузла" for t, rows in rels.items() for r in rows
            if r["start"] not in ids or r["end"] not in ids]


def py3_rel_provenance(c):
    _, rels = load_graph(c.store)
    out = []
    for t, rows in rels.items():
        for r in rows:
            miss = [k for k in ("source", "confidence", "validFrom") if not r.get(k)]
            if miss:
                out.append(f"{t}: {r['start']} → {r['end']} — немає {', '.join(miss)}")
            elif not (0 <= float(r["confidence"]) <= 1) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["validFrom"]):
                out.append(f"{t}: {r['start']} → {r['end']} — confidence поза [0,1] або validFrom не ISO-дата")
    return out


def py4_value_conflicts(c):
    from conflicts import unresolved_value_conflicts
    _, conflicts, _, unresolved = unresolved_value_conflicts(load_corpus(c.corpus))
    by = {x["quantity"]: x for x in conflicts}
    return [f"{q}: значення {', '.join(str(v['value']) for v in by[q]['variants'])} без рішення в реєстрі" for q in unresolved]


def py5_restricted_leak(c):
    """Тексти restricted-документів і адреси не потрапляють у файли якості, що йдуть у git (md, csv, json звітів)."""
    from common import ADDRESS_RE
    sents = set()
    for d in load_corpus(DATA / "corpus" / "docs.jsonl"):
        if d["sensitivity"] == "restricted":
            for s in d["sections"]:
                sents |= {x.strip() for x in re.split(r"(?<=[.!?])\s+", s["text"]) if len(x.strip()) >= 40}
    files = [p for p in QUALITY.glob("*.md")] + [p for p in QUALITY.glob("*.csv")] + list((QUALITY / "reports").glob("*.md"))
    out = []
    for p in files:
        t = p.read_text(encoding="utf-8-sig")
        hits = [s for s in sents if s in t]
        if hits:
            out.append(f"{p.name}: {len(hits)} речень із restricted-документів")
        if ADDRESS_RE.search(t):
            out.append(f"{p.name}: схоже на адресу споживача")
    return out


def py6_model_status(c):
    nodes, _ = load_graph(c.store)
    out = []
    for m in nodes["forecastmodel"]:
        stale = (c.ref - date.fromisoformat(m["trainingDate"])).days > 365
        st = m.get("status")
        if not st:
            out.append(f"{m['id']}: немає статусу експлуатації")
        elif stale and st == "в експлуатації":
            out.append(f"{m['id']}: статус «в експлуатації», хоча від навчання минуло > 12 міс. (kb08)")
    return out


def py7_entity_registry(c):
    if not c.entities.exists():
        return [f"{c.entities.name}: немає реєстру сутностей (python quality/dedup.py merge)"]
    reg = json.loads(c.entities.read_text(encoding="utf-8"))
    out, seen = [], Counter()
    for e in reg["entities"]:
        g = [m for m in e["members"] if m["source"] == "graph"]
        if len(g) > 1:
            out.append(f"{e['entity_id']}: злито {len(g)} вузли графа")
        for m in g:
            seen[m["rid"]] += 1
        codes = {tuple(sorted(set(re.findall(r"\b(LSTM|GRU|VAR|ARIMA)\b", m["name"])))) for m in e["members"]} - {()}
        if len(codes) > 1:
            out.append(f"{e['entity_id']}: різні коди моделей в одній сутності {sorted(codes)}")
    out += [f"{k}: вузол графа в {v} сутностях" for k, v in seen.items() if v > 1]
    return out

def js_check(schema_file, data_fn):
    def f(c):
        import jsonschema
        schema = json.loads((SCHEMAS / schema_file).read_text(encoding="utf-8"))
        v = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
        out = []
        for name, obj in data_fn(c):
            out += [f"{name}: {'/'.join(map(str, e.absolute_path)) or '(корінь)'} — {e.message[:120]}" for e in v.iter_errors(obj)]
        return out
    return f


def _docs(c):
    return [(d["doc_id"], d) for d in load_corpus(c.corpus)]


def _registry(c):
    return [("conflicts_registry", json.loads((QUALITY / "conflicts_registry.json").read_text(encoding="utf-8")))]


def _entities(c):
    return [("entities_resolved", json.loads(c.entities.read_text(encoding="utf-8")))] if c.entities.exists() else []


SHACL_TITLES = {"SH-LR8": "форми ЛР8 (лічильник, категорія, потужність, регіон, модель прогнозу…)",
                "SH1": "навантаження ≤ номінальна потужність", "SH2": "канонічні назви областей",
                "SH3": "інтервал зчитування 15/30/60", "SH4": "статус лічильника з довідника",
                "SH5": "точність моделі 0–100 %", "SH6": "одна дата навчання xsd:date", "SH7": "тип моделі з довідника",
                "SH8": "одна мітка часу вимірювання", "SH9": "споживання ≥ 0", "SH10": "вимірювання — рівно один лічильник"}

CHECKS = [(k, "SHACL", v, shacl_check(k)) for k, v in SHACL_TITLES.items()] + [
    ("SP1", "SPARQL", "немає циклів у ланцюгу живлення", sp1_no_cycles),
    ("SP2", "SPARQL", "кожна підстанція має диспетчера", sp2_dispatcher),
    ("SP3", "SPARQL", "дата навчання не раніша за навчальні дані", sp3_training_date),
    ("SP4", "SPARQL", "прогноз має модель і підстанцію", sp4_forecast_links),
    ("SP5", "SPARQL", "немає індивідів у несумісних класах", sp5_disjoint_consumers),
    ("PY1", "pytest", "унікальні id вузлів", py1_unique_ids),
    ("PY2", "pytest", "посилальна цілісність зв'язків", py2_referential),
    ("PY3", "pytest", "provenance зв'язків (source, confidence, validFrom)", py3_rel_provenance),
    ("PY4", "pytest", "немає нерозв'язаних суперечностей значень у корпусі", py4_value_conflicts),
    ("PY5", "pytest", "restricted-тексти й адреси не у файлах якості", py5_restricted_leak),
    ("PY6", "pytest", "статус моделі відповідає правилу kb08", py6_model_status),
    ("PY7", "pytest", "реєстр сутностей ER без хибних злиттів", py7_entity_registry),
    ("JS1", "JSON Schema", "схема документів корпусу", js_check("doc.schema.json", _docs)),
    ("JS2", "JSON Schema", "схема реєстру суперечностей", js_check("conflicts.schema.json", _registry)),
    ("JS3", "JSON Schema", "схема реєстру сутностей", js_check("entities.schema.json", _entities)),
]


def load_waivers():
    p = QUALITY / "waivers.json"
    return json.loads(p.read_text(encoding="utf-8"))["waivers"] if p.exists() else []


def run_all(ctx):
    waivers = load_waivers()
    res = []
    for cid, tool, title, fn in CHECKS:
        try:
            viol = fn(ctx)
            err = None
        except Exception as e:                       # помилка самої перевірки теж блокує
            viol, err = [f"помилка перевірки: {type(e).__name__}: {e}"], True
        waived = [v for v in viol if any(w["check"] == cid and w["match"] in v and (not w.get("until") or w["until"] >= ctx.ref.isoformat())
                                         for w in waivers)]
        blocking = [v for v in viol if v not in waived]
        res.append({"id": cid, "tool": tool, "title": title, "violations": len(viol), "waived": len(waived),
                    "blocking": len(blocking), "status": "FAIL" if blocking else ("WAIVED" if waived else "PASS"),
                    "details": viol, "error": err})
    return res
