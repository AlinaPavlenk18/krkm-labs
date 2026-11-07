"""Р2. Entity resolution: згадки сутностей із текстів (ЛР13) + вузли графа ЛР9 → сутності без дублікатів.

Записи
  graph  — вузли ЛР9 (підстанції, споживачі, лічильники, моделі, диспетчери, регіони): назва + атрибути;
  text   — згадки ЛР13 (правила й LLM; однаковий фрагмент двох методів = один запис): поверхнева форма + речення.
  Ідентифікатори графа й канонічні ID ЛР13 у порівнянні НЕ використовуються — лише для еталона (ref).
Конвеєр
  нормалізація → blocking (група типу + перша цифра номера / перші 3 літери назви)
  → порівняння: рядки (rapidfuzz token_set_ratio), номери (атрибут), тип (атрибут), ембедінги e5-small (контекст)
  → рішення: score = 0.30·str + 0.35·num + 0.20·emb + 0.15·type ≥ поріг (поріг — на dev за F0.5: хибне злиття
    дорожче за пропуск) → злиття union-find із забороною зливати два різні вузли графа (cannot-link).

Команди (з папки lab14):
  python quality/dedup.py candidates    # записи й пари-кандидати → quality/out/er_*.{jsonl,csv}
  python quality/dedup.py sample        # 120 пар (60 dev / 60 test) → quality/pairs_gold.csv; заповнити label 1/0
  python quality/dedup.py tune          # поріг на dev → quality/out/er_tuning.json, er_tuning.png
  python quality/dedup.py eval          # P/R/F1 на test (+ абляція типів порівняння) → quality/out/er_eval.json
  python quality/dedup.py judge         # LLM-суддя (локальна qwen2.5:7b) на спірних парах test → llm_log/dedup_judge.jsonl
  python quality/dedup.py merge         # злиття → quality/out/entities_resolved.json, quality/out/merge_log.jsonl
  python quality/dedup.py unmerge --record t0123 --reason "…"   # відокремити запис, cannot-link → quality/cannot_link.csv
"""
import argparse
import csv
import hashlib
import json
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime

import numpy as np
from rapidfuzz import fuzz

from common import (DATA, LAB, OUT, QUALITY, SEED, ADDRESS_RE, Encoder, load_graph, normalize, read_jsonl,
                    write_json, write_jsonl)

W = {"str": 0.30, "num": 0.35, "emb": 0.20, "type": 0.15}
GOLD = QUALITY / "pairs_gold.csv"
CANNOT = QUALITY / "cannot_link.csv"
LOG = OUT / "merge_log.jsonl"
REG = OUT / "entities_resolved.json"
JUDGE_LOG = LAB / "llm_log" / "dedup_judge.jsonl"
GROUP = {"SUBSTATION": "SUB", "CONSUMER": "CON", "METER": "MET", "MODEL": "MOD", "METHOD": "MOD",
         "DISPATCHER": "DIS", "REGION": "REG", "METRIC": "MTR", "WEATHER_FACTOR": "WEA"}
GRAPH_TYPES = {"substation": "SUBSTATION", "consumer": "CONSUMER", "meter": "METER", "forecastmodel": "MODEL",
               "dispatcher": "DISPATCHER", "region": "REGION"}
QUOTA = {"SUB": 25, "MOD": 25, "CON": 20, "MET": 15, "DIS": 12, "WEA": 12, "REG": 11}   # 120 пар
TYPE_WORDS = re.compile(r"\b(підстанц\w*|пс|модел\w*|лічильник\w*|споживач\w*|диспетчер\w*|област\w*|метод\w*)\b")


def norm_name(s):
    t = normalize(re.sub(r"\([^)]*\)", " ", s))
    t = TYPE_WORDS.sub(" ", t)
    t = re.sub(r"[№_\-]", " ", t)
    toks = [w[:5] if w.isalpha() and len(w) > 5 else w for w in re.findall(r"[0-9a-zа-щьюяґєії']+", t)]
    return " ".join(toks)


def numbers(s):
    return tuple(re.findall(r"\d+", re.sub(r"\([^)]*\)", " ", s)))


def codes(s):
    return tuple(sorted({c.upper() for c in re.findall(r"[A-Za-z]{2,}", s)} - {"AMI"}))


