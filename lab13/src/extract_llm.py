"""Метод Б: LLM (qwen2.5:7b, Ollama, локально) з JSON-схемою, закритим словником, evidence, валідацією
і повторами (до 2 повторів після помилки).

  python -m src.extract_llm --split dev  [--prompt extract_v1]   # налаштування лише на dev
  python -m src.extract_llm --split test --prompt extract_v2      # фінальний запуск
Вихід: results/llm_<split>.jsonl (provenance), results/llm_<split>_calls.jsonl (сирі відповіді, токени, час).
"""
import argparse, json, os, re, time
from datetime import datetime
from pathlib import Path
import requests

from src.schema import ENTITY_TYPES, RELATION_TYPES, canonical, DEV_DOCS

ROOT = Path(__file__).resolve().parents[1]
MODEL = os.getenv("EXTRACT_MODEL", "qwen2.5:7b")
OLLAMA = os.getenv("OLLAMA_URL", "http://localhost:11434")
MAX_CHARS, RETRIES = 1500, 2

SCHEMA = {"type": "object", "required": ["entities", "relations"], "properties": {
    "entities": {"type": "array", "items": {"type": "object", "required": ["type", "id", "text"], "properties": {
        "type": {"type": "string", "enum": ENTITY_TYPES}, "id": {"type": "string"}, "text": {"type": "string"}}}},
    "relations": {"type": "array", "items": {"type": "object", "required": ["type", "head", "tail", "evidence"], "properties": {
        "type": {"type": "string", "enum": list(RELATION_TYPES)}, "head": {"type": "string"}, "tail": {"type": "string"},
        "evidence": {"type": "string"}}}}}}


def chunks(text):
    """Розділи markdown, жадібно об'єднані до ~MAX_CHARS символів; задовгий розділ ріжеться за абзацами.
    Повертає [(офсет у документі, фрагмент)]."""
    starts = sorted({0} | {m.start() for m in re.finditer(r"(?m)^#{1,3} ", text)})
    secs = list(zip(starts, starts[1:] + [len(text)]))
    pieces = []
    for a, b in secs:                      # задовгі розділи → шматки за абзацами
        while b - a > MAX_CHARS * 1.5:
            cut = text.rfind("\n\n", a + 1, a + MAX_CHARS)
            cut = cut if cut > a else a + MAX_CHARS
            pieces.append((a, cut))
            a = cut
        pieces.append((a, b))
    out, cur = [], None
    for a, b in pieces:                    # жадібне об'єднання сусідніх шматків
        if cur and b - cur[0] <= MAX_CHARS:
            cur = (cur[0], b)
        else:
            if cur:
                out.append(cur)
            cur = (a, b)
    if cur:
        out.append(cur)
    return [(a, text[a:b]) for a, b in out if text[a:b].strip()]


def norm_ws(s):
    return re.sub(r"\s+", " ", s).strip()


def find(ev, chunk):
    """Офсет доказу в фрагменті: дослівно, без урахування регістру і пробілів (v2); -1 якщо немає."""
    if not ev.strip():
        return -1
    i = chunk.find(ev)
    if i >= 0:
        return i
    m = re.search(r"\s+".join(map(re.escape, ev.split())), chunk, re.I)
    return m.start() if m else -1


REG_STEM = {"Region_Lviv": "львівськ", "Region_Volyn": "волинськ", "Region_Rivne": "рівненськ",
            "Region_Ternopil": "тернопільськ", "Region_Zakarpattia": "закарпатськ", "Region_IvanoFrankivsk": "івано-франківськ"}


def mention_re(etype, cid):
    """Регулярний вираз «ядра» згадки сутності — для перевірки, що цитата справді називає сутність."""
    n = re.search(r"(\d+)$", cid)
    if etype == "SUBSTATION":
        return rf"№\s*{n.group(1)}(?!\d)|{cid}"
    if etype == "DISPATCHER":
        return rf"диспетчер\w*\s*№\s*{n.group(1)}(?!\d)|{cid}"
    if etype == "CONSUMER":
        return rf"№\s*{n.group(1)}|{cid}"
    if etype == "METER":
        return rf"AMI-{cid[-5:]}"
    if etype == "MODEL":
        m = re.match(r"ForecastModel_([A-Z]+)(\d+)", cid)
        return rf"{m.group(1)}\s*№\s*{m.group(2)}(?!\d)|моделі {m.group(1)}:[^.]*№{m.group(2)}(?!\d)"
    if etype == "REGION":
        return REG_STEM[cid] + r"\w*\s+(?:та\s+\w+\s+)?област"
    if etype == "METHOD":
        return rf"\b{cid}\b"
    return re.escape(cid)


def header_before(chunk, off):
    hs = [m for m in re.finditer(r"(?m)^#{1,3} .*$", chunk) if m.start() <= off]
    return hs[-1].group(0) if hs else ""


