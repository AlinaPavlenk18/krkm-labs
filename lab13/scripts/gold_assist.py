import json, re, sys
from collections import OrderedDict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.schema import canonical, REGIONS, WEATHER 

PAT = [
    ("MODEL", r"\b(?:ARIMA|SARIMA|VAR|LSTM|GRU)\s*№\s*\d+"),
    ("DISPATCHER", r"[Дд]испетчер\w*\s*№\s*\d+"),
    ("CONSUMER", r"№\s*\d{4}\b"),
    ("METER", r"AMI-\d{5}"),
    ("SUBSTATION", r"№\s*\d{1,2}\b"),
    ("REGION", r"(?:" + "|".join(REGIONS) + r")\w*\s+област\w*"),
    ("METHOD", r"\b(?:SARIMA|ARIMA|VAR|LSTM|GRU)\b(?!\s*№)"),
    ("METRIC", r"\b(?:sMAPE|MAPE|WAPE|RMSE|MAE)\b|pinball loss"),
    ("WEATHER_FACTOR", r"(?i)\b(?:" + "|".join(WEATHER) + r")\w*"),
]


def scan(text):
    taken, found = [], OrderedDict()
    for etype, p in PAT:
        for m in re.finditer(p, text):
            if any(a <= m.start() < b for a, b in taken):
                continue
            if etype == "SUBSTATION":
                ctx = text[max(0, m.start() - 12):m.start()]
                if re.search(r"(ARIMA|VAR|LSTM|GRU|испетчер\w*)\s*$", ctx):
                    continue
            taken.append((m.start(), m.end()))
            cid = canonical(etype, m.group(0))
            if cid and (etype, cid) not in found:
                found[(etype, cid)] = (m.group(0), m.start())
    return found


if __name__ == "__main__":
    want = set(sys.argv[1:])
    for l in open(Path(__file__).resolve().parents[1] / "data/docs.jsonl", encoding="utf-8"):
        d = json.loads(l)
        if want and d["doc_id"] not in want:
            continue
        f = scan(d["text"])
        print(f"== {d['doc_id']} ({len(f)})")
        for (t, c), (s, o) in f.items():
            print(f"   {t:15s} {c:24s} @{o:<5d} «{s}»")
