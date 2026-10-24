"""Результат 1: очищення документів і корпус фрагментів з метаданими.

Вихід:
  data/clean/docs.jsonl    — очищені документи з секціями (вхід для всіх стратегій chunking);
  data/corpus.jsonl        — базові фрагменти (структурна стратегія) з метаданими
                             doc_id, title, section, type, date, sensitivity, source_url (+ license, origin);
  results/r1_corpus_stats.json — кількості, розподіли, спрацювання правил очищення.
Запуск: python scripts/r1_build_corpus.py
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from common import CLEAN, DATA, RESULTS, write_json, write_jsonl  # noqa: E402
from clean import load_documents  # noqa: E402
from chunking import chunk_structural  # noqa: E402

CORPUS_FIELDS = ["chunk_id", "doc_id", "title", "section", "type", "date", "sensitivity", "source_url",
                 "license", "origin", "doc_sensitivity", "n_words", "text"]


def main():
    docs, stats = load_documents()
    write_jsonl(CLEAN / "docs.jsonl", docs)
    chunks = chunk_structural(docs)
    corpus = [{k: c[k] for k in CORPUS_FIELDS} for c in chunks]
    # у корпусі ідентифікатор фрагмента без префікса стратегії: kb06#003
    for c in corpus:
        c["chunk_id"] = c["chunk_id"].replace("#str", "#")
    write_jsonl(DATA / "corpus.jsonl", corpus)

    raw_words = 0
    for d in docs:
        raw_words += sum(len(s["text"].split()) for s in d["sections"])
    upgraded = [c["chunk_id"] for c in corpus if c["sensitivity"] != c["doc_sensitivity"]]
    out = {
        "documents": len(docs),
        "fragments": len(corpus),
        "words_total": raw_words,
        "words_per_fragment": {"mean": round(sum(c["n_words"] for c in corpus) / len(corpus), 1),
                               "min": min(c["n_words"] for c in corpus), "max": max(c["n_words"] for c in corpus)},
        "by_origin": Counter(d["origin"].split(" ")[0] for d in docs),
        "docs_by_type": Counter(d["type"] for d in docs),
        "docs_by_sensitivity": Counter(d["sensitivity"] for d in docs),
        "fragments_by_sensitivity": Counter(c["sensitivity"] for c in corpus),
        "fragments_upgraded_to_restricted": upgraded,
        "cleaning_rules": dict(sorted(stats.items())),
        "per_document": [{"doc_id": d["doc_id"], "title": d["title"], "type": d["type"], "sensitivity": d["sensitivity"],
                          "date": d["date"], "sections": len(d["sections"]),
                          "fragments": sum(1 for c in corpus if c["doc_id"] == d["doc_id"])} for d in docs],
    }
    write_json(RESULTS / "r1_corpus_stats.json", out)
    print(f"документів: {out['documents']}, фрагментів: {out['fragments']}, слів: {raw_words}")
    print("за рівнем доступу (фрагменти):", dict(out["fragments_by_sensitivity"]))
    print("правила очищення:", out["cleaning_rules"])


if __name__ == "__main__":
    main()
