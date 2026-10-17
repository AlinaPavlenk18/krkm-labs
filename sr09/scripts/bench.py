"""
СР9 · Крок 3. Мінімальний бенчмарк: 5 запитів у кожному доступному сховищі.

Для кожного запиту: 3 прогрівальні запуски + 10 вимірюваних. Час — wall-clock на клієнті
(відправлення запиту + отримання ВСІХ рядків), мс: медіана, мінімум, p90.
Результат кожного сховища порівнюється з очікуваним (docs/expected.json) за ключовими колонками.

  python scripts/bench.py neo4j memgraph graphdb      # будь-яка підмножина
Вихід: docs/bench_results.json, docs/bench_results.md
"""
import json
import statistics
import sys
import time

from common import ROOT, bolt_driver, graphdb_endpoint, norm

WARMUP, RUNS = 3, 10
Q = json.loads((ROOT / "queries" / "bench_queries.json").read_text(encoding="utf-8"))
EXPECTED = json.loads((ROOT / "docs" / "expected.json").read_text(encoding="utf-8"))


def bolt_runner(engine):
    drv = bolt_driver(engine)
    session = drv.session()

    def run(q):
        return [{k: norm(v) for k, v in rec.items()} for rec in session.run(q["cypher"])]

    def version():
        try:
            if engine == "neo4j":
                r = session.run("CALL dbms.components() YIELD name, versions, edition "
                                "RETURN name + ' ' + versions[0] + ' ' + edition AS v").single()
                return r["v"]
            return "Memgraph " + str(session.run("SHOW VERSION").single()[0])
        except Exception as e:
            return f"? ({e.__class__.__name__})"
    return run, version, drv.close


def graphdb_runner():
    import requests
    url, repo = graphdb_endpoint()
    http = requests.Session()

    def run(q):
        r = http.post(f"{url}/repositories/{repo}", data={"query": q["sparql"]},
                      headers={"Accept": "application/sparql-results+json"})
        r.raise_for_status()
        js = r.json()
        return [{k: norm(b.get(k)) for k in js["head"]["vars"]} for b in js["results"]["bindings"]]

    def version():
        try:
            return "GraphDB " + http.get(f"{url}/rest/info/version").json().get("productVersion", "?")
        except Exception as e:
            return f"GraphDB ? ({e.__class__.__name__})"
    return run, version, http.close


def keyset(rows, keys):
    return sorted((tuple(r.get(k) for k in keys) for r in rows), key=repr)


def bench(engine):
    run, version, close = graphdb_runner() if engine == "graphdb" else bolt_runner(engine)
    out = {"engine": engine, "version": version(), "queries": []}
    for q in Q:
        rec = {"id": q["id"]}
        try:
            for _ in range(WARMUP):
                rows = run(q)
            times = []
            for _ in range(RUNS):
                t0 = time.perf_counter(); rows = run(q); times.append((time.perf_counter() - t0) * 1000)
            times.sort()
            exp = EXPECTED[q["id"]]["result"]
            rec.update(rows=len(rows), median_ms=round(statistics.median(times), 2), min_ms=round(times[0], 2),
                       p90_ms=round(times[int(0.9 * (RUNS - 1))], 2),
                       matches_expected=keyset(rows, q["key"]) == keyset(exp, q["key"]))
            if not rec["matches_expected"]:
                rec["sample"] = rows[:3]
        except Exception as e:
            rec.update(error=str(e).splitlines()[0][:300])
        out["queries"].append(rec)
        print(engine, rec)
    close()
    return out


def main():
    engines = sys.argv[1:] or ["neo4j", "memgraph", "graphdb"]
    results = [bench(e) for e in engines]
    (ROOT / "docs" / "bench_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    md = ["| Запит | " + " | ".join(f"{r['engine']} (мс, медіана / p90)" for r in results) + " | Результати збігаються |",
          "|---|" + "---|" * len(results) + "---|"]
    for i, q in enumerate(Q):
        cells, ok = [], True
        for r in results:
            x = r["queries"][i]
            if "error" in x:
                cells.append("помилка"); ok = False
            else:
                cells.append(f"{x['median_ms']} / {x['p90_ms']} ({x['rows']} рядк.)"); ok &= x["matches_expected"]
        md.append(f"| {q['id']} | " + " | ".join(cells) + f" | {'так' if ok else 'НІ'} |")
    md.append("")
    md += [f"- {r['engine']}: {r['version']}" for r in results]
    (ROOT / "docs" / "bench_results.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
