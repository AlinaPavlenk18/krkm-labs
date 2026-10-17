# СР9 · Критерії порівняння графових баз: Neo4j, Memgraph, GraphDB

Датасет — синтетичне масштабування графа ЛР9 (seed 42): 664 вузли, 1128 зв'язків / 4120 RDF-триплетів.

## Структура
```
data/       nodes_*.csv, rels_*.csv (Neo4j, Memgraph), bench.ttl (GraphDB)
queries/    B1–B5: *.cypher (Neo4j = Memgraph), *.rq (SPARQL), bench_queries.json
scripts/    generate_bench.py, expected.py, load.py, bench.py, common.py
docs/       expected.json (очікувані результати), load_*.json, bench_results.json/.md
```

## Запуск (Windows, PowerShell, у папці sr09)

### 0. Python
```powershell
pip install "neo4j>=5.20,<6" requests
```

### 1. Neo4j — ОКРЕМИЙ інстанс, щоб не стерти граф ЛР9
Neo4j Desktop → Create instance `sr09-bench` 
```powershell
$env:NEO4J_PASSWORD = "пароль_sr09"
python scripts\load.py neo4j       
```

### 2. Memgraph — Docker Desktop
```powershell
docker run -d -p 7688:7687 -p 7444:7444 --name memgraph memgraph/memgraph-mage
docker run -d -p 3000:3000 -e QUICK_CONNECT_MG_HOST=host.docker.internal -e QUICK_CONNECT_MG_PORT=7688 --name lab memgraph/lab
python scripts\load.py memgraph   
```
Memgraph Lab: http://localhost:3000.

### 3. GraphDB — Docker (без ліцензії працює в режимі Free)
```powershell
docker run -d -p 127.0.0.1:7200:7200 --name graphdb ontotext/graphdb:11.5.2
```
Workbench http://localhost:7200 → Setup → Repositories → Create new repository → GraphDB Repository:
Repository ID `energy-bench`, Ruleset **No inference** → Create.
```powershell
python scripts\load.py graphdb      
```

### 4. Бенчмарк
```powershell
python scripts\bench.py neo4j memgraph graphdb
```
Результат — `docs\bench_results.md` (таблиця часу) і `docs\bench_results.json`. 