def validate(obj, chunk):
    errs, ents, rels, bad = [], {}, [], 0
    for e in obj.get("entities", []):
        t = e.get("type")
        if t not in ENTITY_TYPES:
            errs.append(f"невідомий тип сутності {t}")
            continue
        cid = canonical(t, str(e.get("id", ""))) or canonical(t, str(e.get("text", "")))
        if not cid:
            errs.append(f"id «{e.get('id')}» не відповідає формату {t}")
            bad += 1
            continue
        text, off = str(e.get("text", "")), find(str(e.get("text", "")), chunk)
        NUM = ("SUBSTATION", "CONSUMER", "METER", "MODEL", "DISPATCHER")
        if t in NUM and off >= 0 and not re.search(mention_re(t, cid), text, re.I):
            off = -1                                                
        if off < 0 and t in ("SUBSTATION", "CONSUMER", "METER", "MODEL", "DISPATCHER", "REGION", "METHOD"):
            m = re.search(mention_re(t, cid), chunk, re.I)         
            if m:
                text, off = m.group(0), m.start()
        if off < 0:
            bad += 1                                                
            continue
        ents.setdefault((t, cid), {"type": t, "canonical": cid, "text": chunk[off:off + len(text)], "off": off})
    for r in obj.get("relations", []):
        t = r.get("type")
        if t not in RELATION_TYPES:
            errs.append(f"невідомий тип відношення {t}")
            continue
        ht, tt = RELATION_TYPES[t]
        h, tl = canonical(ht, str(r.get("head", ""))), canonical(tt, str(r.get("tail", "")))
        if not h or not tl:
            errs.append(f"{t}: голова/хвіст мають бути типів {ht} → {tt}, отримано {r.get('head')} → {r.get('tail')}")
            bad += 1
            continue
        ev = str(r.get("evidence", ""))
        off = find(ev, chunk)
        if off < 0:
            errs.append(f"{t}({h}, {tl}): evidence не є дослівним підрядком фрагмента")
            bad += 1
            continue
        ev = chunk[off:off + len(ev)] if chunk[off:off + len(ev)].lower() == ev.lower() else ev
        scope = ev + "\n" + header_before(chunk, off)                   
        if not (re.search(mention_re(ht, h), scope, re.I) and re.search(mention_re(tt, tl), scope, re.I)):
            errs.append(f"{t}({h}, {tl}): у цитаті «{ev[:60]}» не названо обох сутностей")   
            bad += 1
            continue
        rels.append({"type": t, "head": h, "tail": tl, "evidence": ev, "off": off})
    return ents, rels, errs, bad


