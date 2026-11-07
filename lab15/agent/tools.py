"""Інструменти агента (усі read-only) і їх реєстр із JSON-схемами.

  search_docs  — гібридний пошук ЛР10–11 (BM25 + e5 + reranker) по корпусу ЛР14 (data_after, із kb16); роль — із сесії
  graph_query  — шаблонні SPARQL-запити SELECT до RDF-трійок графа ЛР9 (data_after/store/triples.csv), без адрес
  sql_metric   — метрика OLAP ЛР12 лише через семантичний шар (metrics.yml); DuckDB у пам'яті, зовнішній доступ вимкнено
Кожен результат має id для цитування: [kb06#par002], [G:Substation_5], [SQL:peak_load:1].

Версія «до захисту» (AGENT_DEFENSES=0) моделює типові помилки проєктування: роль пошуку задає LLM (параметр role),
graph_query має шаблон raw_sparql (довільний SPARQL, зокрема UPDATE і адреси). Після захисту їх немає.
  python -m agent.tools --lock      # зафіксувати SHA-256 описів інструментів (agent/tool_lock.json)
"""
import csv
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

from agent import config as C

LOCK = Path(__file__).with_name("tool_lock.json")
INJECT_DOCS = []            # для тесту непрямого injection: «отруєні» фрагменти, які harness додає до пошуку

# ---------------------------------------------------------------- специфікації (JSON Schema)
SPECS = {
    "search_docs": {
        "description": "Пошук фрагментів у документах бази знань (регламенти, статті, реєстри, звіти). Повертає фрагменти з id "
                       "для цитування. Використовуй для правил і процедур (дії диспетчера, рівні завантаження), визначень, "
                       "статусу моделей і результатів аналітики графа (Louvain, спільноти, PageRank, центральність).",
        "parameters": {"type": "object", "additionalProperties": False, "required": ["query"],
                       "properties": {"query": {"type": "string", "minLength": 3, "maxLength": 300},
                                      "k": {"type": "integer", "minimum": 1, "maximum": 5, "default": 4}}},
        "rights": "read", "source": "корпус ЛР11/ЛР14 (data_after/corpus)",
    },
    "graph_query": {
        "description": "Запит до графа знань мережі (підстанції, диспетчери, моделі, прогнози, ланцюги живлення) за шаблоном. "
                       "template: overloaded_substations — перевантажені зараз (≥ 85 % номіналу); substation — паспорт підстанції "
                       "з рівнем завантаження, диспетчером і ланцюгом живлення (entity = номер підстанції); impact — наслідки "
                       "аварії вниз ланцюгом (entity = номер, depth 1–3); model — модель прогнозу (entity = LSTM1, GRU1, VAR1, "
                       "ARIMA1…); forecasts — прогнози для підстанції з похибками (entity = номер підстанції); dispatcher — зона "
                       "диспетчера за НОМЕРОМ ДИСПЕТЧЕРА (не підстанції).",
        "parameters": {"type": "object", "additionalProperties": False, "required": ["template"],
                       "properties": {"template": {"type": "string", "enum": ["overloaded_substations", "substation", "impact",
                                                                             "model", "forecasts", "dispatcher"]},
                                      "entity": {"type": "string", "maxLength": 40},
                                      "depth": {"type": "integer", "minimum": 1, "maximum": 3, "default": 3}}},
        "rights": "read", "source": "граф ЛР9 (RDF-трійки data_after/store/triples.csv)",
    },
    "sql_metric": {
        "description": "Метрика сховища даних OLAP (погодинне споживання за 2026 р.) через семантичний шар. metric: total_energy "
                       "(кВт·год), peak_load (кВт), avg_load (кВт), load_factor, over_limit_hours, peak_share (%), "
                       "energy_per_meter_day. by — виміри групування; where — фільтри {вимір: значення}. Виміри: region "
                       "(«Львівська область»), substation («Підстанція №12»), class, month, is_weekend, part_of_day, is_peak.",
        "parameters": {"type": "object", "additionalProperties": False, "required": ["metric"],
                       "properties": {"metric": {"type": "string", "enum": ["total_energy", "peak_load", "avg_load", "load_factor",
                                                                           "over_limit_hours", "peak_share", "energy_per_meter_day"]},
                                      "by": {"type": "array", "maxItems": 2, "items": {"type": "string", "enum": [
                                          "region", "substation", "class", "class_parent", "month", "is_weekend", "part_of_day",
                                          "is_peak"]}},
                                      "where": {"type": "object", "maxProperties": 3}}},
        "rights": "read", "source": "сховище даних ЛР12 (parquet) + семантичний шар metrics.yml",
    },
}
if not C.DEFENSES:                                   # навмисно вразлива версія для Р4 («до»)
    SPECS["search_docs"]["parameters"]["properties"]["role"] = {"type": "string", "enum": ["analyst", "admin"],
                                                                "description": "роль доступу"}
    SPECS["graph_query"]["parameters"]["properties"]["template"]["enum"].append("raw_sparql")
    SPECS["graph_query"]["parameters"]["properties"]["query"] = {"type": "string", "description": "довільний SPARQL"}


