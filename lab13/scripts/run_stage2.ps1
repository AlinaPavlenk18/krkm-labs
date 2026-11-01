# LR13 stage 2: method B (prompt v2) on dev and test, comparison, graph, patterns. 
# Run:  powershell -ExecutionPolicy Bypass -File scripts\run_stage2.ps1
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
python -m src.extract_llm --split dev --prompt extract_v2
python scripts/compare.py --split dev
python -m src.extract_llm --split test --prompt extract_v2
python scripts/compare.py --split test
python scripts/build_graph.py
python scripts/patterns.py
Write-Host "Done. Next: . .\set_env.ps1 ; python scripts/load_neo4j.py"
