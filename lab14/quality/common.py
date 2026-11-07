"""Спільне для скриптів ЛР14: шляхи, завантаження сховища (граф, трійки, корпус), RDF для SHACL/SPARQL,
нормалізація тексту, маскування restricted-даних у звітах, ембедінги e5-small.

Захист даних: тексти restricted-документів (gen03, kb15) обробляються лише локально; у файли, що йдуть у git
(md, csv), замість цитат із них пишеться «[restricted: <doc_id>]», адреси маскуються.
"""
import csv
import hashlib
import json
import os
import re
import subprocess
import unicodedata
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
DATA = LAB / "data"
QUALITY = LAB / "quality"
OUT = QUALITY / "out"
SEED = 42

EX = "http://www.semanticweb.org/energy-forecasting#"
STUB = os.environ.get("LAB14_STUB") == "1"         


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def write_jsonl(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def write_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def read_csv(path, delimiter=","):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def load_graph(store=DATA / "store"):
    """Граф Neo4j ЛР9 з CSV: {label: [вузли]}, {TYPE: [зв'язки]}."""
    g = Path(store) / "graph"
    nodes = {p.stem[6:]: read_csv(p) for p in sorted(g.glob("nodes_*.csv"))}
    rels = {p.stem[5:].upper(): read_csv(p) for p in sorted(g.glob("rels_*.csv"))}
    return nodes, rels


def load_triples(store=DATA / "store"):
    return read_csv(Path(store) / "triples.csv")


def load_corpus(path=DATA / "corpus" / "docs.jsonl"):
    return read_jsonl(path)


def sections(docs):
    """(doc, section_index, section_title, text) для всіх секцій корпусу."""
    for d in docs:
        for i, s in enumerate(d["sections"]):
            yield d, i, s["section"], s["text"]


def to_rdf(triples, with_vocab=True, store=DATA / "store"):
    """Трійки ЛР9 → rdflib.Graph (для pySHACL і SPARQL)."""
    from rdflib import Graph, Literal, Namespace, RDF, XSD
    ns, skos = Namespace(EX), Namespace("http://www.w3.org/2004/02/skos/core#")
    dt = {"double": XSD.double, "string": XSD.string, "date": XSD.date, "dateTime": XSD.dateTime, "integer": XSD.integer}
    g = Graph()
    for r in triples:
        p = r["predicate"]
        pred = RDF.type if p == "rdf:type" else skos.prefLabel if p == "skos:prefLabel" else ns[p]
        if r["object_type"] == "iri":
            obj = ns[r["object"]]
        elif r["lang"]:
            obj = Literal(r["object"], lang=r["lang"])
        else:
            obj = Literal(r["object"], datatype=dt.get(r["datatype"]))
        g.add((ns[r["subject"]], pred, obj))
    if with_vocab:
        g.parse(Path(store) / "ontology" / "lab08_vocabulary.ttl")
    return g


_APOS = str.maketrans({"’": "'", "ʼ": "'", "`": "'", "‘": "'", "−": "-", "–": "-", "—": "-", " ": " "})


def normalize(text):
    t = unicodedata.normalize("NFC", text).translate(_APOS).lower()
    t = re.sub(r"[*_`#>|]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def shingles(text, n=5):
    w = re.findall(r"[0-9a-zа-щьюяґєії',.]+", normalize(text))
    return {" ".join(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}


ADDRESS_RE = re.compile(r"(м\.\s*\w+,\s*)?(вул\.|просп\.|пл\.)\s*[^,;]+(,\s*\d+[^,;]*)?(,\s*кв\.\s*\d+)?")


def safe_quote(text, doc, limit=220):
    if doc.get("sensitivity") == "restricted":
        return f"[restricted: {doc['doc_id']}]"
    t = ADDRESS_RE.sub("[адресу приховано]", re.sub(r"\s+", " ", text)).strip()
    return t if len(t) <= limit else t[:limit].rsplit(" ", 1)[0] + " …"


def git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=LAB, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def files_hash(paths):
    h = hashlib.sha256()
    for p in sorted(str(x) for x in paths):
        h.update(Path(p).read_bytes())
    return h.hexdigest()[:16]


class Encoder:
    """intfloat/multilingual-e5-small (як у ЛР10–11); LAB14_STUB=1 — символьні n-грами (лише тест коду)."""
    NAME = "intfloat/multilingual-e5-small"

    def __init__(self):
        self.model = None
        if not STUB:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.NAME, device="cpu")

    def encode(self, texts):
        import numpy as np
        if STUB:
            vecs = []
            for t in texts:
                v = np.zeros(512, dtype="float32")
                s = normalize(t)
                for i in range(len(s) - 2):
                    v[int(hashlib.md5(s[i:i + 3].encode()).hexdigest()[:6], 16) % 512] += 1
                vecs.append(v / (np.linalg.norm(v) + 1e-9))
            return np.stack(vecs)
        return self.model.encode(["query: " + t for t in texts], batch_size=32, normalize_embeddings=True,
                                 convert_to_numpy=True, show_progress_bar=False).astype("float32")