def sentence_around(text, start, end, limit=300):
    a = max(text.rfind(". ", 0, start), text.rfind("\n", 0, start))
    b = min([x for x in (text.find(". ", end), text.find("\n", end)) if x != -1] or [len(text)])
    s = re.sub(r"\s+", " ", text[a + 1:b + 1]).strip()
    return s if len(s) <= limit else s[:limit] + " …"


def build_records():
    nodes, rels = load_graph()
    region_of = {r["start"]: r["end"] for r in rels["LOCATED_IN"]}
    names = {n["id"]: n["name"] for rows in nodes.values() for n in rows}
    recs = []
    for lab, typ in GRAPH_TYPES.items():
        for n in nodes[lab]:
            attrs = {k: v for k, v in n.items() if k not in ("id", "name", "source", "address") and v}
            if n["id"] in region_of:
                attrs["region"] = names[region_of[n["id"]]]
            desc = f"{n['name']}; " + "; ".join(f"{k} {v}" for k, v in attrs.items())
            recs.append({"rid": f"g:{n['id']}", "source": "graph", "type": typ, "name": n["name"], "doc": None,
                         "sensitivity": "internal", "desc": desc, "context": desc, "ref": n["id"], "ref_src": "graph",
                         "provenance": {"graph_source": n["source"]}})
    docs = {d["doc_id"]: d for d in read_jsonl(DATA / "lab13" / "docs.jsonl")}
    gold = defaultdict(list)
    for g in read_jsonl(DATA / "lab13" / "gold.jsonl"):
        if g["kind"] == "entity":
            gold[g["doc_id"]].append(g)
    spans = {}
    for f, meth in [("extracted_rules.jsonl", "rules"), ("extracted_llm_dev.jsonl", "llm"), ("extracted_llm_test.jsonl", "llm")]:
        for r in read_jsonl(DATA / "lab13" / f):
            if r["kind"] != "entity":
                continue
            k = (r["doc_id"], r["start"], r["end"], r["type"])
            e = spans.setdefault(k, {"text": r["text"], "methods": set(), "canon": set()})
            e["methods"].add(meth)
            e["canon"].add(r["canonical"])
    for i, ((doc, s, e, typ), v) in enumerate(sorted(spans.items())):
        # еталон: золота згадка ЛР13 з тим самим фрагментом або того самого типу, що перетинається; інакше — канон витягу
        g = [x for x in gold[doc] if x["start"] < e and s < x["end"] and ((x["start"], x["end"]) == (s, e) or x["type"] == typ)]
        g.sort(key=lambda x: (-((x["start"], x["end"]) == (s, e)), -(min(e, x["end"]) - max(s, x["start"]))))
        ref, src = (g[0]["canonical"], "gold_lab13") if g else (sorted(v["canon"])[0], "extractor")
        d = docs[doc]
        ctx = sentence_around(d["text"], s, e)
        recs.append({"rid": f"t{i:04d}", "source": "text", "type": typ, "name": v["text"], "doc": doc,
                     "sensitivity": d["sensitivity"], "desc": f"{v['text']} — {ctx}", "context": ctx, "ref": ref,
                     "ref_src": src, "provenance": {"doc": doc, "start": s, "end": e, "methods": sorted(v["methods"]),
                                                    "doc_date": d["date"]}})
    for r in recs:
        r["norm"] = norm_name(r["name"])
        r["nums"] = numbers(r["name"])
        r["codes"] = codes(r["name"])
        r["block"] = GROUP[r["type"]] + "|" + (r["nums"][0][0] if r["nums"] else (r["norm"][:3] or "_"))
    return recs


def features(a, b, emb):
    f_str = fuzz.token_set_ratio(a["norm"], b["norm"]) / 100
    # атрибут-ідентифікатор: номер і код (LSTM/GRU/…); різні — 0, однакові — 1, частково невідомі — 0.5 / за наявним
    if a["codes"] and b["codes"] and set(a["codes"]) != set(b["codes"]):
        f_num = 0.0
    elif a["nums"] and b["nums"]:
        f_num = 1.0 if set(a["nums"]) == set(b["nums"]) else 0.0
    elif a["codes"] and b["codes"]:
        f_num = 1.0
    else:
        f_num = 0.5
    cos = float(emb[a["rid"]] @ emb[b["rid"]])
    f_emb = min(1.0, max(0.0, (cos - 0.70) / 0.30))         
    f_type = 1.0 if a["type"] == b["type"] else 0.0
    return {"str": round(f_str, 4), "num": f_num, "emb": round(f_emb, 4), "type": f_type, "cos": round(cos, 4)}


