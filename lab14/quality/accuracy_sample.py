"""Р1, метрика «точність»: експертна вибірка 30 тверджень корпусу про сутності графа.

Твердження = речення з публічних/внутрішніх документів, що згадує сутність графа (підстанція, модель, лічильник,
диспетчер, споживач) і містить число. Вибірка стратифікована за групами документів (kb 12, gen 10, prj 8), seed 42.
Колонка graph_hint — значення з графа ЛР9 для згаданих сутностей (підказка; рішення приймає експерт).

  python quality/accuracy_sample.py            # → quality/accuracy_sample.csv (не перезаписує заповнений файл)
Заповнити expert_ok = 1 (твердження правильне за графом / первинним джерелом) або 0 і expert_comment.
"""
import csv
import random
import re
import sys

from common import QUALITY, SEED, load_corpus, load_graph, sections
from facts import SENT_RE

OUT = QUALITY / "accuracy_sample.csv"
QUOTA = {"kb": 12, "gen": 10, "prj": 8}

ENT = [
    (re.compile(r"(?:[Пп]ідстанц\w*|ПС)\s?№\s?(\d{1,2})\b"), "substation", "Substation_{}"),
    (re.compile(r"\b(LSTM|GRU|VAR|ARIMA)\s?№\s?(\d)"), "forecastmodel", "ForecastModel_{}{}"),
    (re.compile(r"\bAMI-(\d{5})"), "meter", "Meter_AMI{}"),
    (re.compile(r"[Дд]испетчер\w*\s?№\s?(\d)"), "dispatcher", "Dispatcher_{}"),
    (re.compile(r"[Сс]поживач\w*\s?№\s?(\d{4})"), "consumer", "Consumer_{}"),
]
HIDE = {"address", "source", "name"}


def entities(sent):
    out = []
    for rx, label, tpl in ENT:
        for m in rx.finditer(sent):
            out.append((label, tpl.format(*m.groups())))
    return list(dict.fromkeys(out))


def hint(nodes, ents):
    idx = {lab: {n["id"]: n for n in rows} for lab, rows in nodes.items()}
    parts = []
    for lab, eid in ents:
        n = idx.get(lab, {}).get(eid)
        if n is None:
            parts.append(f"{eid}: немає в графі")
        else:
            parts.append(f"{eid}: " + ", ".join(f"{k}={v}" for k, v in n.items() if k not in HIDE and k != "id" and v))
    return " | ".join(parts)


def main():
    if OUT.exists() and any(r.get("expert_ok") for r in csv.DictReader(open(OUT, encoding="utf-8-sig"), delimiter=";")):
        sys.exit(f"{OUT} уже заповнено експертом — не перезаписую")
    nodes, _ = load_graph()
    pool = {g: [] for g in QUOTA}
    for d, i, title, text in sections(load_corpus()):
        if d["sensitivity"] == "restricted":
            continue
        grp = re.match(r"[a-z]+", d["doc_id"]).group(0)
        for sent in SENT_RE.split(text):
            sent = sent.strip()
            ents = entities(sent)
            if ents and re.search(r"\d", re.sub(r"№\s?\d+|AMI-\d+|ЛР\d+|Q\d+|KQ\d+", "", sent)) and 40 <= len(sent) <= 400:
                pool[grp].append((d["doc_id"], title, sent, ents))
    rnd = random.Random(SEED)
    rows = []
    for g, k in QUOTA.items():
        for doc_id, title, sent, ents in rnd.sample(pool[g], k):
            rows.append({"id": f"A{len(rows) + 1:02d}", "doc_id": doc_id, "section": title, "statement": sent,
                         "graph_hint": hint(nodes, ents), "expert_ok": "", "expert_comment": ""})
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=";")
        w.writeheader()
        w.writerows(rows)
    print(f"Пул: {', '.join(f'{g}={len(v)}' for g, v in pool.items())}; вибірка {len(rows)} → {OUT}")


if __name__ == "__main__":
    main()
