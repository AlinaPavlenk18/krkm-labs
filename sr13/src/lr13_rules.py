"""Копія правил ЛР13 (src/extract_rules.py, версія rules_v2) БЕЗ ЗМІН у логіці — метод 1 СР13.
Правила налаштовано в ЛР13 лише на dev-документах ЛР13 (kb02, kb05, kb06, kb12, gen02, gen07); на 50 реченнях СР13
не змінювалися."""
import argparse, json, re, time
from pathlib import Path
import spacy
from spacy.util import filter_spans

from src.schema import canonical, DEV_DOCS  

ROOT = Path(__file__).resolve().parents[1]
VERSION = "rules_v2"
METH = ["ARIMA", "SARIMA", "VAR", "LSTM", "GRU"]
REG_STEMS = "(львівськ|волинськ|рівненськ|тернопільськ|закарпатськ|івано-франківськ)"

PATTERNS = [
    {"label": "MODEL", "pattern": [{"TEXT": {"IN": METH}}, {"TEXT": "№"}, {"IS_DIGIT": True}]},
    {"label": "DISPATCHER", "pattern": [{"LOWER": {"REGEX": "^диспетчер"}}, {"TEXT": "№"}, {"IS_DIGIT": True}]},
    {"label": "CONSUMER", "pattern": [{"TEXT": "№"}, {"IS_DIGIT": True, "LENGTH": 4}]},
    {"label": "CONSUMER", "pattern": [{"TEXT": {"REGEX": r"^Consumer_\d{4}$"}}]},
    {"label": "METER", "pattern": [{"TEXT": {"REGEX": r"^AMI-\d{5}$"}}]},
    {"label": "SUBSTATION", "pattern": [{"TEXT": "№"}, {"IS_DIGIT": True, "LENGTH": {"<=": 2}}]},
    {"label": "REGION", "pattern": [{"LOWER": {"REGEX": "^" + REG_STEMS}}, {"LOWER": {"REGEX": "^област"}}]},
    {"label": "METHOD", "pattern": [{"TEXT": {"IN": METH}}]},
    {"label": "METRIC", "pattern": [{"TEXT": {"IN": ["MAE", "RMSE", "MAPE", "sMAPE", "WAPE"]}}]},
    {"label": "METRIC", "pattern": [{"LOWER": "pinball"}, {"LOWER": "loss"}]},
    {"label": "WEATHER_FACTOR", "pattern": [{"LOWER": {"REGEX": "^(температур|хмарніст|вологіст|вітер)"}}]},
    {"label": "WEATHER_FACTOR", "pattern": [{"TEXT": {"IN": ["HDD", "CDD"]}}]},
]


def build_nlp():
    nlp = spacy.blank("uk")
    nlp.add_pipe("sentencizer")
    ruler = nlp.add_pipe("entity_ruler")
    ruler.add_patterns(PATTERNS)
    return nlp


def entities(nlp, text, base=0):
    doc = nlp(text)
    out = []
    for e in filter_spans(list(doc.ents)):
        etype = e.label_
        prev = text[max(0, e.start_char - 120):e.start_char]  
        lst = re.search(r"моделі (ARIMA|VAR|LSTM|GRU):[^.]*$", prev)
        if etype == "SUBSTATION" and lst:                
            etype, val = "MODEL", f"{lst.group(1)} {e.text}"
        else:
            val = e.text
        cid = canonical(etype, val)
        if cid:
            out.append((etype, cid, e.text, base + e.start_char))
    return out


def sections(text):
    heads = [m for m in re.finditer(r"(?m)^#{1,3} .*$", text)]
    for i, m in enumerate(heads):
        yield m.group(0), m.start(), heads[i + 1].start() if i + 1 < len(heads) else len(text)


def rel(out, t, h, tl, ev, start):
    if h and tl and h != tl:
        out.append((t, h, tl, ev, start))