def call(system, user):
    t0 = time.time()
    r = requests.post(f"{OLLAMA}/api/chat", timeout=1800, json={
        "model": MODEL, "stream": False, "format": SCHEMA,
        "options": {"temperature": 0, "seed": 42, "num_ctx": 8192, "num_predict": 4096},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
    r.raise_for_status()
    j = r.json()
    return j["message"]["content"], j.get("prompt_eval_count", 0), j.get("eval_count", 0), time.time() - t0


def extract_chunk(system, chunk):
    """До 1 + RETRIES спроб; повтор — якщо JSON невалідний або є помилки у відношеннях/ID.
    Підсумок — об'єднання перевірених тверджень усіх спроб (v2)."""
    user = f"Фрагмент:\n{chunk}"
    log, ents, rels = [], {}, {}
    for attempt in range(1, RETRIES + 2):
        raw, pt, ct, sec = call(system, user)
        try:
            obj = json.loads(raw)
            e, r, errs, bad = validate(obj, chunk)
            n = len(obj.get("entities", [])) + len(obj.get("relations", []))
        except json.JSONDecodeError as ex:
            e, r, errs, bad, n = {}, [], [f"невалідний JSON: {ex}"], 0, 0
        for k, v in e.items():
            ents.setdefault(k, v)
        for x in r:
            rels.setdefault((x["type"], x["head"], x["tail"]), {**x, "attempt": attempt})
        log.append({"attempt": attempt, "raw": raw, "prompt_tokens": pt, "completion_tokens": ct,
                    "seconds": round(sec, 2), "errors": errs, "statements": n, "unverified": bad})
        if not errs:
            break
        user = (f"Фрагмент:\n{chunk}\n\nТвоя попередня відповідь мала помилки:\n- " + "\n- ".join(errs[:12]) +
                "\nВиправ їх: evidence — короткий дослівний підрядок фрагмента, де названо обидві сутності; id — у заданому форматі.")
    return ents, list(rels.values()), log


def replay(chunk, log):
    """Відновлює твердження фрагмента зі збережених сирих відповідей (для --resume, без виклику моделі)."""
    ents, rels = {}, {}
    for a in log:
        try:
            e, r, _, _ = validate(json.loads(a["raw"]), chunk)
        except json.JSONDecodeError:
            continue
        for k, v in e.items():
            ents.setdefault(k, v)
        for x in r:
            rels.setdefault((x["type"], x["head"], x["tail"]), {**x, "attempt": a["attempt"]})
    return ents, list(rels.values())


def run(split, prompt, resume=False):
    system = (ROOT / f"prompts/{prompt}.md").read_text(encoding="utf-8")
    docs = [json.loads(l) for l in open(ROOT / "data/docs.jsonl", encoding="utf-8")]
    docs = [d for d in docs if (d["doc_id"] in DEV_DOCS) == (split == "dev") or split == "all"]
    out_path, calls_path = ROOT / f"results/llm_{split}.jsonl", ROOT / f"results/llm_{split}_calls.jsonl"
    cache = {}
    if resume and calls_path.exists():          # фрагменти, уже оброблені в перерваному запуску
        for l in open(calls_path, encoding="utf-8"):
            try:
                c = json.loads(l)
            except json.JSONDecodeError:         # обірваний останній рядок — фрагмент перерахується
                continue
            if c.get("prompt_version") == prompt:
                cache[(c["doc_id"], c["chunk_start"])] = c
        print(f"--resume: у кеші {len(cache)} готових фрагментів", flush=True)
    stats = {"docs": 0, "chunks": 0, "calls": 0, "retried_chunks": 0, "prompt_tokens": 0, "completion_tokens": 0,
             "seconds": 0.0, "statements_raw": 0, "unverified": 0, "per_doc": {}}
    with open(out_path, "w", encoding="utf-8") as fo, open(calls_path, "w", encoding="utf-8") as fc:
        for d in docs:
            t0, dtok = time.time(), 0
            seen_e, seen_r = set(), set()
            for off, ch in chunks(d["text"]):
                cached = cache.get((d["doc_id"], off))
                if cached:
                    log = cached["attempts"]
                    ents, rels = replay(ch, log)
                    t0 -= sum(a["seconds"] for a in log)      # час збереженого фрагмента входить у час документа
                else:
                    ents, rels, log = extract_chunk(system, ch)
                stats["chunks"] += 1
                stats["calls"] += len(log)
                stats["retried_chunks"] += len(log) > 1
                for l in log:
                    stats["prompt_tokens"] += l["prompt_tokens"]
                    stats["completion_tokens"] += l["completion_tokens"]
                    dtok += l["prompt_tokens"] + l["completion_tokens"]
                fc.write(json.dumps(cached or {"doc_id": d["doc_id"], "chunk_start": off, "chunk_chars": len(ch),
                                               "model": MODEL, "prompt_version": prompt,
                                               "time": datetime.now().isoformat(timespec="seconds"), "attempts": log},
                                    ensure_ascii=False) + "\n")
                fc.flush()
                fo.flush()
                stats["statements_raw"] += sum(l["statements"] for l in log)
                stats["unverified"] += sum(l["unverified"] for l in log)
                base = {"doc_id": d["doc_id"], "method": "llm", "model": MODEL, "prompt_version": prompt,
                        "chunk_start": off, "attempts_used": len(log)}
                for (t, c), e in ents.items():
                    if (t, c) in seen_e:
                        continue
                    seen_e.add((t, c))
                    st = off + e["off"]
                    fo.write(json.dumps({**base, "kind": "entity", "type": t, "canonical": c, "text": e["text"],
                                         "start": st, "end": st + len(e["text"]), "confidence": 0.7}, ensure_ascii=False) + "\n")
                for r in rels:
                    k = (r["type"], r["head"], r["tail"])
                    if k in seen_r:
                        continue
                    seen_r.add(k)
                    st = off + r["off"]
                    fo.write(json.dumps({**base, "kind": "relation", "type": r["type"], "head": r["head"], "tail": r["tail"],
                                         "evidence": r["evidence"], "start": st, "end": st + len(r["evidence"]),
                                         "attempt": r["attempt"], "evidence_verified": True, "confidence": 0.7},
                                        ensure_ascii=False) + "\n")
            sec = time.time() - t0
            stats["docs"] += 1
            stats["seconds"] += sec
            stats["per_doc"][d["doc_id"]] = {"seconds": round(sec, 1), "tokens": dtok}
            print(f"{d['doc_id']}: {sec:.1f} с, токенів {dtok}", flush=True)
    stats.update({"model": MODEL, "prompt": prompt, "split": split, "seconds": round(stats["seconds"], 1),
                  "seconds_per_doc": round(stats["seconds"] / max(1, stats["docs"]), 1),
                  "tokens_per_doc": round((stats["prompt_tokens"] + stats["completion_tokens"]) / max(1, stats["docs"])),
                  "unverified_share": round(stats["unverified"] / max(1, stats["statements_raw"]), 3)})
    (ROOT / f"results/llm_{split}_meta.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in stats.items() if k != "per_doc"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    ap.add_argument("--prompt", default="extract_v1")
    ap.add_argument("--resume", action="store_true", help="продовжити перерваний запуск: готові фрагменти не перераховуються")
    a = ap.parse_args()
    run(a.split, a.prompt, a.resume)
