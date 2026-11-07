"""MCP-сервер «energy-kb» (stdio): ті самі інструменти, що й у LangGraph-агента, для будь-якого MCP-клієнта."""
import json

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from agent import config as C, policy, propose_fact as PF, tools as T

mcp = MCPServer("energy-kb", instructions="Сховище знань «Прогнозування енергоспоживання». Інструменти лише читають дані; "
                                          "запис — тільки пропозицією через propose_fact зі схваленням людини.")
RO = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
SPECS = T.SPECS


def _run(name, args):
    err = policy.validate_call(name, args, SPECS)
    if err:
        return json.dumps({"error": err}, ensure_ascii=False)
    items, neutral, dropped = policy.isolate_output(name, T.FUNCS[name](**args))
    return json.dumps({"items": items, "neutralized": neutral, "dropped_restricted": dropped}, ensure_ascii=False)


@mcp.tool(description=SPECS["search_docs"]["description"], annotations=RO)
def search_docs(query: str, k: int = 4) -> str:
    return _run("search_docs", {"query": query, "k": k})


@mcp.tool(description=SPECS["graph_query"]["description"], annotations=RO)
def graph_query(template: str, entity: str | None = None, depth: int = 3) -> str:
    args = {"template": template, "depth": depth} | ({"entity": entity} if entity else {})
    return _run("graph_query", args)


@mcp.tool(description=SPECS["sql_metric"]["description"], annotations=RO)
def sql_metric(metric: str, by: list[str] | None = None, where: dict | None = None) -> str:
    return _run("sql_metric", {"metric": metric, "by": by or [], "where": where or {}})


@mcp.tool(description="Запропонувати новий факт для графа. НЕ змінює граф напряму: факт проходить валідацію (словник, "
                      "джерело з дослівною цитатою, SHACL) і оцінку ризику; low — авто, medium — чекає схвалення людини, "
                      "high — відхиляється.",
          annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False))
def propose_fact(subject: str, predicate: str, object: str, source: str, quote: str) -> str:
    r = PF.propose(subject, predicate, object, source, quote, proposed_by="mcp-client")
    return json.dumps({k: r[k] for k in ("id", "risk", "status", "reasons")}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()        
