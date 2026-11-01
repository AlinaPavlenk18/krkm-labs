"""Метод 3: LLM зі схемою — qwen2.5:7b в Ollama (локально, CPU), JSON-схема з переліком предикатів,
evidence, валідація; 1 повтор, якщо відповідь невалідна.

  ollama pull qwen2.5:7b
"""
import argparse, json, re, time
import requests

from src.common import ROOT, PREDICATES, sentences, norm_triple, grounded, save

OLLAMA, MODEL, PROMPT, RETRIES = "http://localhost:11434", "qwen2.5:7b", "relations_v1", 1
OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 4096, "num_predict": 1024}
SCHEMA = {"type": "object", "required": ["triples"], "properties": {"triples": {"type": "array", "items": {
    "type": "object", "required": ["s", "p", "o", "evidence"], "properties": {
        "s": {"type": "string"}, "p": {"type": "string", "enum": PREDICATES},
        "o": {"type": "string"}, "evidence": {"type": "string"}}}}}}


def validate(raw, text):
    """→ (трійки, помилки). Трійка приймається, якщо нормалізується за схемою, evidence є в реченні,
    а обидва учасники названі в реченні (захист від вигаданих сутностей)."""
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        return set(), [f"невалідний JSON: {e}"]
    ok, errs = set(), []
    for t in obj.get("triples", []):
        tr = norm_triple(t.get("s", ""), t.get("p", ""), t.get("o", ""))
        ev = re.sub(r"\s+", " ", str(t.get("evidence", ""))).strip()
        if not tr:
            errs.append(f"не за схемою: {t.get('s')} {t.get('p')} {t.get('o')}")
        elif not ev or ev.lower() not in re.sub(r"\s+", " ", text).lower():
            errs.append(f"evidence не з речення: {tr}")
        elif not grounded(tr, text):
            errs.append(f"у реченні не названо {tr[0]} або {tr[2]}")
        else:
            ok.add(tr)
    return ok, errs


def call(system, user):
    t0 = time.time()
    r = requests.post(f"{OLLAMA}/api/chat", timeout=900, json={
        "model": MODEL, "stream": False, "format": SCHEMA, "options": OPTIONS,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
    r.raise_for_status()
    j = r.json()
    return j["message"]["content"], j.get("prompt_eval_count", 0), j.get("eval_count", 0), time.time() - t0


def main(resume):
    system = (ROOT / f"prompts/{PROMPT}.md").read_text(encoding="utf-8")
    calls_path = ROOT / "results/llm_calls.jsonl"
    cache = {}
    if resume and calls_path.exists():
        cache = {c["id"]: c for c in map(json.loads, open(calls_path, encoding="utf-8"))}
        print(f"--resume: у кеші {len(cache)} речень")
    elif calls_path.exists():
        calls_path.unlink()
    rows, tok_in, tok_out, sec_all, n_calls, retried, rejected = [], 0, 0, 0.0, 0, 0, 0
    for s in sentences():
        if s["id"] in cache:
            c = cache[s["id"]]
        else:
            user, attempts = f"Речення: «{s['text']}»", []
            for k in range(RETRIES + 1):
                raw, pt, ct, sec = call(system, user)
                trip, errs = validate(raw, s["text"])
                attempts.append({"attempt": k + 1, "raw": raw, "prompt_tokens": pt, "completion_tokens": ct,
                                 "seconds": round(sec, 2), "errors": errs})
                if not errs:
                    break
                user = (f"Речення: «{s['text']}»\n\nПопередня відповідь мала помилки:\n- " + "\n- ".join(errs) +
                        "\nВиправ: ID у заданому форматі, evidence — дослівний фрагмент речення.")
            c = {"id": s["id"], "model": MODEL, "prompt": PROMPT, "options": OPTIONS, "attempts": attempts}
            with open(calls_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
            print(f"{s['id']}: {sum(a['seconds'] for a in attempts):.1f} c, спроб {len(attempts)}", flush=True)
        trip = set()                                      # об'єднання перевірених трійок усіх спроб
        for a in c["attempts"]:
            t, errs = validate(a["raw"], s["text"])
            trip |= t
            rejected += len(errs)
        n_calls += len(c["attempts"]); retried += len(c["attempts"]) > 1
        tok_in += sum(a["prompt_tokens"] for a in c["attempts"]); tok_out += sum(a["completion_tokens"] for a in c["attempts"])
        sec = sum(a["seconds"] for a in c["attempts"]); sec_all += sec
        rows.append({"id": s["id"], "triples": sorted(trip), "seconds": round(sec, 2), "attempts": len(c["attempts"])})
    n = len(rows)
    save("llm", rows, {"method": "llm", "model": MODEL, "prompt": PROMPT, "options": OPTIONS, "sentences": n,
                       "calls": n_calls, "retried_sentences": retried, "rejected_by_validator": rejected,
                       "prompt_tokens": tok_in, "completion_tokens": tok_out, "seconds": round(sec_all, 1),
                       "seconds_per_sentence": round(sec_all / n, 2), "tokens_per_sentence": round((tok_in + tok_out) / n),
                       "cost_uah": 0})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", action="store_true")
    main(ap.parse_args().resume)