def score(f, w=W):
    return round(sum(w[k] * f[k] for k in w), 4)


def candidates(recs, emb):
    blocks = defaultdict(list)
    for r in recs:
        blocks[r["block"]].append(r)
    pairs = []
    for b, rs in blocks.items():
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)):
                a, c = rs[i], rs[j]
                if a["source"] == "graph" and c["source"] == "graph":
                    continue                                   # реєстр графа — еталонний, пари граф–граф не порівнюємо
                if a["source"] == "graph":
                    a, c = c, a
                f = features(a, c, emb)
                pairs.append({"a": a["rid"], "b": c["rid"], "block": b, **f, "score": score(f),
                              "ref_same": int(a["ref"] == c["ref"])})
    return pairs


def embeddings(recs):
    cache = OUT / "er_emb.npz"
    key = hashlib.sha256("\n".join(r["desc"] for r in recs).encode()).hexdigest()[:16] + ("stub" if os.environ.get("LAB14_STUB") == "1" else "e5")
    if cache.exists():
        z = np.load(cache, allow_pickle=True)
        if str(z["key"]) == key:
            return dict(zip(z["rids"], z["vecs"]))
    vecs = Encoder().encode([r["desc"] for r in recs])
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache, key=key, rids=np.array([r["rid"] for r in recs]), vecs=vecs)
    return dict(zip([r["rid"] for r in recs], vecs))


def cmd_candidates(a):
    t = time.perf_counter()
    recs = build_records()
    emb = embeddings(recs)
    pairs = candidates(recs, emb)
    write_jsonl(OUT / "er_records.jsonl", [{k: v for k, v in r.items() if k not in ("desc",)} for r in recs])
    with open(OUT / "er_candidates.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(pairs[0]))
        w.writeheader()
        w.writerows(pairs)
    n_text = sum(r["source"] == "text" for r in recs)
    n_graph = len(recs) - n_text
    full = n_text * (n_text - 1) // 2 + n_text * n_graph
    stats = {"records": len(recs), "text": n_text, "graph": n_graph, "blocks": len({r["block"] for r in recs}),
             "pairs_without_blocking": full, "candidates": len(pairs), "reduction": round(1 - len(pairs) / full, 4),
             "candidate_positive_share_ref": round(sum(p["ref_same"] for p in pairs) / len(pairs), 4),
             "ref_src": dict(Counter(r["ref_src"] for r in recs)), "by_type": dict(Counter(r["type"] for r in recs)),
             "seconds": round(time.perf_counter() - t, 1)}
    write_json(OUT / "er_candidates_stats.json", stats)
    print(json.dumps(stats, ensure_ascii=False, indent=1))


def load_recs():
    return {r["rid"]: r for r in read_jsonl(OUT / "er_records.jsonl")}


def load_pairs():
    with open(OUT / "er_candidates.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for p in rows:
        for k in ("str", "num", "emb", "type", "cos", "score"):
            p[k] = float(p[k])
        p["ref_same"] = int(p["ref_same"])
    return rows


def shown_context(r):
    if r["source"] == "graph":
        return r["context"]
    if r["sensitivity"] == "restricted":
        pv = r["provenance"]
        return f"[restricted: {r['doc']}, символи {pv['start']}–{pv['end']} — дивитися локально]"
    return ADDRESS_RE.sub("[адресу приховано]", r["context"])


def cmd_sample(a):
    if GOLD.exists() and not a.force:
        sys.exit(f"{GOLD} уже існує (розмітку не перезаписую; --force — створити заново)")
    recs, pairs = load_recs(), load_pairs()
    rnd = random.Random(SEED)
    picked = []
    for grp, k in QUOTA.items():                       # квота на групу типів, усередині — рівномірно за рангом score
        pool = sorted([p for p in pairs if p["block"].startswith(grp + "|")], key=lambda p: p["score"])
        if len(pool) <= k:
            picked += pool
            continue
        step = len(pool) / k
        picked += [pool[min(len(pool) - 1, int(i * step + rnd.random() * step))] for i in range(k)]
    picked.sort(key=lambda p: (p["block"], p["score"]))   # чергування dev/test у межах групи й score = стратифікація
    rows = []
    for i, p in enumerate(picked):
        A, B = recs[p["a"]], recs[p["b"]]
        rows.append({"pair_id": f"P{i + 1:03d}", "split": "dev" if i % 2 == 0 else "test",
                     "a_id": A["rid"], "a_source": A["source"], "a_type": A["type"], "a_name": A["name"],
                     "a_doc": A["doc"] or "graph", "a_context": shown_context(A),
                     "b_id": B["rid"], "b_source": B["source"], "b_type": B["type"], "b_name": B["name"],
                     "b_doc": B["doc"] or "graph", "b_context": shown_context(B),
                     "ref_a": A["ref"], "ref_b": B["ref"], "ref_src": f"{A['ref_src']}/{B['ref_src']}",
                     "suggested": int(A["ref"] == B["ref"]), "label": "", "comment": ""})
    rnd.shuffle(rows)
    with open(GOLD, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=";")
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["pair_id"]))
    print(f"{len(rows)} пар → {GOLD}: dev {sum(r['split'] == 'dev' for r in rows)}, test {sum(r['split'] == 'test' for r in rows)}; "
          f"suggested=1: {sum(r['suggested'] for r in rows)}")


