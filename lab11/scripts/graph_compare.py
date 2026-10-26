"""Результат 2: порівняння «лише текст» vs «текст + граф» на запитах про зв'язки між сутностями.

1. Будує eval/graph_questions.jsonl: 12 питань про зв'язки (живлення, керування, підключення, прогнози, каскад);
   очікувані сутності обчислюються з графа (CSV-експорт ЛР9 = те саме, що в Neo4j), а не вписуються вручну.
2. Проганяє кожне питання в двох режимах RAG (mode = text і text+graph), ролі analyst.
3. Метрики: key_recall — частка очікуваних сутностей, названих у відповіді; correct — названо всі;
   linking — чи знайшов entity linking потрібну стартову сутність; graph_cited — відповідь цитує факти [gN];
   explainable — для кожної названої очікуваної сутності є процитований факт графа, що її містить (шлях видно);
   citation_validity, токени, затримка.
Вихід: results/graph_compare/records.jsonl, summary.json і docs/graph_vs_text_table.md (таблиця для звіту).
Запуск: python scripts/graph_compare.py   (GRAPH_BACKEND=neo4j — з Neo4j; csv — з файлів)
"""
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from common import EVAL, write_json, write_jsonl  
from config import Settings  
from graph_context import CsvGraph  

OUT = ROOT / "results" / "graph_compare"


def out_edges(g, nid, t):
    return sorted(e[2] for e in g.incident(nid) if e[1] == t and e[0] == nid)


def in_edges(g, nid, t):
    return sorted(e[0] for e in g.incident(nid) if e[1] == t and e[2] == nid)


def build_questions(g):
    n = g.all_nodes()
    q = []

    def add(qid, text, seed, expected, kind):
        q.append({"id": qid, "question": text, "seed": seed, "expected": expected, "kind": kind})
    add("g01", "Які підстанції напряму живить підстанція №1?", "Substation_1", out_edges(g, "Substation_1", "FEEDS"), "1 крок")
    add("g02", "Від якої підстанції живиться підстанція №10?", "Substation_10", in_edges(g, "Substation_10", "FEEDS"), "1 крок")
    two = sorted({c for b in out_edges(g, "Substation_1", "FEEDS") for c in out_edges(g, b, "FEEDS")})
    add("g03", "Які підстанції постраждають через дві ланки живлення, якщо відключити підстанцію №1?", "Substation_1", two, "2 кроки")
    add("g04", "Якими підстанціями керує диспетчер №1?", "Dispatcher_1", out_edges(g, "Dispatcher_1", "MANAGES"), "1 крок")
    add("g05", "Який диспетчер керує підстанцією №7?", "Substation_7", in_edges(g, "Substation_7", "MANAGES"), "1 крок")
    add("g06", "До якої підстанції підключено споживача №3310?", "Consumer_3310", out_edges(g, "Consumer_3310", "CONNECTED_TO"), "1 крок")
    add("g07", "Які споживачі підключені до підстанції №5?", "Substation_5", in_edges(g, "Substation_5", "CONNECTED_TO"), "1 крок")
    add("g08", "Яка модель склала прогноз на 24.09.2026 і для якої підстанції?", "Forecast_20260924",
        in_edges(g, "Forecast_20260924", "GENERATED") + out_edges(g, "Forecast_20260924", "FORECAST_FOR"), "1 крок, 2 зв'язки")
    add("g09", "Які погодні умови впливали на модель LSTM №2?", "ForecastModel_LSTM2", in_edges(g, "ForecastModel_LSTM2", "AFFECTS_MODEL"), "1 крок")
    add("g10", "Який лічильник встановлено у споживача №1002?", "Consumer_1002", out_edges(g, "Consumer_1002", "HAS_METER"), "1 крок")
    disp = sorted({d for s in out_edges(g, "Dispatcher_1", "MANAGES") for d in in_edges(g, s, "CONNECTED_TO")})
    add("g11", "Яких споживачів обслуговують підстанції, якими керує диспетчер №1?", "Dispatcher_1", disp, "2 кроки")
    add("g12", "Хто з диспетчерів керує підстанцією №9?", "Substation_9", in_edges(g, "Substation_9", "MANAGES") or ["NONE"], "1 крок (немає)")
    for x in q:
        for e in x["expected"]:
            assert e == "NONE" or e in n, e
    return q


def key_regex(nid):
    """Як очікувана сутність може бути названа у відповіді."""
    if nid == "NONE":
        return r"(?:немає|не має|не призначен|жоден)"
    lab, num = nid.split("_", 1)
    if lab == "Substation":
        return rf"(?:№|#|n|substation_)\s*{num}(?!\d)"
    if lab == "Dispatcher":
        return rf"(?:диспетчер\w*\s*(?:№|#)?\s*{num}(?!\d)|dispatcher_{num}(?!\d))"
    if lab == "Consumer":
        return rf"{num}(?!\d)"
    if lab == "Meter":
        return rf"{num.replace('AMI', '')}(?!\d)"
    if lab == "ForecastModel":
        base, k = re.match(r"([A-Z]+)(\d+)", num).groups()
        return rf"{base}\s*(?:№|#)?\s*{k}(?!\d)"
    if lab in ("WeatherCondition", "Forecast"):
        y, m, d = num[:4], num[4:6], num[6:8]
        return rf"(?:{d}\.{m}\.{y}|{nid})"
    return re.escape(nid)


