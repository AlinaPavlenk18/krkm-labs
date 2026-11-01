"""ЛР13 · Результат 5: гібрид витягу → нормалізація й entity linking → data/graph_load.cypher (Neo4j) з provenance."""
import csv, json, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
NS = "http://www.semanticweb.org/energy-forecasting#"

# зв'язування понять, яких немає серед вузлів графа ЛР9, з онтологією ЛР8 (рішення — docs/entity_linking.md)
CONCEPT_LINKS = {
    ("METHOD", "ARIMA"): (NS + "StatisticalModel", "broader"), ("METHOD", "SARIMA"): (NS + "StatisticalModel", "broader"),
    ("METHOD", "VAR"): (NS + "StatisticalModel", "broader"), ("METHOD", "LSTM"): (NS + "MachineLearningModel", "broader"),
    ("METHOD", "GRU"): (NS + "MachineLearningModel", "broader"),
    ("METRIC", "MAPE"): (NS + "errorPercentage", "closeMatch"),
    ("WEATHER_FACTOR", "TEMPERATURE"): (NS + "temperature", "exactMatch"),
    ("WEATHER_FACTOR", "CLOUD_COVER"): (NS + "cloudCover", "exactMatch"),
}
REL_IRI = {"FEEDS": "upstreamOf", "LOCATED_IN": "region", "MANAGES": "managesSubstation", "CONNECTED_TO": "connectedToSubstation",
           "HAS_METER": "hasMeter", "FORECASTS_FOR": "generatesForecast/forecastFor", "INSTANCE_OF": "rdf:type"}


