"""Результат 3, крок 4: перевірка оновлення індексу (upsert / delete) на 5 документах.

Операції (у пам'яті; файли корпусу не змінюються):
  1. upsert kb08 — змінено тривалість паралельної експлуатації: 7 діб -> 14 діб;
  2. upsert kb06 — підстанції №9 призначено диспетчера №6;
  3. upsert gen02 — модель LSTM №2 перенавчено: точність 78 % -> 88 %;
  4. delete prj08 — документ з результатами бенчмарку СР9 вилучено з бази знань;
  5. upsert kb16 (новий документ) — регламент роботи в період зимового максимуму.
Для кожної операції — контрольний запит ДО і ПІСЛЯ: чи є в топ-5 новий текст і чи зник старий.
Потім compact() (перебудова без надгробків) і повторна перевірка всіх запитів.
Вихід: results/r3_upsert.json
Запуск: python scripts/r3_upsert.py [--model e5-small] [--strategy structural]
"""
import argparse
import copy
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from common import CLEAN, RESULTS, normalize, read_json, read_jsonl, write_json  # noqa: E402
import chunking  # noqa: E402
from encoders import STUB, Encoder  # noqa: E402
from index import build_store  # noqa: E402

NEW_DOC = {
    "doc_id": "kb16", "title": "Регламент роботи в період зимового максимуму навантаження", "type": "regulation",
    "date": "2026-10-23", "sensitivity": "internal", "license": "CC BY 4.0 (Павленко А. С.)", "origin": "kb_article (тест upsert)",
    "source_url": "https://github.com/AlinaPavlenk18/krkm-labs/blob/main/lab10/data/raw/kb/kb16_winter_peak.md",
    "sections": [{"section": "Зимовий максимум", "text": "Період зимового максимуму триває з 1 грудня по 28 лютого. "
                  "У цей період диспетчер щодня до 16:00 перевіряє прогноз на вечірній пік і резерв потужності кожної підстанції своєї зони."}],
}


def edit(doc, old, new):
    d = copy.deepcopy(doc)
    hit = False
    for s in d["sections"]:
        if old in s["text"]:
            s["text"] = s["text"].replace(old, new); hit = True
    assert hit, f"{doc['doc_id']}: не знайдено «{old}»"
    d["date"] = "2026-10-23"
    return d


OPS = [
    ("upsert", "kb08", lambda d: edit(d, "працює паралельно зі старою протягом 7 діб", "працює паралельно зі старою протягом 14 діб"),
     "Скільки діб нова версія моделі працює паралельно зі старою?", "протягом 14 діб", "протягом 7 діб"),
    ("upsert", "kb06", lambda d: edit(d, "Підстанція №9 у Закарпатській області не має призначеного диспетчера.",
                                      "Підстанції №9 у Закарпатській області з 20 жовтня 2026 року призначено диспетчера №6."),
     "Хто відповідає за підстанцію №9?", "призначено диспетчера №6", "не має призначеного диспетчера"),
    ("upsert", "gen02", lambda d: edit(d, "Дата навчання 20.06.2025, точність 78 %", "Дата навчання 22.10.2026, точність 88 %"),
     "Яка точність моделі LSTM №2 після перенавчання?", "точність 88 %", "точність 78 %"),
    ("delete", "prj08", None, "Результати бенчмарку Memgraph медіана p90", None, "memgraph (мс, медіана / p90)"),
    ("upsert", "kb16", lambda d: NEW_DOC, "Коли диспетчер перевіряє прогноз на вечірній пік узимку?", "до 16:00 перевіряє прогноз", None),
]


def topk_texts(store, enc, q, k=5):
    hits = store.search(enc.encode_queries([q]), k)[0]
    return [(store.meta[i]["doc_id"], store.meta[i]["text"]) for i, _ in hits]


def has(texts, s, doc_id=None):
    """Чи містить топ-5 рядок s (для старого тексту — лише у фрагментах того самого документа)."""
    return s is not None and any(normalize(s) in normalize(t) for d, t in texts if doc_id is None or d == doc_id)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="e5-small")
    ap.add_argument("--strategy", default=None)
    args = ap.parse_args()
    strat = args.strategy or (read_json(RESULTS / "r2_chunking.json")["auto_choice"] if (RESULTS / "r2_chunking.json").exists() else "structural")
    if strat == "hierarchical":
        strat = "structural"   # тест оновлення робимо на пласких фрагментах
    docs = {d["doc_id"]: d for d in read_jsonl(CLEAN / "docs.jsonl")}
    enc = Encoder(args.model)
    units, _ = chunking.build(strat, list(docs.values()), encoder=enc if strat == "semantic" else None)
    store = build_store(units, enc.encode_passages([u["embed_text"] for u in units]))
    log = {"model": args.model, "strategy": strat, "stub": STUB, "size_before": len(store), "ops": []}
    for op, doc_id, fn, query, new_s, old_s in OPS:
        before = topk_texts(store, enc, query)
        t = time.perf_counter()
        if op == "delete":
            removed = store.delete(doc_id); added = []
        else:
            nd = fn(docs.get(doc_id))
            ch, _ = chunking.build(strat, [nd], encoder=enc if strat == "semantic" else None)
            vec = enc.encode_passages([c["embed_text"] for c in ch], cache=False)
            removed, added = store.upsert(doc_id, ch, vec)
        ms = (time.perf_counter() - t) * 1000
        after = topk_texts(store, enc, query)
        rec = {"op": op, "doc_id": doc_id, "query": query, "removed_vectors": len(removed), "added_vectors": len(added),
               "ms": round(ms, 1), "index_size": len(store),
               "before": {"new_in_top5": has(before, new_s), "old_in_top5": has(before, old_s, doc_id), "docs": [d for d, _ in before]},
               "after": {"new_in_top5": has(after, new_s), "old_in_top5": has(after, old_s, doc_id), "docs": [d for d, _ in after]}}
        ok = (new_s is None or rec["after"]["new_in_top5"]) and not rec["after"]["old_in_top5"]
        if op == "delete":
            ok = ok and doc_id not in rec["after"]["docs"]
        rec["passed"] = ok
        log["ops"].append(rec)
        print(f"{op:6s} {doc_id:5s} -{len(removed)} +{len(added)}  до: нове={rec['before']['new_in_top5']} старе={rec['before']['old_in_top5']}  "
              f"після: нове={rec['after']['new_in_top5']} старе={rec['after']['old_in_top5']}  {'OK' if ok else 'FAIL'}")
    log["tombstone_ratio_before_compact"] = round(store.tombstone_ratio(), 4)
    t = time.perf_counter()
    store.compact()
    log["compact_ms"] = round((time.perf_counter() - t) * 1000, 1)
    log["size_after_compact"] = len(store)
    recheck = []
    for op, doc_id, fn, query, new_s, old_s in OPS:
        after = topk_texts(store, enc, query)
        recheck.append((new_s is None or has(after, new_s)) and not has(after, old_s, doc_id))
    log["after_compact_all_passed"] = all(recheck)
    log["all_passed"] = all(o["passed"] for o in log["ops"]) and log["after_compact_all_passed"]
    write_json(RESULTS / "r3_upsert.json", log)
    print(f"надгробків {log['tombstone_ratio_before_compact']:.1%}, compact {log['compact_ms']} мс, "
          f"після compact усе OK: {log['after_compact_all_passed']}; разом: {log['all_passed']}")


if __name__ == "__main__":
    main()