def gold(split=None):
    with open(GOLD, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    if any(r["label"].strip() not in ("0", "1") for r in rows):
        sys.exit("pairs_gold.csv: заповніть label (1 — та сама сутність, 0 — різні) у всіх рядках")
    return [r for r in rows if split is None or r["split"] == split]


def prf(y, yhat):
    tp = sum(1 for a, b in zip(y, yhat) if a and b)
    fp = sum(1 for a, b in zip(y, yhat) if not a and b)
    fn = sum(1 for a, b in zip(y, yhat) if a and not b)
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    f05 = 1.25 * p * r / (0.25 * p + r) if p + r else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4), "f05": round(f05, 4)}


VARIANTS = {"full (рядки+номер+тип+ембедінги)": W,
            "без ембедінгів (рядки+номер+тип)": {"str": 0.375, "num": 0.4375, "emb": 0.0, "type": 0.1875},
            "лише рядки": {"str": 1.0, "num": 0.0, "emb": 0.0, "type": 0.0},
            "лише ембедінги": {"str": 0.0, "num": 0.0, "emb": 1.0, "type": 0.0}}


def scored(rows, feats, w):
    return [score(feats[(r["a_id"], r["b_id"])], w) for r in rows]


def best_threshold(y, s):
    grid = np.round(np.arange(0.20, 1.0001, 0.01), 2)
    res = [(t, prf(y, [x >= t for x in s])) for t in grid]
    t, m = max(res, key=lambda x: (x[1]["f05"], x[0]))
    return float(t), m, res


def feat_index():
    return {(p["a"], p["b"]): p for p in load_pairs()}


def cmd_tune(a):
    dev, feats = gold("dev"), feat_index()
    y = [r["label"] == "1" for r in dev]
    out = {"criterion": "max F0.5 на dev (хибне злиття дорожче за пропущений дублікат)", "variants": {}}
    curves = {}
    for name, w in VARIANTS.items():
        t, m, res = best_threshold(y, scored(dev, feats, w))
        out["variants"][name] = {"weights": w, "threshold": t, "dev": m}
        curves[name] = res
    out["threshold"] = out["variants"]["full (рядки+номер+тип+ембедінги)"]["threshold"]
    out["n_dev"], out["dev_positive"] = len(dev), sum(y)
    write_json(OUT / "er_tuning.json", out)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    res = curves["full (рядки+номер+тип+ембедінги)"]
    fig, ax = plt.subplots(figsize=(7, 3.6), dpi=150)
    ax.plot([t for t, _ in res], [m["precision"] for _, m in res], label="precision")
    ax.plot([t for t, _ in res], [m["recall"] for _, m in res], label="recall")
    ax.plot([t for t, _ in res], [m["f05"] for _, m in res], label="F0.5", linestyle="--")
    ax.axvline(out["threshold"], color="black", lw=0.8)
    ax.text(out["threshold"] + 0.01, 0.05, f"поріг {out['threshold']}", fontsize=8)
    ax.set_xlabel("поріг score")
    ax.set_title(f"Підбір порогу на dev (n = {len(dev)})", fontsize=10)
    ax.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(OUT / "er_tuning.png")
    print(json.dumps(out, ensure_ascii=False, indent=1))


