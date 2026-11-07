"""Р1 (і Р5): профіль якості сховища знань — 11 метрик за 8 вимірами, пороги, дашборд, версія.

Сховище = граф Neo4j ЛР9 (CSV-знімок) + RDF-трійки ЛР9 з provenance + онтологія ЛР8 + корпус RAG ЛР11.

  python quality/quality_profile.py                                  # baseline → quality/metrics.json, quality/profile_baseline.md
  python quality/quality_profile.py --tag after --store data_after/store --corpus data_after/corpus/docs.jsonl   # Р5

Дата відліку для актуальності — --ref-date (типово сьогодні); фіксується в metrics.json разом із git-комітом
і хешем знімка, тому baseline можна відтворити.
"""
import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

from common import (DATA, LAB, OUT, QUALITY, files_hash, git_commit, load_corpus, load_graph, load_triples,
                    read_jsonl, sections, shingles, to_rdf, write_json)
import facts

# обов'язкові зв'язки: (мітка вузла, тип зв'язку, напрям) — вузол має мати хоча б один такий зв'язок
REQUIRED_LINKS = [("substation", "LOCATED_IN", "out"), ("substation", "MANAGES", "in"),
                  ("consumer", "HAS_METER", "out"), ("consumer", "CONNECTED_TO", "out"),
                  ("meter", "HAS_METER", "in"), ("measurement", "RECORDED", "in"),
                  ("forecast", "GENERATED", "in"), ("forecast", "FORECAST_FOR", "out")]
DOC_PROV = ["source_url", "license", "origin", "date"]
REL_PROV = ["source", "confidence", "validFrom"]
SENS = {"public", "internal", "restricted"}
ALLOWED_ANALYST = {"public", "internal"}


def m_completeness_attrs(nodes):
    tot = ok = 0
    bad = Counter()
    for lab, rows in nodes.items():
        for n in rows:
            tot += 1
            miss = [k for k, v in n.items() if k != "source" and (v is None or v == "")]
            ok += not miss
            for k in miss:
                bad[f"{lab}.{k}"] += 1
    return ok / tot, {"nodes": tot, "missing": dict(bad)}


def m_completeness_links(nodes, rels):
    out, inn = defaultdict(set), defaultdict(set)
    for t, rows in rels.items():
        for r in rows:
            out[(r["start"], t)].add(r["end"])
            inn[(r["end"], t)].add(r["start"])
    tot, miss = 0, []
    for lab, t, d in REQUIRED_LINKS:
        for n in nodes[lab]:
            tot += 1
            if not (out if d == "out" else inn).get((n["id"], t)):
                miss.append(f"{n['id']} без {t} ({'вихідний' if d == 'out' else 'вхідний'})")
    return 1 - len(miss) / tot, {"slots": tot, "missing": miss}


def m_consistency(docs):
    """Частка величин без НЕРОЗВ'ЯЗАНОЇ суперечності (див. conflicts.unresolved_value_conflicts)."""
    from conflicts import unresolved_value_conflicts
    n, conflicts, resolved, unresolved = unresolved_value_conflicts(docs)
    return 1 - len(unresolved) / n, {"quantities": n, "with_variants": [c["quantity"] for c in conflicts],
                                     "resolved_in_store": resolved, "inconsistent": unresolved,
                                     "variants": {c["quantity"]: {str(v["value"]): v["docs"] for v in c["variants"]} for c in conflicts}}


def m_accuracy():
    p = QUALITY / "accuracy_sample.csv"
    if not p.exists():
        return None, {"n": 0, "note": "немає вибірки — python quality/accuracy_sample.py"}
    rows = list(csv.DictReader(open(p, encoding="utf-8-sig"), delimiter=";"))
    marked = [r for r in rows if r["expert_ok"].strip() in ("0", "1")]
    if len(marked) < len(rows):
        return None, {"n": len(rows), "marked": len(marked), "note": "вибірку ще не розмічено експертом"}
    wrong = [f"{r['id']} ({r['doc_id']}): {r['expert_comment']}" for r in marked if r["expert_ok"].strip() == "0"]
    return 1 - len(wrong) / len(marked), {"n": len(marked), "wrong": wrong}


def m_timeliness(nodes, ref):
    stale = []
    for m in nodes["forecastmodel"]:
        age = (ref - date.fromisoformat(m["trainingDate"])).days
        if age > 365:
            stale.append(f"{m['id']} (навчена {m['trainingDate']}, {age} дн.)")
    n = len(nodes["forecastmodel"])
    return 1 - len(stale) / n, {"models": n, "stale": stale}


