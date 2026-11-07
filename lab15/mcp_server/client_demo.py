import asyncio
import json
import os
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent import config as C

CALLS = [
    ("graph_query", {"template": "overloaded_substations"}),
    ("sql_metric", {"metric": "peak_load", "where": {"region": "Львівська область"}}),
    ("search_docs", {"query": "червоний рівень завантаження підстанції", "k": 2}),
    ("graph_query", {"template": "raw_sparql"}),                                
]


async def main():
    params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server.server"], cwd=str(C.LAB), env=dict(os.environ))   # інакше MCP передає лише мінімальне оточення
    C.LOGS.mkdir(exist_ok=True)
    log = open(C.LOGS / "mcp_demo.jsonl", "w", encoding="utf-8")
    async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        tools = (await s.list_tools()).tools
        print("Інструменти MCP-сервера energy-kb:")
        for t in tools:
            ro = t.annotations.read_only_hint if t.annotations else None
            print(f"  {t.name:<13} readOnly={ro}  params={list(t.input_schema.get('properties', {}))}")
            log.write(json.dumps({"tool": t.name, "readOnly": ro}, ensure_ascii=False) + "\n")
        for name, args in CALLS:
            t0 = time.perf_counter()
            res = await s.call_tool(name, args)
            text = " ".join(c.text for c in res.content if hasattr(c, "text"))
            ms = round((time.perf_counter() - t0) * 1000)
            print(f"\n→ {name} {json.dumps(args, ensure_ascii=False)}  ({ms} мс, is_error={res.is_error})\n  {text[:400]}")
            log.write(json.dumps({"call": name, "args": args, "is_error": res.is_error, "ms": ms, "result": text[:1500]},
                                 ensure_ascii=False) + "\n")
    log.close()


if __name__ == "__main__":
    asyncio.run(main())
