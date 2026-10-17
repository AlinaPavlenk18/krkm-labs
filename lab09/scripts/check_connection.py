#!/usr/bin/env python3
"""Перевірка підключення до Neo4j з Python (ЛР9, підготовка)."""
from neo4j_common import driver, database

with driver() as drv:
    drv.verify_connectivity()
    info = drv.get_server_info()
    with drv.session(database=database()) as s:
        comp = s.run("CALL dbms.components() YIELD name, versions, edition RETURN name, versions[0] AS v, edition").single()
        try:
            gds = s.run("RETURN gds.version() AS v").single()["v"]
        except Exception:
            gds = "не встановлено"
    print(f"Підключено: {info.address}, агент {info.agent}")
    print(f"{comp['name']} {comp['v']} ({comp['edition']}), GDS: {gds}")
