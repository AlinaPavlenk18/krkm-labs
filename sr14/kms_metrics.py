"""8 метрик якості й використання знань KMS «Прогнозування енергоспоживання» + пороги для 2 сценаріїв.

Заміри (версії сховища ЛР14 і прогони RAG на них):
  baseline — ../lab14/data        + RAG ЛР11  (../lab14/data/rag_baseline/records.jsonl)
  after    — ../lab14/data_after  + RAG ЛР14  (../lab14/results/rag_after/records.jsonl)

  python kms_metrics.py --tag baseline
  python kms_metrics.py --tag after
  python kms_metrics.py --report          # таблиця results/metrics.md + дашборд і тренд results/dashboard.png
Кожен замір дописується в results/history.csv (дата, тег, хеш знімка) — це і є тренд.
"""
import argparse
import csv
import hashlib
import json
import math
import sys
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB14 = HERE.parent / "lab14"
sys.path.insert(0, str(LAB14 / "quality"))
from common import load_graph, read_jsonl, sections, shingles  
from conflicts import unresolved_value_conflicts                 

RES = HERE / "results"
HIST = RES / "history.csv"
REF = date(2026, 11, 7)
VERSIONS = {"baseline": (LAB14 / "data", LAB14 / "data" / "rag_baseline" / "records.jsonl"),
            "after": (LAB14 / "data_after", LAB14 / "results" / "rag_after" / "records.jsonl")}

# id, вимір, формула; поріг (чат підтримки, аудит)
METRICS = [
    ("M1", "повнота", "1 − відсутні обов'язкові зв'язки / усі обов'язкові слоти", 0.98, 1.00),
    ("M2", "узгодженість", "1 − величини з нерозв'язаними розбіжностями / усі величини корпусу", 0.95, 1.00),
    ("M3", "точність", "нижня межа Вілсона 95 % для частки правильних у вибірці n = 30", 0.85, 0.95),
    ("M4", "актуальність", "моделі з (дата відліку − trainingDate) ≤ 365 дн. / усі моделі", 1.00, 0.60),
    ("M5", "унікальність", "1 − секції з майже-дублікатом (5-грами, containment ≥ 0,5) / усі секції", 0.97, 0.99),
    ("M6", "походження", "записи з повним provenance (вузол: source; зв'язок: source, confidence, validFrom; документ: url, ліцензія, походження, дата) / усі", 0.95, 1.00),
    ("M7", "використання", "документи, на які RAG послався хоча б раз / доступні ролі analyst документи", 0.50, 0.30),
    ("M8", "довіра до відповідей", "відповіді з ≥ 1 посиланням, усі посилання валідні / усі відповіді, крім «Не знаю»", 0.90, 0.98),
]
OPS = {k: ">=" for k, *_ in METRICS}


def m1(store):
    nodes, rels = load_graph(store)
    out, inn = set(), set()
    for t, rows in rels.items():
        for r in rows:
            out.add((r["start"], t)); inn.add((r["end"], t))
    req = [("substation", "LOCATED_IN", out), ("substation", "MANAGES", inn), ("consumer", "HAS_METER", out),
           ("consumer", "CONNECTED_TO", out), ("meter", "HAS_METER", inn), ("measurement", "RECORDED", inn),
           ("forecast", "GENERATED", inn), ("forecast", "FORECAST_FOR", out)]
    slots = [(n["id"], t, s) for lab, t, s in req for n in nodes[lab]]
    miss = sum((i, t) not in s for i, t, s in slots)
    return 1 - miss / len(slots), f"відсутніх {miss} з {len(slots)}"


def m2(docs):
    n, _, _, unresolved = unresolved_value_conflicts(docs)
    return 1 - len(unresolved) / n, f"нерозв'язаних {len(unresolved)} з {n}"


def m3():
    rows = list(csv.DictReader(open(LAB14 / "quality" / "accuracy_sample.csv", encoding="utf-8-sig"), delimiter=";"))
    n, k, z = len(rows), sum(r["expert_ok"].strip() == "1" for r in rows), 1.96
    p = k / n
    lb = (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)
    return lb, f"{k}/{n} правильних, p̂ = {p:.3f}"


def m4(store):
    nodes, _ = load_graph(store)
    ms = nodes["forecastmodel"]
    fresh = sum((REF - date.fromisoformat(m["trainingDate"])).days <= 365 for m in ms)
    return fresh / len(ms), f"актуальних {fresh} з {len(ms)}"


def m5(docs):
    secs = [(d["doc_id"], s) for d, _, _, x in sections(docs) if len(s := shingles(x)) >= 10]
    dup = set()
    for i in range(len(secs)):
        for j in range(i + 1, len(secs)):
            (da, a), (db, b) = secs[i], secs[j]
            if da != db and len(a & b) / min(len(a), len(b)) >= 0.5:
                dup |= {i, j}
    return 1 - len(dup) / len(secs), f"з дублікатом {len(dup)} з {len(secs)}"


