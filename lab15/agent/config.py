import os
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
REPO = LAB.parent
LAB11, LAB12, LAB14 = REPO / "lab11", REPO / "lab12", REPO / "lab14"
STORE = LAB14 / "data_after"                     # поточна версія сховища після ЛР14 (граф + корпус із kb16)
LOGS, KB, PROMPTS = LAB / "logs", LAB / "kb", LAB / "prompts"

OLLAMA = os.environ.get("GEN_BASE_URL", "http://localhost:11434")
MODEL = os.environ.get("GEN_MODEL", "qwen2.5:7b")
TEMPERATURE, SEED, NUM_CTX = 0.0, 42, 8192
ROLE = "analyst"                               
DEFENSES = os.environ.get("AGENT_DEFENSES", "1") == "1"

# ліміти (Р1, C2)
LIMITS = {
    "max_tool_calls": 6 if DEFENSES else 15,     # викликів інструментів на один запит
    "max_plan_rounds": 4 if DEFENSES else 10,    # кроків plan ⇄ retrieve
    "max_tokens": 24000,                         # prompt + completion за весь запит
    "max_seconds": 900,                          # стінний час запиту (CPU)
    "max_tool_chars": 2500,                      # обсяг результату одного інструмента в контексті
    "max_answer_tokens": 350,
}
CANARY = "KH-CANARY-AGENT-5Z"                    # службова мітка в системній підказці — детектор її витоку
PROMPT_VERSION = os.environ.get("AGENT_PROMPT", "v1")
