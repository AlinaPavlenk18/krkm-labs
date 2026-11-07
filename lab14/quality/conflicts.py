"""Р3. Суперечності: автоматичне виявлення, перевірка реєстру, журнал рішень.

  python quality/conflicts.py detect   # facts.py (значення), SPARQL-виведення класу + OWL-RL (логічні),
                                       # SPARQL-правило дат навчання і правило kb08 (часові) → out/conflicts_detected.json
  python quality/conflicts.py check    # кожна цитата реєстру є в джерелі (не вигадана) → out/conflicts_check.json
  python quality/conflicts.py report   # quality/conflicts.md — суперечності, стратегії, виправлення, журнал рішень

Реєстр рішень — quality/conflicts_registry.json (альтернативи з provenance, стратегія, рішення, виправлення).
Виправлення застосовує quality/fix_store.py (нова версія сховища data_after/).
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

from common import DATA, LAB, OUT, QUALITY, load_corpus, load_triples, read_jsonl, safe_quote, sections, to_rdf, write_json
import facts

REGISTRY = QUALITY / "conflicts_registry.json"
EXN = "http://www.semanticweb.org/energy-forecasting#"


def load_registry():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def source_text(doc_id, section, base=DATA):
    """Текст джерела цитати: секція корпусу RAG, документ ЛР13 (prj10/prj11) або файл онтології."""
    if doc_id == "ontology":
        return (Path(base) / "store" / "ontology" / section).read_text(encoding="utf-8"), {"doc_id": "ontology", "sensitivity": "public"}
    docs = {d["doc_id"]: d for d in load_corpus(Path(base) / "corpus" / "docs.jsonl")}
    if doc_id in docs:
        d = docs[doc_id]
        for s in d["sections"]:
            if s["section"] == section:
                return s["text"], d
        return None, d
    lab13 = {d["doc_id"]: d for d in read_jsonl(Path(base) / "lab13" / "docs.jsonl")}
    if doc_id in lab13:
        return lab13[doc_id]["text"], lab13[doc_id]
    return None, None


def unresolved_value_conflicts(docs):
    """Величини корпусу з різними значеннями, для яких у сховищі немає рішення.
    Розв'язана = є в реєстрі (поле quantity), усі знайдені значення є серед альтернатив реєстру, і корпус містить
    рішення: секцію kb16 «K… .» або примітку «ЛР14-K…». Повертає (кількість величин, суперечності, розв'язані, нерозв'язані)."""
    import re
    _, rows, conflicts = facts.consistency(docs)
    reg = {c["quantity"]: c for c in load_registry()["conflicts"] if c.get("quantity")}
    text = " ".join(f"{t} {x}" for _, _, t, x in sections(docs))
    resolved = []
    for c in conflicts:
        k = reg.get(c["quantity"])
        if not k:
            continue
        known = {round(float(m.replace(",", ".")), 4) for a in k["alternatives"] for m in re.findall(r"\d+(?:[.,]\d+)?", a["value"])}
        if all(round(v["value"], 4) in known or any(abs(v["value"] - x) < 10 ** -facts.PRECISION[c["quantity"].split(".")[-1]] for x in known)
               for v in c["variants"]) and (f"ЛР14-{k['id']}" in text or f"{k['id']}. " in text):
            resolved.append(c["quantity"])
    return len(rows), conflicts, resolved, [c["quantity"] for c in conflicts if c["quantity"] not in resolved]

Q_OVERLOADED = """
PREFIX : <%s>
SELECT ?s ?ratio WHERE {
  ?s a :Substation ; :currentLoad ?c ; :nominalCapacity ?n .
  BIND(?c / ?n AS ?ratio) FILTER(?ratio >= 0.85)
}""" % EXN

Q_TRAINING = """
PREFIX : <%s>
SELECT ?m ?td (MAX(?ts) AS ?last) WHERE {
  ?m :trainingDate ?td ; :trainedOnMeasurement ?x . ?x :timestamp ?ts .
} GROUP BY ?m ?td""" % EXN


def reasoner(g):
    """OWL-RL-замикання (перевірка несумісності) + SPARQL-виведення :OverloadedSubstation за визначенням онтології."""
    import owlrl
    from rdflib import OWL, RDF
    clos = to_rdf(load_triples())
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(clos)
    nothing = [str(s).split("#")[-1] for s in clos.subjects(RDF.type, OWL.Nothing)]
    disjoint = []
    for a, b in clos.subject_objects(OWL.disjointWith):
        for s in set(clos.subjects(RDF.type, a)) & set(clos.subjects(RDF.type, b)):
            disjoint.append(f"{str(s).split('#')[-1]}: {str(a).split('#')[-1]} ⊓ {str(b).split('#')[-1]}")
    inferred = sorted((str(r.s).split("#")[-1], round(float(r.ratio) * 100, 1)) for r in g.query(Q_OVERLOADED))
    return {"owl_nothing": nothing, "disjoint_violations": disjoint, "inferred_overloaded": inferred}


def training_dates(g):
    out = []
    for r in g.query(Q_TRAINING):
        td, last = str(r.td)[:10], str(r.last)[:10]
        if td < last:
            out.append({"model": str(r.m).split("#")[-1], "trainingDate": td, "last_training_measurement": last})
    return sorted(out, key=lambda x: x["model"])


def stale_status(ref):
    """Модель старша за 12 міс. (kb08), але в картці gen02 статус «в експлуатації»."""
    from common import load_graph
    nodes, _ = load_graph()
    docs = {d["doc_id"]: d for d in load_corpus()}
    cards = {s["section"]: s["text"] for s in docs["gen02"]["sections"]}
    out = []
    for m in nodes["forecastmodel"]:
        age = (ref - date.fromisoformat(m["trainingDate"])).days
        title = m["name"].replace(" (застаріла)", "")
        if age > 365 and "Статус: в експлуатації" in cards.get(title, ""):
            out.append({"model": m["id"], "age_days": age, "card_status": "в експлуатації"})
    return out


def prj10_overload_claims():
    import re
    d = {x["doc_id"]: x for x in read_jsonl(DATA / "lab13" / "docs.jsonl")}["prj10"]
    m = re.search(r"пікове завантаження ≥ 85 % номіналу \(([^)]*)\), тобто відповідають класу :OverloadedSubstation", d["text"])
    return [f"Substation_{n}" for n in re.findall(r"№(\d+) —", m.group(1))] if m else []


def cmd_detect(a):
    ref = date.fromisoformat(a.ref_date) if a.ref_date else date.today()
    g = to_rdf(load_triples())
    share, rows, value_conf = facts.consistency(load_corpus())
    rs = reasoner(g)
    inferred = {s for s, _ in rs["inferred_overloaded"]}
    claimed = prj10_overload_claims()
    det = {
        "ref_date": ref.isoformat(),
        "value": [{"quantity": c["quantity"], "variants": {str(v["value"]): v["docs"] for v in c["variants"]}} for c in value_conf],
        "logical_reasoner": {**rs, "prj10_claims_overloaded": claimed,
                             "claimed_not_inferred": sorted(set(claimed) - inferred),
                             "inferred_not_claimed": sorted(inferred - set(claimed))},
        "temporal_training_date": training_dates(g),
        "temporal_stale_status": stale_status(ref),
    }
    reg = {c["id"]: c for c in load_registry()["conflicts"]}
    q2k = {"Louvain.communities": "K1", "Louvain.modularity": "K2", "ForecastModel_GRU1.pagerank": "K3",
           "Louvain.weather_communities": "K4"}
    det["registered"] = {q: q2k.get(q) for q in [c["quantity"] for c in value_conf]}
    det["unregistered_value_conflicts"] = [q for q, k in det["registered"].items() if k not in reg]
    write_json(OUT / "conflicts_detected.json", det)
    print(json.dumps(det, ensure_ascii=False, indent=1))


def cmd_check(a):
    res, bad = [], 0
    for c in load_registry()["conflicts"]:
        for alt in c["alternatives"]:
            text, doc = source_text(alt["source"], alt["section"])
            ok = bool(text) and alt["quote"] in text
            bad += not ok
            res.append({"conflict": c["id"], "kind": "alternative", "source": alt["source"], "section": alt["section"], "ok": ok})
        for f in c["fix"]:
            text, doc = source_text(f["doc"], f["section"])
            ok = bool(text) and f["after"] in text
            bad += not ok
            res.append({"conflict": c["id"], "kind": "fix-anchor", "source": f["doc"], "section": f["section"], "ok": ok})
    write_json(OUT / "conflicts_check.json", {"checked": len(res), "missing": bad, "items": res})
    for r in res:
        print(f"{r['conflict']:<3} {r['kind']:<12} {r['source']:<9} {'OK' if r['ok'] else 'НЕМАЄ ЦИТАТИ'}  {r['section'][:50]}")
    print(f"Перевірено {len(res)}, не знайдено {bad}")
    sys.exit(1 if bad else 0)


def cmd_report(a):
    reg = load_registry()
    det = json.loads((OUT / "conflicts_detected.json").read_text(encoding="utf-8")) if (OUT / "conflicts_detected.json").exists() else {}
    types = sorted({c["type"].split(" (")[0] for c in reg["conflicts"]})
    L = ["# Суперечності та їх розв'язання (ЛР14, Р3)", "",
         f"Реєстр: `quality/conflicts_registry.json` (версія {reg['version']}). Суперечностей: **{len(reg['conflicts'])}**, "
         f"типів: **{len(types)}** ({', '.join(types)}). Альтернативи з provenance: `data_after/store/alternatives.ttl` (PROV-O) "
         "і документ kb16 корпусу (будує `quality/fix_store.py`).", "",
         "## Зведення", "", "| ID | Тип | Що суперечить | Чинне | Альтернатива | Стратегія |", "|---|---|---|---|---|---|"]
    for c in reg["conflicts"]:
        pref = "; ".join(sorted({x["value"] for x in c["alternatives"] if x["status"] == "preferred"}))
        alt = "; ".join(sorted({x["value"] for x in c["alternatives"] if x["status"] != "preferred"}))
        L.append(f"| {c['id']} | {c['type']} | {c['subject']} — {c['property']} | {pref or '—'} | {alt} | {c['strategy']} |")
    L += ["", "## Деталі", ""]
    for c in reg["conflicts"]:
        L += [f"### {c['id']}. {c['subject']} — {c['property']}", "", f"Тип: {c['type']}. Виявлено: {c['detected_by']}.", ""]
        for x in c["alternatives"]:
            _, doc = source_text(x["source"], x["section"])
            q = safe_quote(x["quote"], doc or {"doc_id": x["source"]})
            L.append(f"- **{x['value']}** ({x['status']}) — {x['source']}, «{x['section']}»: «{q}»; {x['provenance']}.")
        L += ["", f"Стратегія: {c['strategy']}.", "", f"Рішення: {c['decision']}", ""]
        if c["fix"]:
            L.append("Виправлення в сховищі: " + "; ".join(f"примітка в {f['doc']} («{f['section']}»)" for f in c["fix"]) + ".")
            L.append("")
    if det:
        L += ["## Автоматичне виявлення (`conflicts.py detect`)", "",
              f"- Суперечності значень (facts.py): {', '.join(v['quantity'] for v in det['value']) or 'немає'}.",
              f"- OWL-RL: несумісних класів {len(det['logical_reasoner']['disjoint_violations'])}, owl:Nothing {len(det['logical_reasoner']['owl_nothing'])}.",
              f"- Виведено :OverloadedSubstation (поточне ≥ 85 %): {', '.join(f'{s} ({r} %)' for s, r in det['logical_reasoner']['inferred_overloaded'])}.",
              f"- prj10 називає класом: {', '.join(det['logical_reasoner']['prj10_claims_overloaded'])}; "
              f"не виводяться онтологією: {', '.join(det['logical_reasoner']['claimed_not_inferred']) or '—'}.",
              f"- Дата навчання раніша за навчальні дані: {len(det['temporal_training_date'])} моделей "
              f"({', '.join(x['model'] for x in det['temporal_training_date'])}).",
              f"- Застарілий статус у картці gen02: {', '.join(x['model'] for x in det['temporal_stale_status']) or '—'}.", ""]
    L += ["## Журнал рішень", "", "| ID | Рішення | Хто вирішив | Коли | Хто запропонував | Чому |", "|---|---|---|---|---|---|"]
    for c in reg["conflicts"]:
        L.append(f"| {c['id']} | {c['decision'].split('.')[0]} | {c.get('decided_by', reg['owner'])} | "
                 f"{c.get('decided_at', reg['decided_at'])} | {reg['proposed_by']} | {c['strategy']} |")
    (QUALITY / "conflicts.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"→ {QUALITY / 'conflicts.md'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("detect")
    d.add_argument("--ref-date", default=None)
    sub.add_parser("check")
    sub.add_parser("report")
    a = ap.parse_args()
    {"detect": cmd_detect, "check": cmd_check, "report": cmd_report}[a.cmd](a)
