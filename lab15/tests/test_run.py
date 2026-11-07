import json
import os
from pathlib import Path
from types import SimpleNamespace

from agent import run


def test_cmd_attacks_closes_and_removes_tool_override_file(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENT_TOOL_OVERRIDES", raising=False)
    attacks = tmp_path / "tests" / "attacks.jsonl"
    attacks.parent.mkdir()
    attacks.write_text(json.dumps({
        "id": "A7",
        "type": "test",
        "question": "test",
        "setup": {"tool_overrides": {"search_docs": "test override"}},
        "success_if": {},
    }) + "\n", encoding="utf-8")
    monkeypatch.setattr(run.C, "LAB", tmp_path)
    monkeypatch.setattr(run, "summarize", lambda *args: None)
    temp_files = []

    def fake_ask(question, tag):
        override_file = Path(os.environ["AGENT_TOOL_OVERRIDES"])
        assert json.loads(override_file.read_text(encoding="utf-8")) == {"search_docs": "test override"}
        temp_files.append(override_file)
        return {
            "steps": [],
            "answer": "",
            "blocked": None,
            "totals": {"tool_calls": 0, "llm_calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
                       "latency_ms": 0},
        }

    monkeypatch.setattr(run, "ask", fake_ask)

    run.cmd_attacks(SimpleNamespace(tag="test"))

    assert len(temp_files) == 1
    assert not temp_files[0].exists()
    assert "AGENT_TOOL_OVERRIDES" not in os.environ