def m6(store, docs):
    nodes, rels = load_graph(store)
    recs = [bool(n.get("source")) for rows in nodes.values() for n in rows]
    recs += [all(r.get(k) for k in ("source", "confidence", "validFrom")) for rows in rels.values() for r in rows]
    recs += [all(d.get(k) for k in ("source_url", "license", "origin", "date")) for d in docs]
    return sum(recs) / len(recs), f"повних {sum(recs)} з {len(recs)}"


def m7(docs, recs):
    allowed = {d["doc_id"] for d in docs if d["sensitivity"] in ("public", "internal")}
    cited = {c.split("#")[0] for r in recs for c in r["citations"]} & allowed
    return len(cited) / len(allowed), f"процитовано {len(cited)} з {len(allowed)}"


def m8(recs):
    ans = [r for r in recs if not r["abstained"]]
    ok = sum(r["auto"].get("has_citation") and r["auto"].get("citation_valid") for r in ans)
    return ok / len(ans), f"{ok} з {len(ans)} відповідей"


def measure(tag):
    base, rag = VERSIONS[tag]
    store, docs, recs = base / "store", read_jsonl(base / "corpus" / "docs.jsonl"), read_jsonl(rag)
    vals = {"M1": m1(store), "M2": m2(docs), "M3": m3(), "M4": m4(store), "M5": m5(docs),
            "M6": m6(store, docs), "M7": m7(docs, recs), "M8": m8(recs)}
    h = hashlib.sha256((base / "corpus" / "docs.jsonl").read_bytes() + Path(rag).read_bytes()).hexdigest()[:12]
    RES.mkdir(exist_ok=True)
    new = not HIST.exists()
    with open(HIST, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["ts", "tag", "hash"] + [m[0] for m in METRICS])
        w.writerow([datetime.now().isoformat(timespec="seconds"), tag, h] + [round(vals[m[0]][0], 4) for m in METRICS])
    (RES / f"details_{tag}.json").write_text(json.dumps({k: {"value": round(v, 4), "detail": d} for k, (v, d) in vals.items()},
                                                        ensure_ascii=False, indent=1), encoding="utf-8")
    for mid, dim, *_ in METRICS:
        v, d = vals[mid]
        print(f"{mid} {dim:<22} {v:.4f}   {d}")


def report():
    rows = list(csv.DictReader(open(HIST, encoding="utf-8")))
    last = {}
    for r in rows:
        last[r["tag"]] = r                                   
    tags = [t for t in ("baseline", "after") if t in last]
    L = ["| Метрика | Вимір | " + " | ".join(tags) + " | Поріг: чат | Поріг: аудит |", "|---" * (4 + len(tags)) + "|"]
    for mid, dim, _, chat, audit in METRICS:
        cells = []
        for t in tags:
            v = float(last[t][mid])
            cells.append(f"{v:.4f} {'✓' if v >= chat else '✗'}{'✓' if v >= audit else '✗'}")
        L.append(f"| {mid} | {dim} | " + " | ".join(cells) + f" | ≥ {chat} | ≥ {audit} |")
    L.append("\n✓/✗ — виконано поріг чату / аудиту.")
    (RES / "metrics.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4), dpi=150, gridspec_kw={"width_ratios": [3, 2]})
    x = range(len(METRICS))
    w = 0.38
    for k, t in enumerate(tags):
        a1.bar([i + (k - 0.5) * w for i in x], [float(last[t][m[0]]) for m in METRICS], w, label=t)
    a1.scatter(list(x), [m[3] for m in METRICS], marker="_", s=300, color="black", label="поріг: чат", zorder=3)
    a1.scatter(list(x), [m[4] for m in METRICS], marker="x", s=30, color="red", label="поріг: аудит", zorder=3)
    a1.set_xticks(list(x), [f"{m[0]}\n{m[1]}" for m in METRICS], fontsize=7)
    a1.set_ylim(0, 1.08)
    a1.set_title("Метрики якості KMS: останній замір кожної версії", fontsize=9)
    a1.legend(fontsize=7, loc="lower left")
    for m in METRICS:
        a2.plot(range(len(rows)), [float(r[m[0]]) for r in rows], marker="o", label=m[0])
    a2.set_xticks(range(len(rows)), [f"{r['tag']}\n{r['ts'][5:16]}" for r in rows], fontsize=7)
    a2.set_title("Тренд (усі заміри history.csv)", fontsize=9)
    a2.legend(fontsize=6, ncol=2)
    plt.tight_layout()
    plt.savefig(RES / "dashboard.png")
    print((RES / "metrics.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", choices=list(VERSIONS))
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.tag:
        measure(a.tag)
    if a.report:
        report()
