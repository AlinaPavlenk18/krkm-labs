"""Р3–Р5. Нова версія сховища data_after/ = baseline (data/) + виправлення якості. Baseline не змінюється.

Що робиться (кожна зміна — у data_after/CHANGES.json з provenance):
  1. Суперечності (реєстр conflicts_registry.json): примітки в секціях корпусу після спірного твердження
     і новий документ kb16 «Реєстр розв'язаних суперечностей» (обидві версії, джерела, рішення).
  2. Альтернативи з provenance: data_after/store/alternatives.ttl (PROV-O) — для K1–K8 і для дат навчання 6 моделей (K6).
  3. Граф: ForecastModel.status за правилом kb08 (K7), trainingDateFlag (K6); LOCATED_IN.validFrom = дата внесення
     в граф ЛР9 з поясненням validFromBasis (час чинності невідомий).
  4. Майже-дублікати секцій (унікальність, Р1): копія в пізнішому документі прибирається, якщо containment 5-грам ≥ 0.6
     і секція не містить доказів тестів RAG; оригінал отримує also_in, вилучений текст — у out/section_merges.jsonl
     (можна повернути: --no-section-dedup).

  python quality/fix_store.py [--ref-date 2026-11-07] [--no-section-dedup]
"""
import argparse
import csv
import json
import shutil
from datetime import date, datetime
from pathlib import Path

from common import DATA, LAB, OUT, normalize, read_jsonl, sections, shingles, write_json, write_jsonl
from conflicts import load_registry

AFTER = LAB / "data_after"
DEDUP_THR = 0.6
LOCATED_IN_DATE = "2026-10-17"          # дата імпорту графа ЛР9 (prj01/prj09); це час внесення, не час чинності


def insert_note(text, anchor, note):
    i = text.find(anchor)
    if i < 0:
        raise ValueError(f"не знайдено якір «{anchor[:50]}»")
    j = i + len(anchor)
    return text[:j] + " " + note + text[j:]


def kb16(reg, docs_by_id, today):
    secs = [{"section": "Призначення документа",
             "text": "Документ фіксує суперечності, знайдені під час перевірки якості бази знань (ЛР14), і рішення щодо них. "
                     "Для кожної суперечності наведено всі версії значення з джерелами, чинну версію, стратегію розв'язання "
                     "та відповідального. Застарілі версії не видаляються — вони збережені як альтернативи з походженням."}]
    for c in reg["conflicts"]:
        def fmt(x):
            title = docs_by_id.get(x["source"], {}).get("title", x["source"])
            return f"{x['value']} — {x['source']} («{title}», розділ «{x['section']}»; {x['provenance']})"
        pref = [fmt(x) for x in c["alternatives"] if x["status"] == "preferred"]
        alt = [fmt(x) for x in c["alternatives"] if x["status"] != "preferred"]
        txt = (f"Суперечність {c['id']} ({c['type']}): {c['subject']}, {c['property']}. "
               + (f"Чинна версія: {'; '.join(pref)}. " if pref else "")
               + f"Інші версії: {'; '.join(alt)}. Стратегія: {c['strategy']}. Рішення: {c['decision']} "
               f"Вирішила: {reg['owner']}, {reg['decided_at']}.")
        secs.append({"section": f"{c['id']}. {c['property'][0].upper()}{c['property'][1:]} ({c['subject']})", "text": txt})
    return {"doc_id": "kb16", "title": "Реєстр розв'язаних суперечностей бази знань", "type": "kb_article", "date": today,
            "sensitivity": "public",
            "source_url": "https://github.com/AlinaPavlenk18/krkm-labs/blob/main/lab14/quality/conflicts.md",
            "license": "CC BY 4.0 (Павленко А. С.)", "origin": "згенеровано з quality/conflicts_registry.json (ЛР14)",
            "file": "kb/kb16_conflict_registry.md", "sections": secs}


