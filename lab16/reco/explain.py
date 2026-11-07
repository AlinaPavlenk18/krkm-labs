"""Пояснення рекомендацій зі шляху графа + LLM-перефразування з автоматичною перевіркою.

шлях: найкоротший (з штрафом за вузли-«хаби») від переглянутого розділу або сутності профілю до рекомендованого;
шаблон: детермінований текст зі шляху (завжди правдивий);
LLM (qwen2.5:7b, локально, t = 0, seed 42) лише перефразовує шаблон; перевірка: усі сутності (ПС, моделі, диспетчери,
регіони) і всі числа в тексті LLM мають бути в шляху, і текст згадує ≥ 1 сутність шляху. Інакше — шаблон.
  python -m reco.explain --users 10 --k 5      → results/explanations.jsonl, results/explain_summary.json
"""
import argparse
import json
import math
import os
import re

import networkx as nx
import requests

from reco.data import LAB, build_graph, entities_of, label, load_items

OLLAMA = os.environ.get("GEN_BASE_URL", "http://localhost:11434")
MODEL = os.environ.get("GEN_MODEL", "qwen2.5:7b")
FAKE = os.environ.get("RECO_FAKE_LLM") == "1"
PROMPTS = {v: (LAB / "prompts" / f"explain_{v}.md").read_text(encoding="utf-8") for v in ("v1", "v2")}
PROMPT = PROMPTS["v1"]
SLOT = re.compile(r"\[(A|B|E\d)\]")
CLAIM_B = re.compile(r"(переглядал|читал|бачил|знайшл|ознайомил)\w*[^.;]{0,60}\[B\]", re.I)
NUM = re.compile(r"\d+(?:[.,]\d+)?")


def find_path(rec, history_items=(), profile=(), max_len=5):
    g = build_graph()
    src = [s for s in list(dict.fromkeys(history_items))[::-1] + list(profile) if s in g and s != rec]
    if not src or rec not in g:
        return None
    w = lambda u, v, d: 1 + 0.5 * math.log1p(g.degree(v))       # хаби («прогноз», «споживачі») дорожчі
    try:
        _, path = nx.multi_source_dijkstra(g, set(src), target=rec, weight=w)
    except nx.NetworkXNoPath:
        return None
    return path if len(path) - 1 <= max_len else None


def template(path):
    """Детермінований текст зі шляху: кожне ребро — одне речення-фрагмент, нічого поза шляхом."""
    g = build_graph()
    first = path[0]
    parts = [f"ви переглядали {label(first)}" if g.nodes[first]["kind"] == "item" else f"у вашому профілі є {label(first)}"]
    for a, b in zip(path, path[1:]):
        rel = g.edges[a, b]["rel"]
        last = b == path[-1]
        tgt = f"рекомендованому розділі {label(b)}" if last else label(b)
        if rel == "згадує" and g.nodes[a]["kind"] == "item":
            parts.append(f"цей розділ згадує {label(b)}")
        elif rel == "згадує":
            parts.append(f"{label(a)} згадується в {tgt}")
        elif rel == "наступний розділ":
            after = load_items()[b]["pos"] > load_items()[a]["pos"]
            where = "далі в тому самому документі йде" if after else "перед ним у тому самому документі йде"
            parts.append(f"{where} {label(b) if not last else 'рекомендований розділ ' + label(b)}")
        else:
            parts.append(f"{label(a)} {rel} {label(b)}")
    return "Рекомендовано, бо " + "; ".join(parts) + "."


def path_vocab(path):
    ents, nums = set(), set()
    for n in path:
        if not n.startswith("C:") and (n.startswith(("Substation_", "Dispatcher_", "ForecastModel_", "Region_"))):
            ents.add(n)
        lab = label(n)
        ents |= {e for e in entities_of(lab) if not e.startswith("C:")}
        nums |= set(NUM.findall(lab))
    return ents, nums


def check(text, path):
    ents, nums = path_vocab(path)
    found = {e for e in entities_of(text) if not e.startswith("C:")}
    extra_e = sorted(found - ents)
    extra_n = sorted(set(NUM.findall(text)) - nums)
    ok = not extra_e and not extra_n and bool(found & ents or not ents)
    return ok, {"extra_entities": extra_e, "extra_numbers": extra_n}


def paraphrase(tmpl, prompt=None):
    if FAKE:
        return tmpl.replace("Рекомендовано, бо ви переглядали", "Рекомендовано, бо раніше ви читали")
    r = requests.post(f"{OLLAMA}/api/chat", timeout=300, json={
        "model": MODEL, "stream": False, "options": {"temperature": 0, "seed": 42, "num_predict": 160},
        "messages": [{"role": "system", "content": prompt or PROMPT}, {"role": "user", "content": "Ланцюжок: " + tmpl}]})
    r.raise_for_status()
    return r.json()["message"]["content"].strip()


def slots(path):
    """Мітки для вузлів шляху: [A] — перший, [B] — рекомендований, [E1]… — проміжні."""
    names = {path[0]: "A", path[-1]: "B"}
    k = 0
    for n in path[1:-1]:
        if n not in names:
            k += 1
            names[n] = f"E{k}"
    return names