def evaluate(qq, rec):
    ans = rec["answer"]
 
    hits = [bool(re.search(key_regex(e), ans, re.I)) and not (e == "NONE" and rec["abstained"]) for e in qq["expected"]]
    facts = {f["id"]: f for f in rec["_graph_full"]["facts"]}
    cited_facts = [facts[c] for c in rec["citations"] if c in facts]
    explain = [any(e in (f["start"], f["end"]) for f in cited_facts) for e, h in zip(qq["expected"], hits) if h and e != "NONE"]
    return {
        "key_recall": sum(hits) / len(hits), "correct": all(hits) and not (rec["abstained"] and qq["expected"] != ["NONE"]),
        "linking": qq["seed"] in [e["id"] for e in rec["graph"]["entities"]] if rec["mode"] == "text+graph" else None,
        "graph_cited": bool(cited_facts), "explainable": (all(explain) if explain else False) if rec["mode"] == "text+graph" else None,
        "citation_valid": not rec["invalid_citations"], "abstained": rec["abstained"],
    }


def main():
    from graph_context import GraphContext
    from rag import RAG
    s = Settings()
    gc = GraphContext(hops=s.graph_hops, max_facts=s.graph_max_facts)
    questions = build_questions(CsvGraph())
    write_jsonl(EVAL / "graph_questions.jsonl", questions)
    OUT.mkdir(parents=True, exist_ok=True)
    rag = RAG(s, graph=gc, log_path=OUT / "rag_log.jsonl")
    rows = []
    for qq in questions:
        for mode in ("text", "text+graph"):
            rec = rag.answer(qq["question"], role="analyst", mode=mode, tag=f"graph_compare:{qq['id']}")
            m = evaluate(qq, rec)
            rows.append({"id": qq["id"], "mode": mode, "question": qq["question"], "expected": qq["expected"], "answer": rec["answer"],
                         "citations": rec["citations"], "entities": rec["graph"]["entities"], "n_facts": len(rec["graph"]["facts"]),
                         "tokens": rec["tokens"], "latency_ms": rec["latency_ms"], **m})
            print(f"{qq['id']} {mode:<10} recall={m['key_recall']:.2f} correct={m['correct']} | {rec['answer'][:100]}", flush=True)
    write_jsonl(OUT / "records.jsonl", rows)
    summ = {}
    for mode in ("text", "text+graph"):
        r = [x for x in rows if x["mode"] == mode]
        summ[mode] = {
            "n": len(r), "correct": round(statistics.mean(x["correct"] for x in r), 3),
            "key_recall": round(statistics.mean(x["key_recall"] for x in r), 3),
            "graph_cited": round(statistics.mean(x["graph_cited"] for x in r), 3),
            "explainable": round(statistics.mean(bool(x["explainable"]) for x in r), 3) if mode == "text+graph" else None,
            "linking": round(statistics.mean(bool(x["linking"]) for x in r), 3) if mode == "text+graph" else None,
            "citation_validity": round(statistics.mean(x["citation_valid"] for x in r), 3),
            "abstained": sum(x["abstained"] for x in r),
            "tokens_prompt_avg": round(statistics.mean(x["tokens"]["prompt"] for x in r), 1),
            "latency_ms_p50": round(statistics.median(x["latency_ms"]["total"] for x in r), 1),
            "graph_ms_avg": round(statistics.mean(x["latency_ms"]["graph"] for x in r), 1),
        }
    summ["backend"] = gc.graph.name
    write_json(OUT / "summary.json", summ)
    t, g = summ["text"], summ["text+graph"]
    lines = ["| Метрика | Лише текст | Текст + граф |", "|---|---|---|"]
    for k, title in [("correct", "Повністю правильні відповіді"), ("key_recall", "Повнота сутностей (key recall)"),
                     ("graph_cited", "Цитують факти графа [gN]"), ("explainable", "Пояснюваність (шлях процитовано)"),
                     ("linking", "Entity linking знайшов сутність"), ("citation_validity", "Валідність цитат"),
                     ("abstained", "Відповідей «не знаю»"), ("tokens_prompt_avg", "Токени промпту (сер.)"),
                     ("latency_ms_p50", "Затримка p50, мс"), ("graph_ms_avg", "Час побудови підграфа, мс")]:
        lines.append(f"| {title} | {t[k] if t[k] is not None else '—'} | {g[k] if g[k] is not None else '—'} |")
    lines += ["", "| Питання | Очікувано | Текст: recall | Текст+граф: recall |", "|---|---|---|---|"]
    for qq in questions:
        a = next(x for x in rows if x["id"] == qq["id"] and x["mode"] == "text")
        b = next(x for x in rows if x["id"] == qq["id"] and x["mode"] == "text+graph")
        lines.append(f"| {qq['id']}. {qq['question']} | {', '.join(qq['expected'])} | {a['key_recall']:.2f} | {b['key_recall']:.2f} |")
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "graph_vs_text_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
