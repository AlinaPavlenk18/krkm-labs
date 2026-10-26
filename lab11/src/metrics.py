"""Метрики пошуку на золотому наборі (Результати 2, 3, 5).

Релевантність задано не id фрагментів, а «доказами» (evidence): короткими точними цитатами з документа,
що містять відповідь (eval/gold.jsonl). Так одну розмітку можна застосувати до будь-якої стратегії chunking.
Фрагмент покриває доказ, якщо він з того самого документа і містить нормалізований текст доказу,
або (коли доказ розрізано межею фрагмента) містить неперервний уривок доказу довжиною ≥ 75 % його слів.

Одиниця релевантності — доказ (grade 2 = пряма відповідь, 1 = часткова/допоміжна).
  recall@k  = частка доказів, покритих топ-k фрагментами;
  MRR       = 1 / ранг першого фрагмента, що покриває будь-який доказ (0, якщо немає в топ-10);
  nDCG@10   = DCG / IDCG, де gain фрагмента = найбільша оцінка ще не покритого ним доказу
              (повторне покриття того самого доказу виграшу не дає), IDCG — докази в ідеальному порядку.
Запити без відповіді (answerable = false) у середні recall/MRR/nDCG не входять; для них окремо
рахується частка випадків, коли reranker «утримався» (найкращий бал нижче порогу).
"""
import math

from common import normalize

COVER_THRESHOLD = 0.75


def covers(chunk_text, chunk_doc, ev):
    if chunk_doc != ev["doc_id"]:
        return False
    t, e = normalize(chunk_text), normalize(ev["evidence"])
    if e in t:
        return True

    ew, tw = e.split(), t.split()
   
    tset = set(tw)
    if any(any(ch.isdigit() for ch in w) and w.strip(".,;:()«»") not in {x.strip(".,;:()«»") for x in tset} for w in ew):
        return False
    if len(ew) < 6:         
        return False
    best, pos = 0, {}
    for i, w in enumerate(tw):
        pos.setdefault(w, []).append(i)
    for a in range(len(ew)):
        for i in pos.get(ew[a], []):
            n = 0
            while a + n < len(ew) and i + n < len(tw) and ew[a + n] == tw[i + n]:
                n += 1
            best = max(best, n)
    return best / len(ew) >= COVER_THRESHOLD


def judge(hits_texts, hits_docs, evidences):
   
    return [{j for j, ev in enumerate(evidences) if covers(t, d, ev)} for t, d in zip(hits_texts, hits_docs)]


def recall_at(cov, evidences, k):
    if not evidences:
        return None
    found = set().union(*cov[:k]) if cov[:k] else set()
    return len(found) / len(evidences)


def mrr(cov, k=10):
    for r, s in enumerate(cov[:k], start=1):
        if s:
            return 1.0 / r
    return 0.0


def ndcg_at(cov, evidences, k=10):
    if not evidences:
        return None
    seen, dcg = set(), 0.0
    for r, s in enumerate(cov[:k], start=1):
        new = s - seen
        if new:
            dcg += max(evidences[j]["grade"] for j in new) / math.log2(r + 1)
            seen |= new
    ideal = sorted((ev["grade"] for ev in evidences), reverse=True)[:k]
    idcg = sum(g / math.log2(r + 1) for r, g in enumerate(ideal, start=1))
    return dcg / idcg if idcg else 0.0


def evaluate_run(results, gold):
    per = {}
    for g in gold:
        if not g["answerable"]:
            continue
        hits = results[g["qid"]]
        cov = judge([h[0] for h in hits], [h[1] for h in hits], g["relevant"])
        per[g["qid"]] = {"recall@5": recall_at(cov, g["relevant"], 5), "recall@10": recall_at(cov, g["relevant"], 10),
                         "mrr": mrr(cov, 10), "ndcg@10": ndcg_at(cov, g["relevant"], 10),
                         "first_rel_rank": next((r for r, s in enumerate(cov, 1) if s), None)}
    keys = ["recall@5", "recall@10", "mrr", "ndcg@10"]
    mean = {k: round(sum(p[k] for p in per.values()) / len(per), 4) for k in keys}
    mean["n_queries"] = len(per)
    return mean, per


def by_type(per, gold, key):
    out = {}
    for g in gold:
        if g["qid"] in per:
            out.setdefault(g["qtype"], []).append(per[g["qid"]][key])
    return {t: round(sum(v) / len(v), 3) for t, v in out.items()}