def slot_chain(path):
    g = build_graph()
    nm = slots(path)
    out = []
    for a, b in zip(path, path[1:]):
        rel = g.edges[a, b]["rel"]
        A, B = f"[{nm[a]}]", f"[{nm[b]}]"
        if rel == "згадує":
            out.append(f"{A} згадує {B}" if g.nodes[a]["kind"] == "item" else f"{A} згадується в {B}")
        elif rel == "наступний розділ":
            after = load_items()[b]["pos"] > load_items()[a]["pos"]
            out.append(f"{A} — розділ документа, {'після' if after else 'перед'} якого йде {B}")
        else:
            out.append(f"{A} {rel} {B}")
    return "; ".join(out)


def check_slots(text, path):
    """Перевірка v2: усі мітки присутні, перші входження — у порядку шляху; поза мітками — жодних сутностей і чисел; [B] не «переглянуто»."""
    order = [f"[{x}]" for x in dict.fromkeys(slots(path)[n] for n in path)]
    found = [m.group(0) for m in SLOT.finditer(text)]
    rest = SLOT.sub(" ", text)
    why = {"slots": found, "expected": order,
           "extra_entities": sorted(e for e in entities_of(rest) if not e.startswith("C:")),
           "extra_numbers": NUM.findall(rest), "claims_B_seen": bool(CLAIM_B.search(text)),
           "plural_A": bool(re.search(r"розділи\s+\[A\]", text))}
    ok = list(dict.fromkeys(found)) == order and not why["extra_entities"] and not why["extra_numbers"] and not why["claims_B_seen"] \
        and not why["plural_A"]
    return ok, why


def fill(text, path):
    nm = {f"[{v}]": label(k) for k, v in slots(path).items()}
    return SLOT.sub(lambda m: nm[m.group(0)], text)


def explain(rec, history_items=(), profile=(), use_llm=True, mode="slots"):
    path = find_path(rec, history_items, profile)
    if not path:
        return {"item": rec, "path": None, "template": None, "llm": None, "llm_ok": None,
                "final": "Рекомендовано за схожістю змісту або популярністю; шляху в графі знань немає.", "source": "no_path"}
    tmpl = template(path)
    out = {"item": rec, "path": path, "template": tmpl, "llm": None, "llm_ok": None, "final": tmpl, "source": "template",
           "mode": mode}
    if use_llm and mode == "free":                     # v1: вільне перефразування + перевірка сутностей
        txt = paraphrase(tmpl, PROMPTS["v1"])
        ok, why = check(txt, path)
        out.update({"llm": txt, "llm_ok": ok, "check": why})
        if ok:
            out.update({"final": txt, "source": "llm"})
    elif use_llm:                                      # v2: LLM пише лише сполучні слова навколо міток
        chain = slot_chain(path)
        txt = ("Рекомендовано, бо " + chain + ".") if FAKE else paraphrase(chain, PROMPTS["v2"])
        ok, why = check_slots(txt, path)
        out.update({"llm": txt, "slot_chain": chain, "llm_ok": ok, "check": why})
        if ok:
            out.update({"final": fill(txt, path), "source": "llm"})
    return out


def main():
    import numpy as np
    from reco.eval import CUT, END, load, rrf, ranked, split
    from reco.models import EmbeddingKNN, GraphPPR, Popularity
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, default=10)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--mode", choices=["free", "slots"], default="slots")
    a = ap.parse_args()
    suf = "" if a.mode == "free" else "_v2"
    ev_json = json.loads((LAB / "results" / "eval.json").read_text(encoding="utf-8"))["seed42"]
    w, kk = ev_json["hybrid_weights"], ev_json["rrf_k"]
    users, ev = load(42)
    train, hist, rel = split(ev, CUT, END)
    warm = [u for u in sorted(users) if hist.get(u) and rel.get(u)]
    rng = np.random.default_rng(42)
    sample = sorted(rng.choice(warm, size=min(a.users, len(warm)), replace=False))
    models = {"popularity": Popularity().fit(train), "graph": GraphPPR(), "embedding": EmbeddingKNN()}
    rows = []
    for u in sample:
        ctx = {"role": users[u]["role"], "history": hist[u], "now": CUT, "profile": []}
        recs = ranked(rrf({n: m.scores(ctx) for n, m in models.items()}, w, kk), ctx, a.k)
        for i in recs:
            e = explain(i, [x for x, _ in sorted(hist[u], key=lambda y: y[1])], mode=a.mode)
            e.update({"user": u, "relevant_in_test": i in rel[u]})
            rows.append(e)
            print(f"{u} {i:<10} {e['source']:<8} ok={e['llm_ok']}  {e['final'][:150]}")
    with open(LAB / "results" / f"explanations{suf}.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with_path = [r for r in rows if r["path"]]
    llm = [r for r in with_path if r["llm_ok"] is not None]
    summ = {"recommendations": len(rows), "with_path": len(with_path),
            "path_share": round(len(with_path) / len(rows), 3),
            "avg_path_len": round(sum(len(r["path"]) - 1 for r in with_path) / max(1, len(with_path)), 2),
            "llm_checked": len(llm), "llm_faithful": sum(r["llm_ok"] for r in llm),
            "llm_faithful_share": round(sum(r["llm_ok"] for r in llm) / max(1, len(llm)), 3),
            "final_faithful_share": round(sum(r["source"] in ("llm", "template") for r in rows) / len(rows), 3),
            "model": MODEL, "params": {"temperature": 0, "seed": 42},
            "prompt": "explain_v1" if a.mode == "free" else "explain_v2", "mode": a.mode}
    (LAB / "results" / f"explain_summary{suf}.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