def alternatives_ttl(reg, models_alt, today):
    def lit(s):
        return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'
    L = ["@prefix : <http://www.semanticweb.org/energy-forecasting#> .", "@prefix q: <http://www.semanticweb.org/energy-forecasting/quality#> .",
         "@prefix prov: <http://www.w3.org/ns/prov#> .", "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .", ""]
    for c in reg["conflicts"]:
        L += [f"q:decision_{c['id']} a prov:Activity ; q:conflictType {lit(c['type'])} ; q:strategy {lit(c['strategy'])} ;",
              f"    q:decision {lit(c['decision'])} ; prov:wasAssociatedWith {lit(reg['owner'])} ;",
              f"    prov:endedAtTime \"{reg['decided_at']}\"^^xsd:date .", ""]
        for i, x in enumerate(c["alternatives"], 1):
            L += [f"q:alt_{c['id']}_{i} a q:ValueAlternative ; q:aboutSubject {lit(c['subject'])} ; q:aboutProperty {lit(c['property'])} ;",
                  f"    q:value {lit(x['value'])} ; q:status {lit(x['status'])} ; q:sourceDoc {lit(x['source'])} ;",
                  f"    q:sourceSection {lit(x['section'])} ; q:quote {lit(x['quote'])} ; q:provenanceNote {lit(x['provenance'])} ;",
                  f"    prov:wasGeneratedBy q:decision_{c['id']} .", ""]
    for m in models_alt:
        L += [f"q:alt_K6_{m['model']}_graph a q:ValueAlternative ; q:aboutSubject :{m['model']} ; q:aboutProperty \"trainingDate\" ;",
              f"    q:value \"{m['trainingDate']}\"^^xsd:date ; q:status \"alternative\" ; q:sourceDoc \"граф ЛР9 (triples)\" ;",
              "    prov:wasGeneratedBy q:decision_K6 .",
              f"q:alt_K6_{m['model']}_data a q:ValueAlternative ; q:aboutSubject :{m['model']} ; q:aboutProperty \"trainingDate (нижня межа)\" ;",
              f"    q:value \"не раніше {m['last_training_measurement']}\" ; q:status \"alternative\" ;",
              "    q:sourceDoc \"TRAINED_ON + Measurement.timestamp (виведено SPARQL)\" ; prov:wasGeneratedBy q:decision_K6 .", ""]
    return "\n".join(L)


def protected_sections(docs):
    tests = read_jsonl(DATA / "rag_baseline" / "rag_eval.jsonl")
    evs = [(e["doc_id"], normalize(e["evidence"])) for t in tests for e in t.get("evidences", [])]
    return {(d["doc_id"], i) for d, i, _, x in sections(docs) if any(dd == d["doc_id"] and e in normalize(x) for dd, e in evs)}


def dedup_sections(docs, changes):
    prot = protected_sections(docs)
    secs = [(d, i, t, shingles(x)) for d, i, t, x in sections(docs)]
    drop, log = set(), []
    for a in range(len(secs)):
        for b in range(a + 1, len(secs)):
            (da, ia, ta, sa), (db, ib, tb, sb) = secs[a], secs[b]
            if da["doc_id"] == db["doc_id"] or len(sa) < 10 or len(sb) < 10:
                continue
            c = len(sa & sb) / min(len(sa), len(sb))
            if c < DEDUP_THR:
                continue
            (keep, ki, kt), (copy, ci, ct) = sorted([(da, ia, ta), (db, ib, tb)], key=lambda x: (x[0]["date"], x[0]["doc_id"]))
            if (copy["doc_id"], ci) in prot:
                log.append({"kept_both": True, "reason": "копія містить доказ тесту RAG", "a": f"{keep['doc_id']}#{ki}", "b": f"{copy['doc_id']}#{ci}", "containment": round(c, 2)})
                continue
            drop.add((copy["doc_id"], ci))
            keep["sections"][ki].setdefault("also_in", []).append({"doc_id": copy["doc_id"], "section": ct, "containment": round(c, 2)})
            log.append({"op": "merge_section", "kept": f"{keep['doc_id']}#{ki} «{kt}»", "removed": f"{copy['doc_id']}#{ci} «{ct}»",
                        "containment": round(c, 2), "removed_text": copy["sections"][ci]["text"],
                        "ts": datetime.now().isoformat(timespec="seconds")})
    for d in docs:
        d["sections"] = [s for i, s in enumerate(d["sections"]) if (d["doc_id"], i) not in drop]
    write_jsonl(OUT / "section_merges.jsonl", log)
    changes += [{"what": "злиття секції-дубліката", **{k: v for k, v in x.items() if k != "removed_text"}} for x in log]


