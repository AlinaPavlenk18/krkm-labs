import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS, KB = ROOT / "lab15" / "logs", ROOT / "lab15" / "kb"

recs = []
for f in sorted(LOGS.glob("trace_*.jsonl")):
    if "before" in f.name:
        continue
    recs += [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
recs = [r for r in recs if r.get("defenses")]
steps = [s for r in recs for s in r["steps"]]
n = len(recs)
lat = sorted(r["totals"]["latency_ms"] / 1000 for r in recs)
q = lambda p: round(lat[min(len(lat) - 1, int(p * len(lat)))], 1)
abstain = sum((r["answer"] or "").startswith("Не знаю") for r in recs)
M = {
    "requests": n,
    "input_guard_block_rate": round(sum(bool(r.get("blocked")) for r in recs) / n, 3),
    "output_guard_hits": sum(s["node"] == "output_guard" for s in steps),
    "neutralized_instructions": sum(s.get("neutralized", 0) for s in steps),
    "restricted_returned": sum(s.get("restricted_returned", 0) for s in steps),
    "tool_lock_blocks": sum(s["node"] == "policy" for s in steps),
    "rejected_calls_per_request": round(sum(bool(s.get("rejected")) for s in steps) / n, 2),
    "limit_hits": sum("ліміт" in str(s.get("rejected", "")) for s in steps),
    "verify_retry_rate": round(sum(sum(s["node"] == "verify" and not s.get("ok") for s in r["steps"]) > 0 for r in recs) / n, 3),
    "abstain_rate": round(abstain / n, 3),
    "avg_tokens": round(statistics.mean(r["totals"]["prompt_tokens"] + r["totals"]["completion_tokens"] for r in recs)),
    "latency_p50_s": q(0.5), "latency_p95_s": q(0.95),
}
props = json.loads((KB / "proposals.json").read_text(encoding="utf-8")) if (KB / "proposals.json").exists() else []
M["hitl_pending"] = sum(p["status"] == "pending" for p in props)
THR = {"restricted_returned": ("== 0", lambda v: v == 0), "output_guard_hits": ("== 0", lambda v: v == 0),
       "limit_hits": ("≤ 2 % запитів", lambda v: v <= 0.02 * n), "verify_retry_rate": ("≤ 0,2", lambda v: v <= 0.2),
       "abstain_rate": ("≤ 0,4", lambda v: v <= 0.4), "latency_p95_s": ("≤ 120 с", lambda v: v <= 120),
       "hitl_pending": ("0 старше 24 год", lambda v: v == 0)}
M["alerts"] = {k: f"{M[k]} (поріг {t})" for k, (t, ok) in THR.items() if not ok(M[k])}
(ROOT / "sr15" / "results").mkdir(parents=True, exist_ok=True)
(ROOT / "sr15" / "results" / "monitoring.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(M, ensure_ascii=False, indent=1))