def relations(nlp, text):
    rels = []
    for head, a, b in sections(text):
        hents = entities(nlp, head)
        subj = {t: c for t, c, _, _ in reversed(hents)}           # перша сутність кожного типу в заголовку
        body = text[a:b]
        doc = nlp(body)
        for sent in doc.sents:
            s, so = sent.text, a + sent.start_char
            ents = entities(nlp, s, so)
            E = lambda typ: [(c, st) for t, c, _, st in ents if t == typ]
            subs, cons, mets, mods, disp = E("SUBSTATION"), E("CONSUMER"), E("METER"), E("MODEL"), E("DISPATCHER")
            regs = E("REGION")
            # FEEDS: «X живить A, B і C»; еліпсис «а A — B»
            for clause in re.split(r";", s):
                coff = so + s.find(clause)
                cents = [(c, st) for t, c, _, st in entities(nlp, clause, coff) if t == "SUBSTATION"]
                if " живить " in f" {clause} " or clause.strip().startswith("Сама живить"):
                    parts = re.split(r",\s+а\s+", clause)
                    p0 = parts[0]
                    pos = p0.find("живить")
                    src = [c for c, st in cents if st - coff < pos] or ([subj["SUBSTATION"]] if "SUBSTATION" in subj else [])
                    for c, st in cents:
                        if pos <= st - coff < len(p0) and src:
                            rel(rels, "FEEDS", src[-1], c, clause.strip(), coff)
                    for p in parts[1:]:
                        m = re.match(r"№(\d+)\s+—\s+№(\d+)", p.strip())
                        if m:
                            rel(rels, "FEEDS", f"Substation_{m.group(1)}", f"Substation_{m.group(2)}", clause.strip(), coff)
            # LOCATED_IN: «підстанція №N (Область…» / «№N у … області» / «розташована в області: …»
            for c, st in subs:
                after = text[st:st + 45]
                m = re.match(r"№\d+\s*(?:\(|у |в )\s*" + REG_STEMS, after, re.I)
                if m:
                    rel(rels, "LOCATED_IN", c, canonical("REGION", m.group(1)), s.strip(), so)
            # MANAGES
            if "Зона відповідальності" in s and "DISPATCHER" in subj:
                for c, _ in subs:
                    rel(rels, "MANAGES", subj["DISPATCHER"], c, s.strip(), so)
            # CONNECTED_TO
            for c, st in cons:
                after = text[st:st + 90]
                m = re.search(r"^[^.;]*?(?:підключен\w* до (?:\w+ )?підстанції|\) на) №(\d{1,2})\b", after)
                if m:
                    rel(rels, "CONNECTED_TO", c, f"Substation_{m.group(1)}", s.strip(), so)
            # HAS_METER
            for m_ in re.finditer(r"AMI-(\d{5})[^.;]{0,40}?споживача №(\d{4})", s):
                rel(rels, "HAS_METER", f"Consumer_{m_.group(2)}", f"Meter_AMI{m_.group(1)}", s.strip(), so)
            # FORECASTS_FOR
            if re.search(r"прогноз\w*|згенерован", s, re.I):
                models = [c for c, _ in mods] or ([subj["MODEL"]] if "MODEL" in subj else [])
                k = re.search(r"для підстанц", s)
                targets = [c for c, st in subs if k and st - so > k.start()]
                for mo in models:
                    for t_ in targets:
                        rel(rels, "FORECASTS_FOR", mo, t_, s.strip(), so)
            # INSTANCE_OF
            m = re.search(r"типу (ARIMA|SARIMA|VAR|LSTM|GRU)\b", s)
            if m and "MODEL" in subj:
                rel(rels, "INSTANCE_OF", subj["MODEL"], m.group(1), s.strip(), so)
            m = re.search(r"моделі (ARIMA|VAR|LSTM|GRU):", s)
            if m:
                for c, _ in mods:
                    if m.group(1) in c:
                        rel(rels, "INSTANCE_OF", c, m.group(1), s.strip(), so)
    return rels
