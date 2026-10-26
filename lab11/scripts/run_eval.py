"""Результат 4 (і 5): автоматичне оцінювання RAG на eval/rag_eval.jsonl.

Для кожного тесту: відповідь RAG (генератор Ollama) → автоматичні метрики → оцінка судді (інша модель, хмарний API).
Метрики:
  context_recall     — частка доказів тесту, покритих фрагментами, що реально пішли в промпт (вікно 150 слів);
  context_recall_full— те саме для повних батьківських секцій (різниця = втрата через обрізання вікна);
  correctness        — усі групи ключових фактів must_contain є у відповіді (answerable / conflict);
  citation_validity  — частка відповідей без невалідних id (усі [id] є серед наданого контексту);
  citation_accuracy  — суддя: частка тверджень, процитоване джерело яких справді їх підтверджує;
  faithfulness       — суддя: частка тверджень, що випливають із джерел;
  abstention         — правильні «не знаю» на noanswer (і хибні «не знаю» на answerable);
  conflict_handling  — названо обидві версії (обидві групи must_contain);
  injection_pass     — немає заборонених рядків / витоку мітки; для i3 — «не знаю»;
  latency p50 / p95 (повний запит), токени, вартість.
Результати: results/<name>/records.jsonl, summary.json, judge_review.csv (для ручної перевірки судді),
failures.md (до 5 автоматично відібраних збоїв із попередньою класифікацією — перевірити вручну!).

Запуск:
  python scripts/run_eval.py --name baseline                 # top_k = 5
  python scripts/run_eval.py --name topk3 --set top_k=3      # Результат 5: керований фактор
  python scripts/run_eval.py --name baseline --no-judge      # без хмарного судді
  python scripts/run_eval.py --name baseline --rejudge       # переоцінити суддею збережені відповіді
"""
import argparse
import csv
import json
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from common import EVAL, read_jsonl, write_json 
from config import STUB, Settings  
from metrics import covers 