def rewrite_csv(path, rows, fields):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main(a):
    ref = date.fromisoformat(a.ref_date) if a.ref_date else date.today()
    today = ref.isoformat()
    if AFTER.exists():
        shutil.rmtree(AFTER)
    shutil.copytree(DATA / "store", AFTER / "store")
    (AFTER / "corpus").mkdir(parents=True)
    (AFTER / "lab13").mkdir(parents=True)
    reg = load_registry()
    changes = []
    docs = read_jsonl(DATA / "corpus" / "docs.jsonl")
    lab13 = read_jsonl(DATA / "lab13" / "docs.jsonl")
    by = {d["doc_id"]: d for d in docs}
    by13 = {d["doc_id"]: d for d in lab13}
    # 1. примітки до суперечностей
    for c in reg["conflicts"]:
        for f in c["fix"]:
            if f["doc"] in by:
                s = next(s for s in by[f["doc"]]["sections"] if s["section"] == f["section"])
                s["text"] = insert_note(s["text"], f["after"], f["note"])
            else:
                by13[f["doc"]]["text"] = insert_note(by13[f["doc"]]["text"], f["after"], f["note"])
            changes.append({"what": "примітка до суперечності", "conflict": c["id"], "doc": f["doc"], "section": f["section"]})
    # 4. дублікати секцій (до додавання kb16)
    if a.section_dedup:
        dedup_sections(docs, changes)
    docs.append(kb16(reg, by, today))
    changes.append({"what": "новий документ kb16", "sections": len(docs[-1]["sections"])})
    write_jsonl(AFTER / "corpus" / "docs.jsonl", docs)
    write_jsonl(AFTER / "lab13" / "docs.jsonl", lab13)
    # 3. граф
    g = AFTER / "store" / "graph"
    models = list(csv.DictReader(open(g / "nodes_forecastmodel.csv", encoding="utf-8")))
    from conflicts import training_dates
    from common import load_triples, to_rdf
    td = {x["model"]: x for x in training_dates(to_rdf(load_triples()))}
    for m in models:
        stale = (ref - date.fromisoformat(m["trainingDate"])).days > 365
        m["status"] = "потребує перенавчання" if stale else "в експлуатації"
        m["statusSource"] = f"правило kb08 (>12 міс.), оцінка {today}"
        m["trainingDateFlag"] = (f"K6: раніша за навчальні дані (до {td[m['id']]['last_training_measurement']})" if m["id"] in td else "ok")
    rewrite_csv(g / "nodes_forecastmodel.csv", models, list(models[0].keys()))
    changes.append({"what": "ForecastModel.status / trainingDateFlag", "conflicts": ["K6", "K7"],
                    "stale": [m["id"] for m in models if m["status"] != "в експлуатації"]})
    loc = list(csv.DictReader(open(g / "rels_located_in.csv", encoding="utf-8")))
    n = 0
    for r in loc:
        if not r["validFrom"]:
            r["validFrom"], n = LOCATED_IN_DATE, n + 1
        r["validFromBasis"] = "дата внесення в граф ЛР9 (transaction time); час чинності невідомий"
    rewrite_csv(g / "rels_located_in.csv", loc, list(loc[0].keys()))
    changes.append({"what": "LOCATED_IN.validFrom", "filled": n, "value": LOCATED_IN_DATE, "basis": "transaction time"})
    # 2. альтернативи
    (AFTER / "store" / "alternatives.ttl").write_text(alternatives_ttl(reg, list(td.values()), today), encoding="utf-8")
    changes.append({"what": "alternatives.ttl", "conflicts": len(reg["conflicts"]), "model_alternatives": 2 * len(td)})
    write_json(AFTER / "CHANGES.json", {"created": datetime.now().isoformat(timespec="seconds"), "ref_date": today,
                                        "base": "data/ (baseline)", "changes": changes})
    for c in changes:
        print(" -", json.dumps(c, ensure_ascii=False)[:160])
    print(f"→ {AFTER}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref-date", default=None)
    ap.add_argument("--no-section-dedup", dest="section_dedup", action="store_false")
    main(ap.parse_args())