def m_uniqueness(docs, thr=0.5):
    secs = [(d["doc_id"], f"{d['doc_id']}#{i}", t, shingles(x)) for d, i, t, x in sections(docs)]
    secs = [s for s in secs if len(s[3]) >= 10]
    dup, pairs = set(), []
    for a in range(len(secs)):
        for b in range(a + 1, len(secs)):
            if secs[a][0] == secs[b][0]:
                continue
            sa, sb = secs[a][3], secs[b][3]
            c = len(sa & sb) / min(len(sa), len(sb))
            if c >= thr:
                dup.update([secs[a][1], secs[b][1]])
                pairs.append((secs[a][1], secs[b][1], round(c, 2)))
    return len(dup) / len(secs), {"sections": len(secs), "dup_sections": len(dup), "pairs": sorted(pairs, key=lambda x: -x[2])}


def m_provenance(nodes, rels, docs):
    tot = ok = 0
    bad = Counter()
    for lab, rows in nodes.items():
        for n in rows:
            tot += 1
            ok += bool(n.get("source"))
            bad[f"node:{lab}"] += not n.get("source")
    for t, rows in rels.items():
        for r in rows:
            tot += 1
            miss = [k for k in REL_PROV if not r.get(k)]
            ok += not miss
            for k in miss:
                bad[f"{t}.{k}"] += 1
    for d in docs:
        tot += 1
        miss = [k for k in DOC_PROV if not d.get(k)]
        ok += not miss
        for k in miss:
            bad[f"doc.{k}"] += 1
    return ok / tot, {"records": tot, "missing": {k: v for k, v in bad.items() if v}}


def m_validity(store, extra_shapes=None):
    from pyshacl import validate
    from rdflib import Graph, Namespace
    g = to_rdf(load_triples(store), store=store)
    sh = Graph().parse(Path(store) / "ontology" / "lab08_shapes.ttl")
    if extra_shapes and Path(extra_shapes).exists():
        sh.parse(extra_shapes)
    conforms, rg, _ = validate(g, shacl_graph=sh, inference="rdfs")
    SH = Namespace("http://www.w3.org/ns/shacl#")
    viol = []
    for r in rg.subjects(predicate=None, object=SH.ValidationResult):
        viol.append(f"{str(rg.value(r, SH.focusNode)).split('#')[-1]}: {rg.value(r, SH.resultMessage)}")
    return len(viol), {"conforms": bool(conforms), "violations": sorted(viol), "shapes": "lab08_shapes.ttl" +
                                                                                       (f" + {Path(extra_shapes).name}" if extra_shapes and Path(extra_shapes).exists() else "")}


def m_access_labels(docs):
    bad = [d["doc_id"] for d in docs if d.get("sensitivity") not in SENS or not any(s["text"].strip() for s in d["sections"])]
    return 1 - len(bad) / len(docs), {"docs": len(docs), "bad": bad}


def m_access_rag(docs, tests):
    sens = {d["doc_id"]: d["sensitivity"] for d in docs}
    tests = [t for t in tests if t["category"] in ("answerable", "conflict")]
    blocked = [t["id"] for t in tests if not any(sens.get(e["doc_id"]) in ALLOWED_ANALYST for e in t["evidences"])]
    return 1 - len(blocked) / len(tests), {"tests": len(tests), "no_accessible_evidence": blocked}


# id, вимір, назва, поріг, оператор
DEFS = [
    ("completeness_attrs", "повнота", "Частка вузлів графа з усіма заповненими атрибутами", 0.98, ">="),
    ("completeness_links", "повнота", "Частка обов'язкових зв'язків, що існують (регіон, диспетчер, лічильник…)", 1.0, ">="),
    ("consistency_values", "узгодженість", "Частка величин корпусу без нерозв'язаних суперечностей (і збіг із графом)", 1.0, ">="),
    ("accuracy_expert", "точність", "Частка правильних тверджень в експертній вибірці (n = 30)", 0.95, ">="),
    ("timeliness_models", "актуальність", "Частка моделей, навчених не раніше ніж 12 міс. тому (правило kb08)", 1.0, ">="),
    ("uniqueness_sections", "унікальність", "Частка секцій корпусу, що мають майже-дублікат в іншому документі", 0.02, "<="),
    ("provenance_records", "походження", "Частка записів (вузли, зв'язки, документи) з повним provenance", 1.0, ">="),
    ("validity_shacl", "валідність", "Кількість порушень SHACL на RDF-трійках сховища", 0, "<="),
    ("access_labels", "доступність", "Частка документів з валідною міткою доступу й непорожнім текстом", 1.0, ">="),
    ("access_rag", "доступність", "Частка тестів RAG ЛР11 з доказом, доступним ролі analyst", 1.0, ">="),
]


