"""Метод 1: правила/шаблони (spaCy EntityRuler + регулярні вирази) — правила ЛР13 rules_v2 без змін.

  python -m src.m1_rules        
"""
import time
import spacy

from src.common import sentences, norm_triple, save
from src.lr13_rules import build_nlp, relations, VERSION

WRAP = "# Речення\n\n"        


def main():
    t0 = time.time()
    nlp = build_nlp()
    load_s = time.time() - t0
    rows, t1 = [], time.time()
    for s in sentences():
        ts = time.time()
        trip = {norm_triple(h, p, t) for p, h, t, _, _ in relations(nlp, WRAP + s["text"])} - {None}
        rows.append({"id": s["id"], "triples": sorted(trip), "seconds": round(time.time() - ts, 4)})
    sec = time.time() - t1
    save("rules", rows, {"method": "rules", "version": VERSION, "spacy": spacy.__version__, "sentences": len(rows),
                         "seconds": round(sec, 3), "seconds_per_sentence": round(sec / len(rows), 4),
                         "load_seconds": round(load_s, 2), "tokens": 0, "cost_uah": 0})


if __name__ == "__main__":
    main()
