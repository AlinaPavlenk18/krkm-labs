"""Спільне: читання речень і розмітки, нормалізація трійок (s, p, o), запис результатів методів.

Трійка в розмітці пишеться коротко: «1 FEEDS 10», «LSTM2 FORECASTS_FOR 11», «3310 HAS_METER 77410»,
«1 LOCATED_IN Львівська», «LSTM1 INSTANCE_OF LSTM»; повні ID («Substation_1») теж приймаються.
Кілька трійок — через «;», речення без відношень — «-».
"""
import csv, json, re
from pathlib import Path

from src.schema import RELATION_TYPES, canonical

ROOT = Path(__file__).resolve().parents[1]
PREDICATES = list(RELATION_TYPES)          # FEEDS, LOCATED_IN, MANAGES, CONNECTED_TO, HAS_METER, FORECASTS_FOR, INSTANCE_OF


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


def grounded(triple, text):
    """Чи названо і s, і o в реченні."""
    h, p, t = triple
    ht, tt = RELATION_TYPES[p]
    return bool(re.search(mention_re(ht, h), text, re.I) and re.search(mention_re(tt, t), text, re.I))


def sentences():
    with open(ROOT / "data/sentences.csv", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))


def norm_triple(s, p, o):
    """(s, p, o) у канонічних ID графа ЛР9 або None, якщо предикат чи типи не відповідають схемі."""
    p = str(p).strip().upper()
    if p not in RELATION_TYPES:
        return None
    ht, tt = RELATION_TYPES[p]
    h, t = canonical(ht, str(s)), canonical(tt, str(o))
    return (h, p, t) if h and t and h != t else None


def parse_cell(cell):
    """Клітинка розмітки → множина нормалізованих трійок; ValueError, якщо щось не розібрано."""
    cell = (cell or "").strip()
    if cell == "-":
        return set()
    if not cell:
        raise ValueError("порожня клітинка (для речення без відношень поставте «-»)")
    out = set()
    for part in cell.split(";"):
        toks = part.split()
        if not toks:
            continue
        if len(toks) < 3:
            raise ValueError(f"не трійка: «{part.strip()}»")
        tr = norm_triple(toks[0], toks[1], " ".join(toks[2:]))
        if not tr:
            raise ValueError(f"не нормалізується за схемою: «{part.strip()}»")
        out.add(tr)
    return out


def gold(path="data/gold.csv"):
    """{id: множина трійок}; перевіряє, що розмічено всі 50 речень."""
    res, errs = {}, []
    with open(ROOT / path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            try:
                res[r["id"]] = parse_cell(r["triples"])
            except ValueError as e:
                errs.append(f"{r['id']}: {e}")
    if errs:
        raise SystemExit("Розмітка неповна або з помилками:\n  " + "\n  ".join(errs))
    return res


def save(method, rows, meta):
    """rows: [{"id", "triples": [[s, p, o], ...], "seconds", ...}] → results/<method>.jsonl + _meta.json."""
    with open(ROOT / f"results/{method}.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (ROOT / f"results/{method}_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))


def load(method):
    return {r["id"]: {tuple(t) for t in r["triples"]} for r in map(json.loads, open(ROOT / f"results/{method}.jsonl", encoding="utf-8"))}