def rag_indicators(records_path):
    """Як дублікати й суперечності впливають на RAG: зайнятість топ-k документом prj09 і повтори документів."""
    if not Path(records_path).exists():
        return {}
    recs = read_jsonl(records_path)
    slots = [s["doc_id"] for r in recs for s in r["sources_full"]]
    same_doc = sum(1 for r in recs if max(Counter(s["doc_id"] for s in r["sources_full"]).values(), default=0) >= 3)
    return {"queries": len(recs), "topk_slots": len(slots), "share_slots_prj09": round(slots.count("prj09") / len(slots), 3),
            "queries_with_3plus_from_one_doc": same_doc}


def run(a):
    ref = date.fromisoformat(a.ref_date) if a.ref_date else date.today()
    store, corpus = Path(a.store).resolve(), Path(a.corpus).resolve()
    nodes, rels = load_graph(store)
    docs = load_corpus(corpus)
    tests = read_jsonl(DATA / "rag_baseline" / "rag_eval.jsonl")
    calc = {
        "completeness_attrs": lambda: m_completeness_attrs(nodes),
        "completeness_links": lambda: m_completeness_links(nodes, rels),
        "consistency_values": lambda: m_consistency(docs),
        "accuracy_expert": m_accuracy,
        "timeliness_models": lambda: m_timeliness(nodes, ref),
        "uniqueness_sections": lambda: m_uniqueness(docs),
        "provenance_records": lambda: m_provenance(nodes, rels, docs),
        "validity_shacl": lambda: m_validity(store, a.shapes),
        "access_labels": lambda: m_access_labels(docs),
        "access_rag": lambda: m_access_rag(docs, tests),
    }
    metrics = []
    for mid, dim, name, thr, op in DEFS:
        val, det = calc[mid]()
        ok = None if val is None else (val >= thr if op == ">=" else val <= thr)
        metrics.append({"id": mid, "dimension": dim, "name": name, "value": None if val is None else round(val, 4),
                        "threshold": thr, "op": op, "pass": ok, "details": det})
        print(f"{mid:<22} {str(None if val is None else round(val, 4)):>8} {op} {thr:<5} {'OK' if ok else ('—' if ok is None else 'FAIL')}")
    snap = [p for p in store.rglob("*") if p.is_file()] + [corpus]
    res = {"version": a.version or f"{a.tag}-{datetime.now():%Y%m%d}", "tag": a.tag,
           "created": datetime.now().isoformat(timespec="seconds"), "ref_date": ref.isoformat(),
           "git_commit": git_commit(), "snapshot_hash": files_hash(snap), "store": str(store.relative_to(LAB)),
           "corpus": str(corpus.relative_to(LAB)), "metrics": metrics,
           "rag_indicators": rag_indicators(DATA / "rag_baseline" / "records.jsonl") if a.tag == "baseline" else {}}
    out_json = QUALITY / ("metrics.json" if a.tag == "baseline" else f"metrics_{a.tag}.json")
    write_json(out_json, res)
    png = dashboard(res)
    write_md(res, png)
    print(f"→ {out_json}\n→ {png}")


def dashboard(res):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ms = res["metrics"]
    labels, vals, cols, thr = [], [], [], []
    for m in ms:
        labels.append(f"{m['id']}\n({m['dimension']})")
        if m["id"] == "validity_shacl":                     # кількість порушень → частка «0 порушень = 1»
            v, t = (1.0 if m["value"] == 0 else 1 / (1 + m["value"])), 1.0
        elif m["op"] == "<=":
            v, t = 1 - m["value"], 1 - m["threshold"]
        else:
            v, t = m["value"], m["threshold"]
        vals.append(v if v is not None else 0)
        thr.append(t)
        cols.append("#9e9e9e" if m["pass"] is None else ("#2e7d32" if m["pass"] else "#c62828"))
    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=150)
    y = range(len(ms))[::-1]
    ax.barh(list(y), vals, color=cols, height=0.6)
    ax.scatter(thr, list(y), marker="|", s=400, color="black", zorder=3, label="поріг")
    for yy, v, m in zip(y, vals, ms):
        txt = "очікує розмітки" if m["value"] is None else (str(m["value"]) if m["id"] == "validity_shacl" else f"{m['value']:.3f}")
        ax.text(min(v, 1.0) + 0.01, yy, txt, va="center", fontsize=8)
    ax.set_yticks(list(y), labels, fontsize=7.5)
    ax.set_xlim(0, 1.15)
    ax.set_xlabel("значення (для «≤»-метрик — 1 − значення; SHACL: 1/(1 + порушення))")
    ax.set_title(f"Профіль якості сховища · {res['version']} · відлік {res['ref_date']}", fontsize=10)
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), fontsize=8)
    plt.tight_layout()
    png = OUT / f"dashboard_{res['tag']}.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(png)
    plt.close()
    return png


