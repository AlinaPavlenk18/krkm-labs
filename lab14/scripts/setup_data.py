"""Знімок сховища (baseline) для ЛР14: копіює дані ЛР8–ЛР13 у lab14/data і записує контрольні суми.

  data/store/triples.csv        — RDF-трійки ЛР9 з provenance (source, confidence, valid_from)
  data/store/graph/*.csv        — граф Neo4j ЛР9 (вузли й зв'язки, те, що читає RAG у режимі «текст + граф»)
  data/store/ontology/*.ttl     — словник і SHACL-форми ЛР8
  data/corpus/docs.jsonl        — корпус RAG ЛР11 (30 документів)
  data/lab13/*.jsonl            — витягнуті сутності ЛР13 (правила, LLM), золотий набір, тексти
  data/rag_baseline/            — тестовий набір і baseline-метрики RAG ЛР11
Запуск (з папки lab14):  python scripts/setup_data.py
"""
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
REPO = LAB.parent
DATA = LAB / "data"

COPY = [
    ("lab09/data/triples_final.csv", "store/triples.csv"),
    ("lab09/data/source/lab08_vocabulary.ttl", "store/ontology/lab08_vocabulary.ttl"),
    ("lab09/data/source/lab08_shapes.ttl", "store/ontology/lab08_shapes.ttl"),
    ("lab11/data/clean/docs.jsonl", "corpus/docs.jsonl"),
    ("lab13/data/extracted.jsonl", "lab13/extracted_rules.jsonl"),
    ("lab13/results/llm_dev.jsonl", "lab13/extracted_llm_dev.jsonl"),
    ("lab13/results/llm_test.jsonl", "lab13/extracted_llm_test.jsonl"),
    ("lab13/data/gold.jsonl", "lab13/gold.jsonl"),
    ("lab13/data/docs.jsonl", "lab13/docs.jsonl"),
    ("lab11/eval/rag_eval.jsonl", "rag_baseline/rag_eval.jsonl"),
    ("lab11/results/baseline/summary.json", "rag_baseline/summary.json"),
    ("lab11/results/baseline/records.jsonl", "rag_baseline/records.jsonl"),
]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def main():
    files = {}
    for src, dst in COPY:
        s, d = REPO / src, DATA / dst
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(s, d)
        files[dst] = {"from": src, "sha256_16": sha(d)}
    for s in sorted((REPO / "lab11/data/graph").glob("*.csv")):
        d = DATA / "store/graph" / s.name
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(s, d)
        files[f"store/graph/{s.name}"] = {"from": f"lab11/data/graph/{s.name}", "sha256_16": sha(d)}
    manifest = {"snapshot": "baseline", "created": datetime.now().isoformat(timespec="seconds"), "files": files}
    (DATA / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Скопійовано {len(files)} файлів → {DATA}")


if __name__ == "__main__":
    main()
