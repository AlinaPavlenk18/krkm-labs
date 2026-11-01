"""Повторна валідація збережених сирих відповідей LLM новим валідатором (без нових викликів моделі).
  python scripts/replay_validator.py results/v1/llm_dev_calls.jsonl results/v1/llm_dev_replay_validator_v2.jsonl
Використано на dev для оцінки внеску валідатора v2 окремо від підказки v2."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.extract_llm import validate  

docs = {json.loads(l)["doc_id"]: json.loads(l)["text"] for l in open(ROOT / "data/docs.jsonl", encoding="utf-8")}
src, dst = sys.argv[1], sys.argv[2]
out, raw_n, bad_n = [], 0, 0
seen = set()
for l in open(src, encoding="utf-8"):
    c = json.loads(l)
    text, off = docs[c["doc_id"]], c["chunk_start"]
    chunk = text[off:off + c["chunk_chars"]]
    E, R = {}, {}
    for a in c["attempts"]:
        try:
            obj = json.loads(a["raw"])
        except json.JSONDecodeError:
            continue
        e, r, errs, bad = validate(obj, chunk)
        raw_n += len(obj.get("entities", [])) + len(obj.get("relations", []))
        bad_n += bad
        for k, v in e.items():
            E.setdefault(k, v)
        for x in r:
            R.setdefault((x["type"], x["head"], x["tail"]), x)
    for (t, cid), e in E.items():
        if (c["doc_id"], "E", t, cid) in seen:
            continue
        seen.add((c["doc_id"], "E", t, cid))
        out.append({"doc_id": c["doc_id"], "method": "llm", "kind": "entity", "type": t, "canonical": cid,
                    "text": e["text"], "start": off + e["off"]})
    for k, x in R.items():
        if (c["doc_id"], "R") + k in seen:
            continue
        seen.add((c["doc_id"], "R") + k)
        out.append({"doc_id": c["doc_id"], "method": "llm", "kind": "relation", "type": x["type"], "head": x["head"],
                    "tail": x["tail"], "evidence": x["evidence"], "start": off + x["off"]})
with open(dst, "w", encoding="utf-8") as f:
    for r in out:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"сирих тверджень {raw_n}, без підтвердження {bad_n} ({bad_n / max(1, raw_n):.3f}); після валідації {len(out)}")