def fmt(v):
    return "—" if v is None else (f"{v:.4f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v))


def priorities(res):
    """Три пріоритети покращення, впорядковані за очікуваним впливом на RAG (числа — з профілю та baseline ЛР11)."""
    m = {x["id"]: x for x in res["metrics"]}
    ri = res["rag_indicators"]
    rag = json.loads((DATA / "rag_baseline" / "summary.json").read_text(encoding="utf-8"))
    cons, uniq, tim = m["consistency_values"], m["uniqueness_sections"], m["timeliness_models"]
    return ["## Пріоритети покращення (за впливом на RAG)", "",
            f"1. **Суперечності значень (узгодженість {fmt(cons['value'])}).** Розбіжні величини: "
            f"{', '.join(cons['details']['inconsistent'])}. Саме про них конфліктні тести c1–c5 ЛР11: "
            f"conflict_both_versions = {rag['conflict_both_versions']}, тобто жодного разу RAG не назвав обидві версії й не пояснив, "
            "яка чинна. Дія: Р3 — розв'язати суперечності, зберегти альтернативи з provenance і явно позначити в корпусі чинне значення.",
            f"2. **Дублікати (унікальність {fmt(uniq['value'])} при порозі ≤ {uniq['threshold']}).** Звіт prj09 повторює секції "
            f"prj03–prj05; prj09 займає {ri['share_slots_prj09']} слотів топ-k, у {ri['queries_with_3plus_from_one_doc']} з "
            f"{ri['queries']} запитів ≥ 3 з 5 фрагментів — з одного документа, тож копії витісняють інші джерела "
            f"(context recall baseline {rag['context_recall']}). Дія: Р2 — entity resolution для сутностей і злиття майже-дублікатів секцій зі збереженням provenance.",
            f"3. **Актуальність і походження (моделі {fmt(tim['value'])}, provenance {fmt(m['provenance_records']['value'])}).** "
            f"Застарілі моделі: {'; '.join(tim['details']['stale'])}; у документах статус «застаріла» має лише LSTM №2, "
            "тож відповідь RAG про придатність моделей спирається на неактуальні тексти; у LOCATED_IN немає validFrom. "
            "Дія: Р3/Р4 — часові суперечності, правило актуальності в CI, позначення статусу з provenance.", ""]


def write_md(res, png):
    L = [f"# Профіль якості сховища — {res['tag']}", "",
         f"Версія: **{res['version']}** · створено {res['created']} · дата відліку {res['ref_date']} · "
         f"git {res['git_commit'] or '—'} · хеш знімка `{res['snapshot_hash']}`", "",
         f"Сховище: `{res['store']}` (граф ЛР9, трійки з provenance, онтологія ЛР8), корпус RAG: `{res['corpus']}`.", "",
         "| № | Вимір | Метрика | Значення | Поріг | Статус |", "|---|---|---|---|---|---|"]
    for i, m in enumerate(res["metrics"], 1):
        st = "очікує розмітки" if m["pass"] is None else ("✅ так" if m["pass"] else "❌ ні")
        L.append(f"| {i} | {m['dimension']} | {m['name']} | {fmt(m['value'])} | {m['op']} {m['threshold']} | {st} |")
    L += ["", f"Дашборд: `{png.relative_to(LAB)}`", "", "## Деталі порушень", ""]
    for m in res["metrics"]:
        d = m["details"]
        if m["pass"] is False or m["pass"] is None:
            L.append(f"**{m['id']}** — " + json.dumps({k: v for k, v in d.items() if k != "pairs"}, ensure_ascii=False)[:900])
            if d.get("pairs"):
                L.append("Пари майже-дублікатів (containment 5-грам): " + "; ".join(f"{a} ~ {b} ({c})" for a, b, c in d["pairs"][:12]))
            L.append("")
    ri = res.get("rag_indicators") or {}
    if ri:
        L += ["## Індикатори впливу на RAG (baseline ЛР11)", "",
              f"- Запитів: {ri['queries']}; слотів топ-k: {ri['topk_slots']}; частка слотів, зайнятих звітом prj09: {ri['share_slots_prj09']}.",
              f"- Запитів, де ≥ 3 з 5 фрагментів з одного документа: {ri['queries_with_3plus_from_one_doc']}.", ""]
        L += priorities(res)
    path = QUALITY / f"profile_{res['tag']}.md"
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"→ {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="baseline")
    ap.add_argument("--version", default=None)
    ap.add_argument("--store", default=str(DATA / "store"))
    ap.add_argument("--corpus", default=str(DATA / "corpus" / "docs.jsonl"))
    ap.add_argument("--shapes", default=None, help="додаткові SHACL-форми (Р4: quality/shapes.ttl)")
    ap.add_argument("--ref-date", default=None)
    run(ap.parse_args())
