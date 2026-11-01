"""Метод 2: статистична spaCy-модель uk_core_news_sm (синтаксичний аналіз залежностей).

Ідея: згадки сутностей знаходимо за формою коду (№N, AMI-N, «LSTM №2», «… області»), а відношення вирішує
модель — через шлях у дереві залежностей між згадками:
  * на шляху має бути слово-тригер предиката (лема з таблиці TRIGGERS, узята зі схеми ЛР13), або
  * для «коротких» предикатів (LOCATED_IN, HAS_METER, CONNECTED_TO) — пряма синтаксична близькість (≤ 3 ребра);
  * напрям FEEDS — з синтаксичних ролей: «X живить Y» (nsubj → obj), «X живиться від Y» (obl → nsubj).
Тригери на 50 реченнях СР13 не налаштовувалися.

  python -m spacy download uk_core_news_sm
"""
import re, time
import spacy

from src.common import sentences, norm_triple, save
from src.schema import RELATION_TYPES

MODEL = "uk_core_news_sm"
TRIGGERS = {
    "FEEDS": {"живити", "живитися", "→"},
    "LOCATED_IN": {"розташувати", "розташований", "знаходитися"},
    "MANAGES": {"керувати", "відповідальний", "відповідальність"},
    "CONNECTED_TO": {"підключити", "підключений", "належати"},
    "HAS_METER": {"лічильник", "належати"},
    "FORECASTS_FOR": {"прогнозувати", "прогноз", "згенерувати", "згенерований", "скласти"},
    "INSTANCE_OF": {"тип"},
}
NEAR = {"LOCATED_IN": 3, "HAS_METER": 3, "CONNECTED_TO": 3}      # допустима відстань без тригера (ребер)
MAX_PATH = 7

METH = r"(?:ARIMA|SARIMA|VAR|LSTM|GRU)"
STEMS = r"(?:львівськ|волинськ|рівненськ|тернопільськ|закарпатськ|івано-франківськ)"
MENTIONS = [                      # (тип, регулярний вираз) — порядок = пріоритет при перекритті
    ("METER", r"AMI-\d{5}"),
    ("MODEL", METH + r"\s*№\s*\d+"),
    ("DISPATCHER", r"[Дд]испетчер\w*\s*№\s*\d+"),
    ("CONSUMER", r"Consumer_\d{4}|№\s*\d{4}(?!\d)"),
    ("SUBSTATION", r"№\s*\d{1,2}(?!\d)"),
    ("REGION", STEMS + r"\w*\s+област\w*"),
    ("METHOD", r"\b" + METH + r"\b(?!\s*№)"),
]


def mentions(doc):
    """[(тип, канонічна форма, span)] без перекриттів."""
    out, taken = [], []
    for etype, rx in MENTIONS:
        for m in re.finditer(rx, doc.text, re.I if etype == "REGION" else 0):
            a, b = m.span()
            if any(a < y and x < b for x, y in taken):
                continue
            span = doc.char_span(a, b, alignment_mode="expand")
            if span is None:
                continue
            taken.append((a, b))
            out.append((etype, m.group(0), span))
    return out


def path(a, b):
    """Токени шляху a … LCA … b у дереві залежностей."""
    up_a = [a] + list(a.ancestors)
    up_b = [b] + list(b.ancestors)
    ids_b = [t.i for t in up_b]
    for k, t in enumerate(up_a):
        if t.i in ids_b:
            return up_a[:k + 1] + list(reversed(up_b[:ids_b.index(t.i)]))
    return []


def feeds_direction(p, x, y):
    """Для шляху x…y з тригером «живити/живитися» повертає (джерело, споживач) або None."""
    for k, v in enumerate(p):
        if v.lemma_ not in ("живити", "живитися"):
            continue
        cx = p[k - 1] if k > 0 else None              # дочірній токен дієслова на боці x
        cy = p[k + 1] if k + 1 < len(p) else None     # на боці y
        if cx is None or cy is None:
            return None
        role = lambda c: "subj" if c.dep_.startswith("nsubj") else ("obl" if c.dep_.startswith("obl") else
                                                                     ("obj" if c.dep_ in ("obj", "iobj") else ""))
        rx, ry = role(cx), role(cy)
        if v.lemma_ == "живити":
            return (x, y) if (rx, ry) == ("subj", "obj") else (y, x) if (rx, ry) == ("obj", "subj") else None
        return (y, x) if (rx, ry) == ("subj", "obl") else (x, y) if (rx, ry) == ("obl", "subj") else None
    if any(t.text == "→" for t in p) and len(p) <= 4:   # «№7 → №5»: напрям за порядком у тексті
        return (x, y) if x.i < y.i else (y, x)
    return None


def extract(nlp, text):
    doc = nlp(text)
    ms = mentions(doc)
    out = set()
    for pred, (ht, tt) in RELATION_TYPES.items():
        for t1, v1, s1 in ms:
            for t2, v2, s2 in ms:
                if (t1, t2) != (ht, tt) or s1 == s2:
                    continue
                p = path(s1.root, s2.root)
                if not p or len(p) - 1 > MAX_PATH:
                    continue
                lem = {t.lemma_.lower() for t in p} | {t.text for t in p}
                has_trig = bool(lem & TRIGGERS[pred])
                if pred == "FEEDS":
                    d = feeds_direction(p, s1.root, s2.root) if has_trig else None
                    if d and d[0] == s1.root:
                        out.add(norm_triple(v1, pred, v2))
                    continue
                if has_trig or len(p) - 1 <= NEAR.get(pred, 0):
                    out.add(norm_triple(v1, pred, v2))
    return out - {None}


def main():
    t0 = time.time()
    nlp = spacy.load(MODEL)
    load_s = time.time() - t0
    rows, t1 = [], time.time()
    for s in sentences():
        ts = time.time()
        rows.append({"id": s["id"], "triples": sorted(extract(nlp, s["text"])), "seconds": round(time.time() - ts, 4)})
    sec = time.time() - t1
    save("spacy", rows, {"method": "spacy", "model": f"{MODEL}-{nlp.meta['version']}", "spacy": spacy.__version__,
                         "sentences": len(rows), "seconds": round(sec, 3), "seconds_per_sentence": round(sec / len(rows), 4),
                         "load_seconds": round(load_s, 2), "tokens": 0, "cost_uah": 0})


if __name__ == "__main__":
    main()
