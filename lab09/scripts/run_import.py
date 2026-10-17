import datetime as dt
import time

from neo4j_common import ROOT, database, driver, statements

IMP = ROOT / "import"
COUNT_Q = "MATCH (n) WITH count(n) AS nodes MATCH ()-[r]->() RETURN nodes, count(r) AS rels"


def run_file(session, name):
    t0 = time.perf_counter()
    for q in statements(IMP / name):
        session.run(q).consume()
    return time.perf_counter() - t0


def counts(session):
    rec = session.run(COUNT_Q).single()
    return rec["nodes"], rec["rels"]


log = [f"# Журнал імпорту ({dt.datetime.now():%Y-%m-%d %H:%M})", ""]
with driver() as drv, drv.session(database=database()) as s:
    for f in ("01_constraints.cypher", "02_indexes.cypher"):
        log.append(f"- {f}: {run_file(s, f):.2f} c")
    for attempt in (1, 2):
        t_n = run_file(s, "03_load_nodes.cypher")
        t_r = run_file(s, "04_load_rels.cypher")
        n, r = counts(s)
        log.append(f"- Імпорт №{attempt}: вузли {t_n:.2f} c, зв'язки {t_r:.2f} c → **{n} вузлів, {r} зв'язків**")
        if attempt == 1:
            first = (n, r)
    log.append("")
    log.append("Ідемпотентність: " + ("ПІДТВЕРДЖЕНО (кількості збігаються)" if first == (n, r)
                                     else f"ПОРУШЕНО: {first} → {(n, r)}"))
    log.append("\n## Обмеження\n")
    for rec in s.run("SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties"):
        log.append(f"- {rec['name']}: {rec['type']} {rec['labelsOrTypes']} {rec['properties']}")
    log.append("\n## Індекси\n")
    for rec in s.run("SHOW INDEXES YIELD name, type, labelsOrTypes, properties, owningConstraint"):
        log.append(f"- {rec['name']}: {rec['type']} {rec['labelsOrTypes']} {rec['properties']}"
                   + (f" (опора обмеження {rec['owningConstraint']})" if rec['owningConstraint'] else ""))
    log.append("\n## Порушення обмеження\n")
    try:
        s.run("CREATE (:Substation {id: 'Substation_7', name: 'Дублікат підстанції №7'})").consume()
        log.append("УВАГА: дублікат створено — обмеження не працює!")
    except Exception as e:  # neo4j.exceptions.ConstraintError
        log.append(f"`{getattr(e, 'code', type(e).__name__)}`: {getattr(e, 'message', str(e))}")

out = ROOT / "docs" / "import_log.md"
out.write_text("\n".join(log) + "\n", encoding="utf-8")
print("\n".join(log))