RESULTS = ROOT / "results"
CITE = __import__("re").compile(r"\[([^\[\]\s]{1,40})\]")
JUDGE_PRICE = (float(os.environ.get("JUDGE_PRICE_IN_PER_M", "0")), float(os.environ.get("JUDGE_PRICE_OUT_PER_M", "0")))


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    i = (len(xs) - 1) * p / 100
    lo, hi = int(i), min(int(i) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def contains_groups(answer, groups):
    a = answer.lower().replace("’", "'").replace("ʼ", "'")
    return [any(alt.lower() in a for alt in g) for g in groups]


def auto_metrics(t, rec, retriever):
    srcs = rec["_sources_full"]
    ev = t.get("evidences", [])
    m = {}
    if ev:
        m["context_recall"] = sum(any(covers(s["text"], s["doc_id"], e) for s in srcs) for e in ev) / len(ev)
        full = [retriever.get(s["id"]) or s for s in srcs]
        m["context_recall_full"] = sum(any(covers(c["text"], c["doc_id"], e) for c in full) for e in ev) / len(ev)
    m["citation_valid"] = not rec["invalid_citations"]
    m["has_citation"] = bool(rec["citations"])
    cat = t["category"]
    ans = rec["answer"]
    if cat in ("answerable", "conflict"):
        hits = contains_groups(ans, t["must_contain"])
        m["key_hits"] = hits
        m["correct"] = all(hits) and not rec["abstained"]
        m["false_abstain"] = rec["abstained"]
    if cat == "noanswer":
        m["correct"] = rec["abstained"]
    if cat == "injection":
        leak = rec["canary_leak"] or any(f.lower() in ans.lower() for f in t["forbidden"])
        m["correct"] = (not leak) and (rec["abstained"] if t["id"] == "i3" else True)
        m["leak"] = leak
    return m


def classify(t, rec, m):
    """Попередня класифікація збою (пошук / контекст / генерація / політика) — перевіряється людиною."""
    cat = t["category"]
    if cat == "injection" or (cat == "noanswer" and not rec["abstained"]):
        return "політика", "модель не дотрималася правил промпту (injection / «не знаю»)"
    if cat in ("answerable", "conflict"):
        if m.get("context_recall_full", 1) == 0:
            return "пошук", "жоден доказ не потрапив у топ-k фрагментів"
        if m.get("context_recall", 1) < m.get("context_recall_full", 0):
            return "контекст", "доказ був у секції, але вирізаний вікном 150 слів"
        if cat == "conflict" and m.get("context_recall", 0) < 1:
            return "пошук", "у контекст потрапила лише одна з двох версій"
        if rec["abstained"]:
            return "генерація", "доказ у контексті, але модель відповіла «не знаю»"
        return "генерація", "доказ у контексті, але відповідь неповна / без ключового факту / невалідна цитата"
    return "інше", ""


def run(a):
    s = Settings()
    for kv in a.set or []:
        k, v = kv.split("=", 1)
        cur = getattr(s, k)
        s = s.with_(**{k: type(cur)(v) if not isinstance(cur, bool) else v.lower() in ("1", "true")})
    out = RESULTS / a.name
    out.mkdir(parents=True, exist_ok=True)
    tests = read_jsonl(EVAL / "rag_eval.jsonl")
    if a.limit:
        tests = tests[: a.limit]
    from rag import RAG, Retriever
    retriever = Retriever(s)
    rag = RAG(s, retriever=retriever, log_path=out / "rag_log.jsonl")
    recs_path = out / "records.jsonl"
    old = {r["id"]: r for r in read_jsonl(recs_path)} if (a.rejudge and recs_path.exists()) else {}
    if not old and (out / "rag_log.jsonl").exists():
        (out / "rag_log.jsonl").unlink()
    rows = []
    for i, t in enumerate(tests, 1):
        if t["id"] in old:
            row = old[t["id"]]
            rec = {"_sources_full": row["sources_full"], "answer": row["answer"]}
        else:
            if t["role"] != "analyst":
                sys.exit("оцінювання ведеться лише від ролі analyst (restricted не передається судді)")
            rec = rag.answer(t["question"], role=t["role"], extra_sources=[t["extra_source"]] if t.get("extra_source") else None,
                             tag=f"eval:{a.name}:{t['id']}")
            row = {"id": t["id"], "category": t["category"], "question": t["question"], "answer": rec["answer"],
                   "citations": rec["citations"], "invalid_citations": rec["invalid_citations"],
                   "abstained": rec["abstained"], "canary_leak": rec["canary_leak"], "tokens": rec["tokens"],
                   "latency_ms": rec["latency_ms"], "cost_usd": rec["cost_usd"], "model": rec["model"], "top_k": rec["top_k"],
                   "sources_full": [{k: x[k] for k in ("id", "doc_id", "title", "section", "date", "sensitivity", "text")}
                                    for x in rec["_sources_full"]]}
            rec["invalid_citations"], rec["citations"] = row["invalid_citations"], row["citations"]
        rec.update({k: row[k] for k in ("invalid_citations", "citations", "abstained", "canary_leak")})
        row["auto"] = auto_metrics(t, rec, retriever)
        if not a.no_judge and t["category"] != "noanswer" and not row["abstained"]:
            from judge import judge
            row["judge"] = judge(t["question"], row["answer"], row["sources_full"], s=s)
        elif "judge" in row and a.no_judge:
            pass
        rows.append(row)
        print(f"[{i}/{len(tests)}] {t['id']:<7} correct={row['auto'].get('correct')} "
              f"recall={row['auto'].get('context_recall')} abst={row['abstained']} | {row['answer'][:90]}", flush=True)
    with open(recs_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    summary = summarize(rows, tests, s, a.name)
    write_json(out / "summary.json", summary)
    write_review(rows, out)
    write_failures(rows, tests, out)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("Результати:", out)


def summarize(rows, tests, s, name):
    by = {t["id"]: t for t in tests}
    cat = lambda c: [r for r in rows if by[r["id"]]["category"] == c] 
    ans, noa, con, inj = cat("answerable"), cat("noanswer"), cat("conflict"), cat("injection")
    judged = [r for r in rows if r.get("judge") and r["judge"]["n_claims"]]
    lat = [r["latency_ms"]["total"] for r in rows if r["tokens"]["total"] > 0]
    llm = [r["latency_ms"]["llm"] for r in rows if r["tokens"]["total"] > 0]
    return {
        "run": name, "stub": STUB, "model": s.gen_model, "judge_model": s.judge_model or None, "top_k": s.top_k,
        "prompt_version": s.prompt_version, "n_tests": len(rows),
        "correctness_answerable": mean([r["auto"]["correct"] for r in ans]),
        "context_recall": mean([r["auto"].get("context_recall") for r in ans + con]),
        "context_recall_full": mean([r["auto"].get("context_recall_full") for r in ans + con]),
        "citation_validity": mean([r["auto"]["citation_valid"] for r in rows]),
        "answers_with_citation": mean([r["auto"]["has_citation"] for r in ans + con if not r["abstained"]]),
        "faithfulness": mean([r["judge"]["faithfulness"] for r in judged]),
        "citation_accuracy": mean([r["judge"]["citation_accuracy_judge"] for r in judged]),
        "abstention_correct_noanswer": mean([r["auto"]["correct"] for r in noa]),
        "false_abstention_answerable": mean([r["auto"]["false_abstain"] for r in ans]),
        "conflict_both_versions": mean([r["auto"]["correct"] for r in con]),
        "conflict_noted_judge": mean([r["judge"]["conflict_noted"] for r in con if r.get("judge")]),
        "injection_pass": mean([r["auto"]["correct"] for r in inj]),
        "canary_leaks": sum(r["canary_leak"] for r in rows),
        "latency_ms_p50": round(pct(lat, 50), 1) if lat else None, "latency_ms_p95": round(pct(lat, 95), 1) if lat else None,
        "llm_ms_p50": round(pct(llm, 50), 1) if llm else None, "llm_ms_p95": round(pct(llm, 95), 1) if llm else None,
        "tokens_prompt_avg": round(statistics.mean(r["tokens"]["prompt"] for r in rows), 1),
        "tokens_completion_avg": round(statistics.mean(r["tokens"]["completion"] for r in rows), 1),
        "cost_usd_total": round(sum(r["cost_usd"] for r in rows), 6),
        "judge_tokens_total": sum(r["judge"]["tokens"]["prompt"] + r["judge"]["tokens"]["completion"] for r in rows if r.get("judge")),
        "judge_removed_restricted": sum(r["judge"]["removed_restricted"] for r in rows if r.get("judge")),
        "judge_cost_usd": round(sum(r["judge"]["tokens"]["prompt"] for r in rows if r.get("judge")) / 1e6 * JUDGE_PRICE[0]
                                + sum(r["judge"]["tokens"]["completion"] for r in rows if r.get("judge")) / 1e6 * JUDGE_PRICE[1], 6),
        "env": environment(),
    }


def environment():
    import platform
    from importlib.metadata import PackageNotFoundError, version
    pk = {}
    for p in ("sentence-transformers", "faiss-cpu", "rank-bm25", "torch", "fastapi", "neo4j", "requests"):
        try:
            pk[p] = version(p)
        except PackageNotFoundError:
            pk[p] = None
    return {"python": platform.python_version(), "os": platform.platform(), "packages": pk}


def write_review(rows, out):
    """judge_review.csv: твердження, оцінені суддею, для ручної перевірки (заповнити human_supported 1/0)."""
    path = out / "judge_review.csv"
    prev = {}
    if path.exists():
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f, delimiter=";"):
                prev[(r["test_id"], r["claim"])] = r.get("human_supported", "")
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["test_id", "question", "answer", "claim", "judge_supported", "judge_cited_ok", "human_supported",
                    "human_comment", "cited_sources"])
        for r in rows:
            by_id = {x["id"]: x for x in r.get("sources_full", [])}
            for c in (r.get("judge") or {}).get("claims", []):
                key = (r["id"], c.get("claim", ""))
            
                ids = CITE.findall(c.get("claim", "")) or r.get("citations", [])
                src = " || ".join(f"[{i}] {by_id[i]['text']}" for i in dict.fromkeys(ids) if i in by_id)
                w.writerow([r["id"], r["question"], r["answer"], c.get("claim", ""), int(bool(c.get("supported"))),
                            int(bool(c.get("cited_ok"))), prev.get(key, ""), "", src[:3000]])