def cmd_eval(a):
    test, feats = gold("test"), feat_index()
    tun = json.loads((OUT / "er_tuning.json").read_text(encoding="utf-8"))
    y = [r["label"] == "1" for r in test]
    out = {"n_test": len(test), "test_positive": sum(y), "variants": {}}
    for name, v in tun["variants"].items():
        s = scored(test, feats, v["weights"])
        out["variants"][name] = {"threshold": v["threshold"], "test": prf(y, [x >= v["threshold"] for x in s])}
    t = tun["threshold"]
    s = scored(test, feats, W)
    out["errors"] = [{"pair_id": r["pair_id"], "type": "FP (хибне злиття)" if x >= t else "FN (пропущений дублікат)",
                      "a": f"{r['a_name']} [{r['a_type']}, {r['a_doc']}]", "b": f"{r['b_name']} [{r['b_type']}, {r['b_doc']}]",
                      "score": x, "features": {k: feats[(r['a_id'], r['b_id'])][k] for k in ("str", "num", "emb", "type")},
                      "comment": r["comment"]}
                     for r, x, yy in zip(test, s, y) if (x >= t) != yy]
    out["label_vs_suggested_disagree"] = [r["pair_id"] for r in gold() if r["label"] != str(r["suggested"])]
    jp = OUT / "er_judge.json"
    if jp.exists():
        out["with_llm_judge"] = json.loads(jp.read_text(encoding="utf-8"))
    write_json(OUT / "er_eval.json", out)
    print(json.dumps(out, ensure_ascii=False, indent=1))


# ---------- LLM-суддя (локально) ----------
def ollama(messages):
    import requests
    base = os.environ.get("GEN_BASE_URL", "http://localhost:11434")
    model = os.environ.get("GEN_MODEL", "qwen2.5:7b")
    t = time.perf_counter()
    r = requests.post(base + "/api/chat", timeout=600, json={
        "model": model, "messages": messages, "stream": False, "format": "json",
        "options": {"temperature": 0, "seed": SEED, "num_ctx": 4096, "num_predict": 200}})
    r.raise_for_status()
    return r.json()["message"]["content"], model, round((time.perf_counter() - t) * 1000)


def judge_prompt():
    raw = (LAB / "prompts" / "dedup_judge_v1.md").read_text(encoding="utf-8")
    return raw.split("===SYSTEM===")[1].split("===USER===")[0].strip(), raw.split("===USER===")[1].strip()


def cmd_judge(a):
    recs, feats = load_recs(), feat_index()
    test = gold("test")
    t = json.loads((OUT / "er_tuning.json").read_text(encoding="utf-8"))["threshold"]
    disputed = [r for r in test if abs(score(feats[(r["a_id"], r["b_id"])]) - t) <= a.margin]
    system, tpl = judge_prompt()
    JUDGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    verdicts = {}
    for i, r in enumerate(disputed, 1):
        A, B = recs[r["a_id"]], recs[r["b_id"]]
        user = tpl
        for k, R in (("A", A), ("B", B)):
            user = (user.replace(f"{{{k}_type}}", R["type"]).replace(f"{{{k}_name}}", R["name"])
                    .replace(f"{{{k}_context}}", R["context"]).replace(f"{{{k}_source}}", R["doc"] or "граф ЛР9"))
        raw, model, ms = ollama([{"role": "system", "content": system}, {"role": "user", "content": user}])
        try:
            d = json.loads(raw)
            same = bool(d.get("same"))
        except json.JSONDecodeError:
            d, same = {}, None
        verdicts[r["pair_id"]] = same
        rec = {"ts": datetime.now().isoformat(timespec="seconds"), "model": model, "params": {"temperature": 0, "seed": SEED},
               "prompt_version": "dedup_judge_v1", "pair_id": r["pair_id"], "score": score(feats[(r["a_id"], r["b_id"])]),
               "threshold": t, "raw": raw, "same": same, "reason": d.get("reason"), "latency_ms": ms,
               "human_label": int(r["label"]), "human_decision": "accept" if same == (r["label"] == "1") else "reject"}
        with open(JUDGE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"[{i}/{len(disputed)}] {r['pair_id']} score={rec['score']} llm={same} людина={r['label']} ({ms} мс)")
    y = [r["label"] == "1" for r in test]
    base = [score(feats[(r["a_id"], r["b_id"])]) >= t for r in test]
    withj = [verdicts.get(r["pair_id"]) if verdicts.get(r["pair_id"]) is not None else b for r, b in zip(test, base)]
    dis_y = [r["label"] == "1" for r in disputed]
    res = {"margin": a.margin, "disputed": len(disputed), "threshold": t,
           "llm_agrees_with_human": sum(verdicts[r["pair_id"]] == yy for r, yy in zip(disputed, dis_y)),
           "rule_agrees_with_human": sum((score(feats[(r["a_id"], r["b_id"])]) >= t) == yy for r, yy in zip(disputed, dis_y)),
           "test_rule": prf(y, base), "test_rule_plus_llm": prf(y, withj)}
    write_json(OUT / "er_judge.json", res)
    print(json.dumps(res, ensure_ascii=False, indent=1))