def load(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")] if p.exists() else []


def lr9_nodes():
    out = {}
    for f in (ROOT / "data/source").glob("nodes_*.csv"):
        for r in csv.DictReader(open(f, encoding="utf-8")):
            out[r["id"]] = r.get("name", r["id"])
    return out


def q(s):
    return "'" + str(s).replace("\\", "\\\\").replace("'", "\\'") + "'"


def main():
    rules = load(ROOT / "results/rules_dev.jsonl") + load(ROOT / "results/rules_test.jsonl")
    llm = load(ROOT / "results/llm_dev.jsonl") + load(ROOT / "results/llm_test.jsonl")
    docs = {json.loads(l)["doc_id"]: json.loads(l) for l in open(ROOT / "data/docs.jsonl", encoding="utf-8")}
    key = lambda r: (r["doc_id"], r["type"], r["head"], r["tail"])
    R = {key(r): r for r in rules if r["kind"] == "relation"}
    L = {key(r): r for r in llm if r["kind"] == "relation"}
    stmts = []
    for r in rules:
        if r["kind"] == "entity":
            stmts.append({**r, "method": "rules"})
    for k in sorted(set(R) | set(L)):
        r = R.get(k) or L[k]
        both = k in R and k in L
        stmts.append({**r, "method": "rules+llm" if both else ("rules" if k in R else "llm"),
                      "model": f"{R[k]['model']} + {L[k]['model']}" if both else r["model"],
                      "prompt_version": (L.get(k) or {}).get("prompt_version"),
                      "confidence": 0.95 if both else (0.9 if k in R else 0.7)})
    with open(ROOT / "data/extracted.jsonl", "w", encoding="utf-8") as f:
        for s in stmts:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    # entity linking
    nodes = lr9_nodes()
    ents = {}
    for s in stmts:
        if s["kind"] == "entity":
            ents.setdefault((s["type"], s["canonical"]), s["text"])
        else:
            from src.schema import RELATION_TYPES
            ht, tt = RELATION_TYPES[s["type"]]
            ents.setdefault((ht, s["head"]), s["head"])
            ents.setdefault((tt, s["tail"]), s["tail"])
    linking = []
    for (t, c), surf in sorted(ents.items()):
        if c in nodes:
            linking.append((t, c, surf, "LR9", c, "sameAs", nodes[c]))
        elif (t, c) in CONCEPT_LINKS:
            iri, how = CONCEPT_LINKS[(t, c)]
            linking.append((t, c, surf, "LR8", iri, how, ""))
        else:
            linking.append((t, c, surf, "—", "", "новий вузол", ""))

    L_ = ["// ЛР13 · Знання, витягнуті з текстів, з provenance. Завантаження: python scripts/load_neo4j.py",
          "CREATE CONSTRAINT xentity_id IF NOT EXISTS FOR (e:XEntity) REQUIRE e.id IS UNIQUE;",
          "CREATE CONSTRAINT xdoc_id IF NOT EXISTS FOR (d:XDocument) REQUIRE d.id IS UNIQUE;"]
    for did, d in sorted(docs.items()):
        L_.append(f"MERGE (d:XDocument {{id: {q(did)}}}) SET d.title = {q(d['title'])}, d.type = {q(d['type'])}, "
                  f"d.sensitivity = {q(d['sensitivity'])}, d.source_url = {q(d['source_url'])};")
    for t, c, surf, src, target, how, name in linking:
        L_.append(f"MERGE (e:XEntity {{id: {q(c)}}}) SET e.type = {q(t)}, e.name = {q(name or c)}, e.linked = {q(src)}, "
                  f"e.link = {q(target)}, e.link_type = {q(how)};")
        if src == "LR9":
            L_.append(f"MATCH (e:XEntity {{id: {q(c)}}}), (n {{id: {q(c)}}}) WHERE NOT n:XEntity MERGE (e)-[:SAME_AS]->(n);")
    for s in stmts:
        if s["kind"] == "entity":
            L_.append(f"MATCH (d:XDocument {{id: {q(s['doc_id'])}}}), (e:XEntity {{id: {q(s['canonical'])}}}) "
                      f"MERGE (d)-[m:MENTIONS {{offset: {s['start']}}}]->(e) SET m.text = {q(s['text'])}, "
                      f"m.method = {q(s['method'])}, m.model = {q(s['model'])}, m.confidence = {s['confidence']};")
        else:
            L_.append(f"MATCH (h:XEntity {{id: {q(s['head'])}}}), (t:XEntity {{id: {q(s['tail'])}}}) "
                      f"MERGE (h)-[r:{s['type']} {{source: {q(s['doc_id'])}, offset: {s['start']}}}]->(t) "
                      f"SET r.evidence = {q(s['evidence'])}, r.method = {q(s['method'])}, r.model = {q(s['model'])}, "
                      f"r.prompt_version = {q(s.get('prompt_version') or '')}, r.confidence = {s['confidence']}, "
                      f"r.ontology = {q(REL_IRI[s['type']])};")
    (ROOT / "data/graph_load.cypher").write_text("\n".join(L_) + "\n", encoding="utf-8")

    by = defaultdict(int)
    for x in linking:
        by[x[3]] += 1
    md = ["# Нормалізація та entity linking (ЛР13, результат 5)", "",
          f"Сутностей після нормалізації: {len(linking)}; зв'язано з вузлами графа ЛР9: {by['LR9']}, "
          f"з термінами онтології ЛР8: {by['LR8']}, нових вузлів: {by['—']}.", "",
          "## Правила", "",
          "1. Нормалізація — `src/schema.py::canonical()` (таблиця в `docs/extraction_schema.md`, розділ 5).",
          "2. Канонічний ID збігається з `id` вузла графа ЛР9 → зв'язок `SAME_AS` з вузлом ЛР9.",
          "3. Методи прогнозування → клас онтології ЛР8 (`broader`): ARIMA, SARIMA, VAR → `:StatisticalModel`; LSTM, GRU → `:MachineLearningModel`.",
          "4. Погодні змінні → властивість онтології (`exactMatch`), якщо вона є: температура → `:temperature`, хмарність → `:cloudCover`.",
          "5. MAPE → `closeMatch :errorPercentage` (у базі знань похибка прогнозу — відносна, як у MAPE).",
          "6. Немає відповідника в ЛР8/ЛР9 → новий вузол `XEntity` без зв'язку (рішення: не вигадувати IRI).", "",
          "## Рішення щодо граничних випадків", "",
          "- «№1» у переліку «моделі LSTM: №1, №2 і №3» → `ForecastModel_LSTM1` (не підстанція).",
          "- «Consumer_5019» у проєктному документі та «споживач №5019» — одна сутність `Consumer_5019`.",
          "- «Закарпатській області», «Закарпатська область» → `Region_Zakarpattia`; «закарпатські підстанції» не зв'язуються.",
          "- Вологість, вітер, HDD, CDD, MAE, RMSE, sMAPE, WAPE, pinball loss — нові вузли (у ЛР8 немає; kb04 називає це прогалиною).", "",
          "## Таблиця зв'язування", "", "| Тип | Канонічний ID | Джерело зв'язку | Ціль | Вид |", "|---|---|---|---|---|"]
    md += [f"| {t} | {c} | {src} | {target} | {how} |" for t, c, surf, src, target, how, name in linking]
    (ROOT / "docs/entity_linking.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    m = defaultdict(int)
    for s in stmts:
        m[(s["kind"], s["method"])] += 1
    print(f"тверджень у графі: {len(stmts)} {dict(m)}; сутностей {len(linking)}: {dict(by)}; рядків Cypher {len(L_)}")


if __name__ == "__main__":
    main()