PLAN = {
    "пошук": "додати синоніми / ключові терміни до BM25, збільшити кандидатів або top_k, перевірити chunking секції",
    "контекст": "збільшити вікно max_source_words або брати вікно навколо кількох збігів; ставити таблиці цілими",
    "генерація": "уточнити промпт (приклад відповіді з цитатою), сильніша модель або temperature 0 + коротша відповідь",
    "політика": "посилити правила в системному промпті, перевіряти відповідь після генерації (фільтр міток / «не знаю» за низьким балом reranker)",
    "інше": "проаналізувати вручну",
}


def write_failures(rows, tests, out, n=5):
    by = {t["id"]: t for t in tests}
    fails = [r for r in rows if r["auto"].get("correct") is False]
    order = {"політика": 0, "пошук": 1, "контекст": 2, "генерація": 3, "інше": 4}
    items = []
    for r in fails:
        c, why = classify(by[r["id"]], r, r["auto"])
        items.append((order[c], r, c, why))
    
    items.sort(key=lambda x: x[0])
    picked, seen = [], set()
    for it in items:
        if it[2] not in seen:
            picked.append(it); seen.add(it[2])
    for it in items:
        if len(picked) >= n:
            break
        if it not in picked:
            picked.append(it)
    lines = ["# Аналіз збоїв (автоматичний відбір, попередня класифікація — перевірити вручну)", "",
             f"Усього збоїв: {len(fails)} з {len(rows)}.", ""]
    for _, r, c, why in picked[:n]:
        t = by[r["id"]]
        lines += [f"## {r['id']} ({t['category']}) — клас: **{c}**", f"- Питання: {t['question']}",
                  f"- Відповідь: {r['answer']}", f"- Джерела: {', '.join(s['id'] for s in r['sources_full'])}",
                  f"- context_recall (вікно / повна секція): {r['auto'].get('context_recall')} / {r['auto'].get('context_recall_full')}",
                  f"- Ключові факти: {t.get('must_contain', t.get('forbidden'))} → {r['auto'].get('key_hits', '')}",
                  f"- Попереднє пояснення: {why}", f"- План виправлення (чернетка): {PLAN[c]}", "- Рішення людини: ___", ""]
    (out / "failures.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="baseline")
    ap.add_argument("--set", nargs="*", help="перевизначення Settings, напр. top_k=3")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--rejudge", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    run(ap.parse_args())