# злиття / розділення
def cannot_links():
    if not CANNOT.exists():
        return set()
    with open(CANNOT, encoding="utf-8") as f:
        return {frozenset((r["a"], r["b"])) for r in csv.DictReader(f)}


def log(entry):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"), **entry}, ensure_ascii=False) + "\n")


def cmd_merge(a):
    recs, pairs = load_recs(), load_pairs()
    t = json.loads((OUT / "er_tuning.json").read_text(encoding="utf-8"))["threshold"]
    cl = cannot_links()
    parent = {r: r for r in recs}
    members = {r: {r} for r in recs}
    graph_of = {r: ({r} if recs[r]["source"] == "graph" else set()) for r in recs}
    # ідентифікатори кластера: коди (LSTM, VAR…) і номери; сутність не може містити різні (обмеження на рівні кластера,
    # захищає від транзитивного ланцюга «VAR №1» ~ «№1» ~ «LSTM №1»); --no-cluster-check вимикає (версія v1)
    codes_of = {r: set(recs[r]["codes"]) for r in recs}
    nums_of = {r: set(recs[r]["nums"][:1]) for r in recs}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    if LOG.exists():
        LOG.unlink()
    accepted = blocked_graph = blocked_cl = blocked_ids = 0
    edges = defaultdict(list)
    for p in sorted(pairs, key=lambda p: -p["score"]):
        if p["score"] < t:
            break
        ra, rb = find(p["a"]), find(p["b"])
        if ra == rb:
            continue
        if any(frozenset((x, y)) in cl for x in members[ra] for y in members[rb]):
            blocked_cl += 1
            continue
        if graph_of[ra] and graph_of[rb]:
            blocked_graph += 1                                # два різні вузли графа в одній сутності — заборонено
            continue
        if a.cluster_check and ((codes_of[ra] and codes_of[rb] and codes_of[ra] != codes_of[rb])
                                or (nums_of[ra] and nums_of[rb] and nums_of[ra] != nums_of[rb])):
            blocked_ids += 1
            continue
        parent[rb] = ra
        members[ra] |= members.pop(rb)
        graph_of[ra] |= graph_of.pop(rb)
        codes_of[ra] |= codes_of.pop(rb)
        nums_of[ra] |= nums_of.pop(rb)
        accepted += 1
        e = {"a": p["a"], "b": p["b"], "score": p["score"], "features": {k: p[k] for k in ("str", "num", "emb", "type")}}
        edges[ra].append(e)
        log({"op": "merge", **e, "decided_by": f"auto: score ≥ {t}"})
    for x in list(edges):
        r = find(x)
        if r != x:
            edges[r] += edges.pop(x)
    entities, xn = [], 0
    for root, mem in members.items():
        if find(root) != root:
            continue
        g = [m for m in mem if recs[m]["source"] == "graph"]
        if g:
            eid = recs[g[0]]["ref"]
        else:
            xn += 1
            eid = f"XE{xn:03d}"
        texts = [recs[m] for m in mem if recs[m]["source"] == "text"]
        name = recs[g[0]]["name"] if g else Counter(r["name"] for r in texts).most_common(1)[0][0]
        entities.append({"entity_id": eid, "type": recs[next(iter(mem))]["type"], "preferred_name": name,
                         "n_members": len(mem), "docs": sorted({r["doc"] for r in texts}),
                         "members": [{"rid": m, "source": recs[m]["source"], "name": recs[m]["name"],
                                      "provenance": recs[m]["provenance"], "ref": recs[m]["ref"]} for m in sorted(mem)],
                         "merge_evidence": edges.get(root, [])})
    entities.sort(key=lambda e: (e["type"], e["entity_id"]))
    # якість кластерів за еталоном (ref): скільки сутностей «чисті»
    impure = [e["entity_id"] for e in entities if len({m["ref"] for m in e["members"]}) > 1]
    n_ref = len({r["ref"] for r in recs.values()})
    stats = {"threshold": t, "records": len(recs), "entities": len(entities), "reference_entities": n_ref,
             "cluster_check": a.cluster_check, "merges": accepted, "blocked_two_graph_nodes": blocked_graph,
             "blocked_cluster_ids": blocked_ids, "blocked_cannot_link": blocked_cl,
             "impure_entities": impure,
             "records_in_impure": sum(e["n_members"] for e in entities if e["entity_id"] in impure)}
    write_json(REG, {"created": datetime.now().isoformat(timespec="seconds"), "stats": stats, "entities": entities})
    print(json.dumps(stats, ensure_ascii=False, indent=1))


