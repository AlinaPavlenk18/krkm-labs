import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
CLEAN = DATA / "clean"
EVAL = ROOT / "eval"
RESULTS = ROOT / "results"
CACHE = RESULTS / "cache"
DOCS = ROOT / "docs"
SEED = 42

SENSITIVITY_ORDER = {"public": 0, "internal": 1, "restricted": 2}


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def write_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


_APOS = str.maketrans({"’": "'", "ʼ": "'", "`": "'", "‘": "'", "−": "-", "–": "-", "—": "-", " ": " "})


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFC", text).translate(_APOS).lower()
    t = re.sub(r"[*_`#>|]", " ", t)         
    t = re.sub(r"\s+", " ", t)
    return t.strip()


WORD_RE = re.compile(r"[0-9a-zа-щьюяґєії']+", re.IGNORECASE)


_SUFFIXES = sorted("""
ами ями ові еві ого ому ими іми ій ої ою ею ах ях ам ям ом ем ів їв ий ій ої ою ий им их ім
ого ому ою ість ості істю ання ання ення ення ування ують ують ити ати іти ено ано ний на не ні
у ю а я о е і ї и ь""".split(), key=len, reverse=True)

STOPWORDS = set("""і й та а але або чи що як які який яка яке в у на з із зі до від по за для про при над під
це цей ця ці той та те ті не ні так же ж би б є бути був була було були його її їх ми ви він вона воно
вони я ти мені тобі себе свій своя своє свої наш ваш хто де коли чому скільки який яких яким якою
the a an of to in on for and or is are be by with what which how""".split())


def stem(word: str) -> str:
    if len(word) <= 4 or word.isdigit():
        return word
    for s in _SUFFIXES:
        if word.endswith(s) and len(word) - len(s) >= 4:
            return word[: -len(s)]
    return word


def tokenize(text: str, stemming=True):
    words = WORD_RE.findall(normalize(text))
    words = [w for w in words if w not in STOPWORDS]
    return [stem(w) for w in words] if stemming else words


def word_count(text: str) -> int:
    return len(text.split())
