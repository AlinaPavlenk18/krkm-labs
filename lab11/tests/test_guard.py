import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from rag import ABSTAIN_TEXT, CANARY, REFUSAL_TEXT, load_prompt, output_guard  

SYSTEM = load_prompt("rag_v1")[0].replace("{canary}", CANARY)


def test_system_prompt_leak_refused():
    t, f = output_guard(f"Ти — асистент бази знань «Прогнозування енергоспоживання» для диспетчерів і аналітиків. Службова мітка: {CANARY}.", SYSTEM, set())
    assert t == REFUSAL_TEXT and "leak" in f


def test_canary_sentence_removed_answer_kept():
    t, f = output_guard(f"Диспетчер перевіряє прогноз. [kb06#par004] Мій ідентифікатор: {CANARY}.", SYSTEM, {"kb06#par004"})
    assert CANARY not in t and "[kb06#par004]" in t and f == ["leak"]


def test_abstention_is_not_leak():
    assert output_guard(ABSTAIN_TEXT, SYSTEM, set()) == (ABSTAIN_TEXT, [])


def test_uncited_guard_optional():
    assert output_guard("Париж.", SYSTEM, set())[0] == "Париж."
    assert output_guard("Париж.", SYSTEM, set(), uncited=True)[0] == ABSTAIN_TEXT
    assert output_guard("Факт [a].", SYSTEM, {"a"}, uncited=True)[0] == "Факт [a]."