def cmd_unmerge(a):
    reg = json.loads(REG.read_text(encoding="utf-8"))
    ent = next((e for e in reg["entities"] if any(m["rid"] == a.record for m in e["members"])), None)
    if ent is None:
        sys.exit(f"запис {a.record} не знайдено")
    if ent["n_members"] == 1:
        sys.exit(f"{a.record} уже окрема сутність {ent['entity_id']}")
    m = next(m for m in ent["members"] if m["rid"] == a.record)
    ent["members"] = [x for x in ent["members"] if x["rid"] != a.record]
    ent["n_members"] = len(ent["members"])
    ent["merge_evidence"] = [e for e in ent["merge_evidence"] if a.record not in (e["a"], e["b"])]
    new_id = f"XE{1 + max([int(e['entity_id'][2:]) for e in reg['entities'] if e['entity_id'].startswith('XE')] or [0]):03d}"
    reg["entities"].append({"entity_id": new_id, "type": ent["type"], "preferred_name": m["name"], "n_members": 1,
                            "docs": [m["provenance"].get("doc")], "members": [m], "merge_evidence": [],
                            "split_from": ent["entity_id"], "split_reason": a.reason})
    reg["stats"]["entities"] = len(reg["entities"])
    write_json(REG, reg)
    new = not CANNOT.exists()
    with open(CANNOT, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["a", "b", "reason", "by", "ts"])
        for x in ent["members"]:
            w.writerow([a.record, x["rid"], a.reason, a.by, datetime.now().isoformat(timespec="seconds")])
    log({"op": "unmerge", "entity": ent["entity_id"], "record": a.record, "new_entity": new_id, "reason": a.reason, "by": a.by})
    print(f"{a.record} ({m['name']}, {m['provenance'].get('doc')}) відокремлено від {ent['entity_id']} → {new_id}; "
          f"cannot-link з {len(ent['members'])} записами → {CANNOT.name}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("candidates")
    s = sub.add_parser("sample")
    s.add_argument("--force", action="store_true")
    sub.add_parser("tune")
    sub.add_parser("eval")
    j = sub.add_parser("judge")
    j.add_argument("--margin", type=float, default=0.10)
    m = sub.add_parser("merge")
    m.add_argument("--no-cluster-check", dest="cluster_check", action="store_false")
    u = sub.add_parser("unmerge")
    u.add_argument("--record", required=True)
    u.add_argument("--reason", required=True)
    u.add_argument("--by", default="Павленко А. С.")
    a = ap.parse_args()
    {"candidates": cmd_candidates, "sample": cmd_sample, "tune": cmd_tune, "eval": cmd_eval, "judge": cmd_judge,
     "merge": cmd_merge, "unmerge": cmd_unmerge}[a.cmd](a)