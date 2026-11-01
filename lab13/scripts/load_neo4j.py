import json, os, sys
from pathlib import Path
from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parents[1]
PROOF = {
    "1. Скільки завантажено": """
        MATCH (e:XEntity) WITH count(e) AS entities
        MATCH (:XDocument)-[m:MENTIONS]->(:XEntity) WITH entities, count(m) AS mentions
        MATCH (:XEntity)-[r]->(:XEntity) WHERE type(r) <> 'SAME_AS'
        RETURN entities, mentions, count(r) AS relations""",
    "2. Відношення за типом і методом витягу": """
        MATCH (:XEntity)-[r]->(:XEntity) WHERE type(r) <> 'SAME_AS'
        RETURN type(r) AS rel, r.method AS method, count(*) AS n, round(avg(r.confidence), 2) AS avg_conf
        ORDER BY rel, method""",
    "3. Provenance твердження (доказ)": """
        MATCH (h:XEntity)-[r:FEEDS]->(t:XEntity)
        RETURN h.id AS head, t.id AS tail, r.source AS source, r.offset AS offset, r.method AS method,
               r.model AS model, r.prompt_version AS prompt, r.confidence AS confidence, r.evidence AS evidence
        ORDER BY source, offset LIMIT 6""",
    "4. Entity linking з графом ЛР9": """
        MATCH (x:XEntity)-[:SAME_AS]->(n) RETURN labels(n)[0] AS lr9_label, count(*) AS linked ORDER BY linked DESC""",
    "5. Витягнуте vs граф ЛР9 (FEEDS)": """
        MATCH (h:XEntity)-[r:FEEDS]->(t:XEntity), (h)-[:SAME_AS]->(h9), (t)-[:SAME_AS]->(t9)
        WITH DISTINCT h.id AS head, t.id AS tail, EXISTS { (h9)-[:FEEDS]->(t9) } AS in_lr9
        RETURN in_lr9, count(*) AS n""",
}


def main():
    drv = GraphDatabase.driver(os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
                               auth=(os.getenv("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]))
    with drv.session() as s:
        if "--drop" in sys.argv:
            s.run("MATCH (n) WHERE n:XEntity OR n:XDocument DETACH DELETE n").consume()
            print("видалено вузли XEntity / XDocument")
            return
        text = "\n".join(l for l in (ROOT / "data/graph_load.cypher").read_text(encoding="utf-8").splitlines()
                         if not l.startswith("//"))
        stmts = [x.strip().rstrip(";") for x in text.split(";\n") if x.strip()]
        for st in stmts:
            s.run(st).consume()
        print(f"виконано {len(stmts)} операторів Cypher\n")
        out = {}
        for name, q in PROOF.items():
            rows = [dict(r) for r in s.run(q)]
            out[name] = rows
            print(f"== {name}")
            for r in rows:
                print("  ", json.dumps(r, ensure_ascii=False))
        (ROOT / "results/graph_proof.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str),
                                                         encoding="utf-8")
    drv.close()


if __name__ == "__main__":
    main()
