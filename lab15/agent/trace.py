import json
import time
import uuid
from datetime import datetime

from agent import config as C


class Trace:
    def __init__(self, question, tag):
        self.rec = {"run_id": uuid.uuid4().hex[:10], "ts": datetime.now().isoformat(timespec="seconds"), "tag": tag,
                    "defenses": C.DEFENSES, "model": C.MODEL, "params": {"temperature": C.TEMPERATURE, "seed": C.SEED},
                    "prompt_version": C.PROMPT_VERSION, "limits": C.LIMITS, "question": question, "steps": []}
        self.t0 = time.perf_counter()

    def event(self, node, data):
        self.rec["steps"].append({"node": node, "t_ms": round((time.perf_counter() - self.t0) * 1000), **data})

    def finish(self, state):
        llm = [s for s in self.rec["steps"] if "prompt_tokens" in s]
        tools = [s for s in self.rec["steps"] if s["node"] == "retrieve" and "tool" in s]
        self.rec.update({"answer": state.get("answer"), "citations": state.get("citations", []), "verified": state.get("verified"),
                         "blocked": state.get("blocked"), "evidence_ids": list(state.get("evidence", {})),
                         "totals": {"llm_calls": len(llm), "tool_calls": len(tools),
                                    "prompt_tokens": sum(s["prompt_tokens"] for s in llm),
                                    "completion_tokens": sum(s["completion_tokens"] for s in llm),
                                    "latency_ms": round((time.perf_counter() - self.t0) * 1000), "cost_usd": 0.0}})
        C.LOGS.mkdir(exist_ok=True)
        with open(C.LOGS / f"trace_{self.rec['tag']}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(self.rec, ensure_ascii=False) + "\n")
        return self.rec
