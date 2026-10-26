$env:GEN_PROVIDER   = "ollama"
$env:GEN_BASE_URL   = "http://localhost:11434"
$env:GEN_MODEL      = "qwen2.5:7b"

$env:JUDGE_BASE_URL = "https://api.groq.com/openai/v1"
$env:JUDGE_MODEL    = "openai/gpt-oss-120b"
$env:JUDGE_EXTRA    = '{"reasoning_effort": "low"}'
$env:JUDGE_PRICE_IN_PER_M  = "0.15"
$env:JUDGE_PRICE_OUT_PER_M = "0.60"

$env:GRAPH_BACKEND  = "neo4j"
$env:NEO4J_URI      = "neo4j://localhost:7687"
$env:NEO4J_USER     = "neo4j"

$env:PYTHONUTF8     = "1"
$env:JUDGE_API_KEY  = (Read-Host "Ключ Groq (gsk_...)").Trim()
$env:NEO4J_PASSWORD = Read-Host "Пароль Neo4j"