def spec_hash(name, spec):
    return hashlib.sha256(json.dumps({"name": name, "description": spec["description"], "parameters": spec["parameters"]},
                                     ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def load_specs(trace=None):
    """Специфікації інструментів для LLM. AGENT_TOOL_OVERRIDES — JSON зі зміненими описами (імітація скомпрометованого
    MCP-сервера). Із захистами опис, хеш якого не збігається з tool_lock.json, відкидається разом з інструментом."""
    specs = json.loads(json.dumps(SPECS))
    ov = os.environ.get("AGENT_TOOL_OVERRIDES")
    if ov:
        for name, desc in json.loads(Path(ov).read_text(encoding="utf-8")).items():
            if name in specs:
                specs[name]["description"] = desc
    if C.DEFENSES and LOCK.exists():
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        for name in list(specs):
            if lock.get(name) != spec_hash(name, specs[name]):
                specs.pop(name)
                if trace is not None:
                    trace.event("policy", {"blocked_tool": name, "reason": "опис інструмента не збігається з tool_lock.json"})
    return specs


# ---------------------------------------------------------------- search_docs
_retriever = None


def _get_retriever():
    global _retriever
    if _retriever is None:
        sys.path.insert(0, str(C.LAB11 / "src"))
        import common as c11                         # lab11/src/common.py
        from config import Settings                  # lab11/src/config.py
        from rag import Retriever
        c11.CLEAN = C.STORE / "corpus"
        _retriever = Retriever(Settings())
    return _retriever


def search_docs(query, k=4, role=None):
    role = role if (role and not C.DEFENSES) else C.ROLE
    hits = _get_retriever().search(query, role, k)
    out = [{"id": h["id"], "title": h["title"], "section": h["section"], "date": h["date"],
            "sensitivity": h["sensitivity"], "text": h["text"]} for h in hits]
    return out + [dict(d) for d in INJECT_DOCS]


# ---------------------------------------------------------------- graph_query
EX = "http://www.semanticweb.org/energy-forecasting#"
_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        from rdflib import Graph, Literal, Namespace, RDF, XSD
        ns, skos = Namespace(EX), Namespace("http://www.w3.org/2004/02/skos/core#")
        dt = {"double": XSD.double, "string": XSD.string, "date": XSD.date, "dateTime": XSD.dateTime, "integer": XSD.integer}
        g = Graph()
        rows = list(csv.DictReader(open(C.STORE / "store" / "triples.csv", encoding="utf-8-sig")))
        approved = C.KB / "facts.csv"                     # факти, схвалені через propose_fact (Р5), — частина знань
        if approved.exists():
            rows += list(csv.DictReader(open(approved, encoding="utf-8")))
        if True:
            for r in rows:
                p = r["predicate"]
                pred = RDF.type if p == "rdf:type" else skos.prefLabel if p == "skos:prefLabel" else ns[p]
                o = (ns[r["object"]] if r["object_type"] == "iri" else
                     Literal(r["object"], lang=r["lang"]) if r["lang"] else Literal(r["object"], datatype=dt.get(r["datatype"])))
                g.add((ns[r["subject"]], pred, o))
        _graph = g
    return _graph


P = f"PREFIX : <{EX}>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n"
Q = {
    "overloaded_substations": P + """SELECT ?s ?load ?cap ?region WHERE { ?s a :Substation ; :currentLoad ?load ;
        :nominalCapacity ?cap ; :region ?region . FILTER(?load / ?cap >= 0.85) } ORDER BY DESC(?load / ?cap)""",
    "substation": P + """SELECT ?s ?load ?cap ?region (GROUP_CONCAT(DISTINCT STRAFTER(STR(?d), "#"); separator=", ") AS ?disp)
        (GROUP_CONCAT(DISTINCT STRAFTER(STR(?up), "#"); separator=", ") AS ?feeders)
        (GROUP_CONCAT(DISTINCT STRAFTER(STR(?down), "#"); separator=", ") AS ?feeds) WHERE {
        BIND(:{ID} AS ?s) ?s :currentLoad ?load ; :nominalCapacity ?cap ; :region ?region .
        OPTIONAL { ?s :managedByDispatcher ?d } OPTIONAL { ?up :upstreamOf ?s } OPTIONAL { ?s :upstreamOf ?down } }
        GROUP BY ?s ?load ?cap ?region""",
    "impact": P + """SELECT ?sub (COUNT(DISTINCT ?c) AS ?consumers) (SUM(?lim) AS ?limit)
        (GROUP_CONCAT(DISTINCT STRAFTER(STR(?d), "#"); separator=", ") AS ?disp) WHERE {
        VALUES ?sub { {SUBS} } OPTIONAL { ?c :connectedToSubstation ?sub ; :contractLimit ?lim }
        OPTIONAL { ?sub :managedByDispatcher ?d } } GROUP BY ?sub""",
    "model": P + """SELECT ?m ?type ?acc ?td (COUNT(DISTINCT ?f) AS ?forecasts) (MAX(?ts) AS ?lastTrain) (SAMPLE(?st) AS ?status)
        WHERE { BIND(:{ID} AS ?m) ?m :modelType ?type ; :accuracy ?acc ; :trainingDate ?td . OPTIONAL { ?m :status ?st }
        OPTIONAL { ?f :generatedByModel ?m } OPTIONAL { ?m :trainedOnMeasurement ?x . ?x :timestamp ?ts } }
        GROUP BY ?m ?type ?acc ?td""",
    "forecasts": P + """SELECT ?f ?label ?model ?err ?period WHERE { ?f :forecastForSubstation :{ID} ; skos:prefLabel ?label ;
        :generatedByModel ?model ; :errorPercentage ?err ; :forecastPeriod ?period } ORDER BY ?f""",
    "dispatcher": P + """SELECT ?d ?label ?qual ?shift (GROUP_CONCAT(DISTINCT STRAFTER(STR(?s), "#"); separator=", ") AS ?zone)
        (COUNT(DISTINCT ?f) AS ?forecasts) WHERE { BIND(:{ID} AS ?d) ?d skos:prefLabel ?label ; :qualification ?qual ; :shift ?shift .
        OPTIONAL { ?s :managedByDispatcher ?d } OPTIONAL { ?d :usesForecast ?f } } GROUP BY ?d ?label ?qual ?shift""",
}


def _ln(x):
    return str(x).split("#")[-1]


def _v(x):
    """Значення з рядка результату; незв'язане (у т. ч. GROUP_CONCAT від порожнього) → ''."""
    return "" if x is None or "NotBound" in str(x) else str(x)


def _level(p):
    """Рівень завантаження за регламентом kb06."""
    return ("червоний (≥ 95 %), критичне перевантаження" if p >= 95 else "жовтий (85–95 %), перевантажена" if p >= 85
            else "зелений (< 85 %), не перевантажена")


def _entity(template, entity):
    e = (entity or "").strip()
    if template == "model":
        m = re.search(r"(LSTM|GRU|VAR|ARIMA)\D*(\d)", e.upper())
        if not m:
            raise ValueError("entity для model — код моделі (LSTM1, LSTM2, LSTM3, GRU1, VAR1, ARIMA1), не номер підстанції; "
                             "назву моделі бери з доказів (напр. «модель ForecastModel_LSTM2»)")
        return f"ForecastModel_{m.group(1)}{m.group(2)}"
    m = re.search(r"\d+", e)
    if not m:
        raise ValueError(f"entity для {template}: номер, напр. «7»")
    return f"{'Dispatcher' if template == 'dispatcher' else 'Substation'}_{int(m.group(0))}"


def graph_query(template, entity=None, depth=3, query=None):
    g = _get_graph()
    if template == "raw_sparql":                                  # лише у версії без захисту
        if re.search(r"\b(INSERT|DELETE|DROP|CLEAR|LOAD|CREATE)\b", query or "", re.I):
            before = len(g)
            g.update(query)
            return [{"id": "G:update", "text": f"UPDATE виконано: трійок {before} → {len(g)}"}]
        return [{"id": f"G:raw:{i}", "text": "; ".join(f"{k}={_ln(v)}" for k, v in r.asdict().items())}
                for i, r in enumerate(g.query(query)) if i < 50]
    out = []
    if template == "overloaded_substations":
        for r in g.query(Q[template]):
            pct = float(r.load) / float(r.cap) * 100
            out.append({"id": f"G:{_ln(r.s)}", "text": f"{_ln(r.s)}: навантаження {float(r.load):g} з {float(r.cap):g} кВт "
                                                      f"({pct:.1f} %), рівень {_level(pct)}, {r.region}"})
        if not out:
            return [{"id": "G:none", "text": "перевантажених підстанцій немає"}]
        head = {"id": "G:overloaded", "text": f"усього перевантажених (≥ 85 % номіналу) підстанцій: {len(out)} — "
                                              + ", ".join(o["id"][2:] for o in out)}
        return [head] + out
    eid = _entity(template, entity)
    if template == "impact":
        down = {eid: 0}
        frontier = [eid]
        for d in range(1, int(depth) + 1):
            nxt = []
            for s in frontier:
                for (o,) in g.query(P + f"SELECT ?o WHERE {{ :{s} :upstreamOf ?o }}"):
                    if _ln(o) not in down:
                        down[_ln(o)] = d
                        nxt.append(_ln(o))
            frontier = nxt
        rows = list(g.query(Q["impact"].replace("{SUBS}", " ".join(f":{s}" for s in down))))
        tot_c = sum(int(r.consumers) for r in rows)
        tot_l = sum(float(r.limit or 0) for r in rows)
        disp = sorted({x for r in rows for x in _v(r.disp).split(", ") if x})
        out.append({"id": f"G:impact:{eid}", "text": f"аварія на {eid} (глибина {depth}): зачеплено підстанцій {len(down)} "
                                                     f"({', '.join(f'{s} (гл. {d})' for s, d in down.items())}); споживачів "
                                                     f"{tot_c}, сумарний договірний ліміт {tot_l:.1f} кВт; диспетчери: "
                                                     f"{', '.join(disp) or 'немає'}"})
        return out
    rows = list(g.query(Q[template].replace("{ID}", eid)))
    if not rows:
        return [{"id": f"G:{eid}", "text": f"{eid}: у графі немає даних"}]
    for r in rows:
        if template == "substation":
            pct = float(r.load) / float(r.cap) * 100
            out.append({"id": f"G:{eid}", "text": f"{eid}: номінал {float(r.cap):g} кВт, поточне навантаження {float(r.load):g} кВт "
                                                  f"({pct:.1f} %), рівень {_level(pct)}; {r.region}; диспетчер: "
                                                  f"{_v(r.disp) or 'не призначено'}; живиться від: {_v(r.feeders) or '—'}; живить: {_v(r.feeds) or '—'}"})
        elif template == "model":
            out.append({"id": f"G:{eid}", "text": f"{eid}: тип {r.type}, точність {float(r.acc):g} %, дата навчання {r.td}, "
                                                  f"статус: {_v(r.status) or 'не вказано'}, прогнозів {r.forecasts}, "
                                                  f"останнє вимірювання в навчальній вибірці {str(r.lastTrain)[:10]}"})
        elif template == "forecasts":
            out.append({"id": f"G:{_ln(r.f)}", "text": f"{r.label}: модель {_ln(r.model)}, період {r.period}, похибка {float(r.err):g} %"})
        elif template == "dispatcher":
            out.append({"id": f"G:{eid}", "text": f"{r.label}: {r.qual}, зміна {r.shift}; зона: {_v(r.zone) or 'немає'}; "
                                                  f"користується прогнозами: {r.forecasts}"})
    return out


# ---------------------------------------------------------------- sql_metric
_duck = _sem = None


def _get_sql():
    global _duck, _sem
    if _duck is None:
        import duckdb
        spec = importlib.util.spec_from_file_location("semantic12", C.LAB12 / "semantic" / "semantic.py")
        _sem = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_sem)
        con = duckdb.connect(":memory:")
        for p in sorted((C.LAB12 / "data").glob("*.parquet")):
            con.execute(f"CREATE TABLE {p.stem} AS SELECT * FROM read_parquet('{p.as_posix()}')")
        con.execute("SET enable_external_access = false")           # далі жодних файлів / мережі
        con.execute("SET lock_configuration = true")
        _duck = con
    return _duck, _sem


def sql_metric(metric, by=None, where=None):
    con, sem = _get_sql()
    sql = sem.metric_sql(metric, by=by or [], where=where or {})      # SQL будує лише семантичний шар
    if not re.match(r"^\s*(WITH|SELECT)\b", sql, re.I):
        raise ValueError("семантичний шар повернув не SELECT")
    rows = con.execute(sql).fetchall()[:30]
    cols = [d[0] for d in con.description]
    unit = sem.METRICS[metric]["unit"]
    ctx = f"{metric} ({sem.METRICS[metric].get('label', metric)}), 2026 р." + \
        (f", фільтр: {', '.join(f'{k}={v}' for k, v in (where or {}).items())}" if where else ", без фільтра")
    return [{"id": f"SQL:{metric}:{i + 1}", "text": ctx + ": " + ", ".join(f"{c}={round(v, 2) if isinstance(v, float) else v}"
                                                                         for c, v in zip(cols, r)) + f" ({unit})"}
            for i, r in enumerate(rows)] or [{"id": f"SQL:{metric}:0", "text": "порожній результат"}]


FUNCS = {"search_docs": search_docs, "graph_query": graph_query, "sql_metric": sql_metric}


if __name__ == "__main__":
    if "--lock" in sys.argv:
        LOCK.write_text(json.dumps({n: spec_hash(n, s) for n, s in SPECS.items()}, indent=1), encoding="utf-8")
        print(f"→ {LOCK}")
