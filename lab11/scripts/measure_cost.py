"""Результат 5, крок 3: точні токени промпту і контрольований вимір затримки top_k = 5 vs top_k = 3.

Чому окремо від run_eval.py:
  * prompt_eval_count Ollama не дорівнює розміру промпту: Ollama повторно використовує KV-кеш спільного префікса
    (системний промпт) з попереднім запитом і рахує лише нові токени, тому числа «стрибають»;
  * прогони baseline і topk3 виконувались у різний час і з паузами (сон ПК, інші задачі), тож їхні p50/p95
    відображають стан комп'ютера, а не лише top_k.
Що робить:
  1) tokens — відтворює кожен промпт із results/<run>/records.jsonl (ті самі джерела й питання) і рахує токени
     токенізатором Qwen2.5 із шаблоном чату (точний розмір промпту, однаковий спосіб для обох прогонів);
  2) bench — на 10 тестах по черзі запускає top_k = 5 і top_k = 3 (порядок чергується: 5→3, 3→5, …), без судді,
     після одного розігрівного запиту; так обидві конфігурації вимірюються в однакових умовах.
Вихід: results/latency_bench/{bench.jsonl, summary.json}, docs/cost_latency_table.md.
Запуск: python scripts/measure_cost.py            (обидва кроки; ≈ 20–40 хв на CPU)
        python scripts/measure_cost.py --skip-bench
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from common import EVAL, read_jsonl, write_json  
from config import Settings  
from rag import CANARY, format_context, load_prompt  

BENCH_IDS = ["a_q01", "a_q05", "a_q11", "a_q15", "a_q17", "a_q21", "a_q27", "a_q36", "n1", "c2"]
TOKENIZER = "Qwen/Qwen2.5-7B-Instruct"     


def pct(xs, p):
    xs = sorted(xs)
    i = (len(xs) - 1) * p / 100
    lo, hi = int(i), min(int(i) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def count_tokens(runs):
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(TOKENIZER)
    system, tpl = load_prompt("rag_v1")
    system = system.replace("{canary}", CANARY)
    res = {}
    for run in runs:
        n = []
        for r in read_jsonl(ROOT / "results" / run / "records.jsonl"):
            user = tpl.replace("{context}", format_context(r["sources_full"]) or "(джерел немає)").replace("{question}", r["question"])
            ids = tok.apply_chat_template([{"role": "system", "content": system}, {"role": "user", "content": user}],
                                          tokenize=True, add_generation_prompt=True)
            if not isinstance(ids, list):            
                ids = ids["input_ids"]
            if ids and isinstance(ids[0], list):
                ids = ids[0]
            n.append(len(ids))
        res[run] = {"mean": round(statistics.mean(n), 1), "median": statistics.median(n), "min": min(n), "max": max(n),
                    "system_tokens": len(tok(system)["input_ids"])}
    return res


def bench(n_rounds):
    from rag import RAG
    s = Settings()
    rag = RAG(s)
    tests = {t["id"]: t for t in read_jsonl(EVAL / "rag_eval.jsonl")}
    out_dir = ROOT / "results" / "latency_bench"
    out_dir.mkdir(parents=True, exist_ok=True)
    rag.answer(tests["a_q01"]["question"], role="analyst", top_k=5, log=False)         
    rows = []
    for rnd in range(n_rounds):
        for i, tid in enumerate(BENCH_IDS):
            order = (5, 3) if (i + rnd) % 2 == 0 else (3, 5)
            for k in order:
                r = rag.answer(tests[tid]["question"], role="analyst", top_k=k, log=False)
                row = {"id": tid, "top_k": k, "round": rnd, "llm_ms": r["latency_ms"]["llm"], "total_ms": r["latency_ms"]["total"],
                       "retrieval_ms": r["latency_ms"]["retrieval"], "ollama_prompt_tokens": r["tokens"]["prompt"],
                       "completion_tokens": r["tokens"]["completion"], "answer": r["answer"]}
                rows.append(row)
                print(f"{tid:<6} top_k={k}  llm {row['llm_ms'] / 1000:7.1f} с  total {row['total_ms'] / 1000:7.1f} с", flush=True)
    with open(out_dir / "bench.jsonl", "w", encoding="utf-8") as f:
        for x in rows:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    summ = {"model": s.gen_model, "n_per_config": len(rows) // 2}
    for k in (5, 3):
        xs = [x for x in rows if x["top_k"] == k]
        summ[f"top_k={k}"] = {
            "llm_p50_s": round(pct([x["llm_ms"] for x in xs], 50) / 1000, 1), "llm_p95_s": round(pct([x["llm_ms"] for x in xs], 95) / 1000, 1),
            "total_p50_s": round(pct([x["total_ms"] for x in xs], 50) / 1000, 1), "total_p95_s": round(pct([x["total_ms"] for x in xs], 95) / 1000, 1),
            "completion_tokens_mean": round(statistics.mean(x["completion_tokens"] for x in xs), 1)}
    pairs = {}
    for x in rows:
        pairs.setdefault((x["id"], x["round"]), {})[x["top_k"]] = x["total_ms"]
    ratios = [p[3] / p[5] for p in pairs.values() if 3 in p and 5 in p]
    summ["paired_ratio_total_k3_over_k5_median"] = round(statistics.median(ratios), 3)
    write_json(out_dir / "summary.json", summ)
    return summ


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", default=["baseline", "topk3"])
    ap.add_argument("--skip-bench", action="store_true")
    ap.add_argument("--rounds", type=int, default=1)
    a = ap.parse_args()
    tok = count_tokens(a.runs)
    print(json.dumps(tok, ensure_ascii=False, indent=1))
    lines = ["| Прогін | Токени промпту: середнє | медіана | мін–макс | з них системний промпт |", "|---|---|---|---|---|"]
    lines += [f"| {r} | {v['mean']} | {v['median']} | {v['min']}–{v['max']} | {v['system_tokens']} |" for r, v in tok.items()]
    summ = None
    if not a.skip_bench:
        summ = bench(a.rounds)
        print(json.dumps(summ, ensure_ascii=False, indent=1))
        lines += ["", f"Контрольований вимір затримки ({summ['n_per_config']} запитів на конфігурацію, порядок чергується, модель {summ['model']}):", "",
                  "| Конфігурація | LLM p50, с | LLM p95, с | Повний запит p50, с | p95, с | Токени відповіді |", "|---|---|---|---|---|---|"]
        for k in (5, 3):
            v = summ[f"top_k={k}"]
            lines.append(f"| top_k = {k} | {v['llm_p50_s']} | {v['llm_p95_s']} | {v['total_p50_s']} | {v['total_p95_s']} | {v['completion_tokens_mean']} |")
        lines += ["", f"Медіана парного відношення часу (top_k = 3 / top_k = 5): {summ['paired_ratio_total_k3_over_k5_median']}"]
    (ROOT / "docs" / "cost_latency_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
