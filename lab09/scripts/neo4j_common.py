import os
import re
from pathlib import Path

from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parents[1]


def driver(user=None, password=None):
    uri = os.environ.get("NEO4J_URI", "neo4j://localhost:7687")
    user = user or os.environ.get("NEO4J_USER", "neo4j")
    password = password or os.environ["NEO4J_PASSWORD"]
    return GraphDatabase.driver(uri, auth=(user, password))


def database():
    return os.environ.get("NEO4J_DATABASE", "neo4j")


def statements(path):
    """Розбиває файл на запити за ';' в кінці рядка, відкидаючи рядкові коментарі //."""
    text = Path(path).read_text(encoding="utf-8")
    lines = []
    for line in text.splitlines():
        if line.strip().startswith("//"):
            continue
        lines.append(re.sub(r"\s//[^'\"]*$", "", line))
    chunks, cur = [], []
    for line in lines:
        cur.append(line)
        if line.rstrip().endswith(";"):
            stmt = "\n".join(cur).strip().rstrip(";").strip()
            if stmt:
                chunks.append(stmt)
            cur = []
    tail = "\n".join(cur).strip()
    if tail:
        chunks.append(tail)
    return chunks
