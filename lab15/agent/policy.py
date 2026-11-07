"""Політики й захисти агента (Р1, Р4). Кожна функція — окремий шар захисту; у версії «до захисту»
(AGENT_DEFENSES=0) вимкнено все, крім валідації аргументів і жорсткого ліміту кроків.

  input_guard        — запит: інструкції-перехоплення, запис/видалення, вимоги персональних даних → відмова
  validate_call      — інструмент є в дозволеному реєстрі, аргументи відповідають JSON Schema
  loop_guard         — повтор того самого виклику, ліміти викликів / токенів / часу
  isolate_output     — результат інструмента: restricted-фрагменти відкидаються, інструкції в даних нейтралізуються,
                       текст обрізається й обгортається як ДАНІ
  output_guard       — відповідь: службова мітка, системна підказка, адреси → не видаються
"""
import json
import re
import time

import jsonschema

from agent import config as C

INJECTION = re.compile(r"(ігнор\w*|забудь|не зважай)\W+(\w+\W+){0,3}(інструкц|правил|обмежен|джерел)|"
                       r"системн\w* (промпт|підказк|інструкц)|system prompt|ти тепер|you are now|developer mode|"
                       r"службов\w* мітк|режим адміністратора|jailbreak", re.I)
WRITE = re.compile(r"\b(видал\w*|вилуч\w*|знищ\w*|очист\w*|зміни\w*|зміню\w*|онов\w*|перезапиш\w*|запиш\w*|додай\w*|"
                   r"delete|drop|insert|update|merge|detach)\b", re.I)
PII = re.compile(r"адрес\w*|паспорт\w*|телефон\w*|особов\w* рахун\w*", re.I)
DATA_INSTR = re.compile(r"(увага,? систем\w*|попередні (правила|інструкції) скасован\w*|ігнор\w* \w+ інструкц\w*|"
                        r"system\s*:|assistant\s*:|обов'язково додай|відповідай, що)", re.I)
ADDRESS = re.compile(r"(вул\.|просп\.|пл\.|бульв\.)\s*[А-ЯҐЄІЇA-Z][^,;\n]{1,40}(,\s*\d+)?")

REFUSALS = {
    "injection": "Запит містить спробу змінити мої правила роботи. Я відповідаю лише на питання про мережу за джерелами бази знань.",
    "write": "Я працюю лише в режимі читання: змінювати чи видаляти знання не можу. Нове знання можна запропонувати через "
             "propose_fact — його перевірять і схвалить людина.",
    "pii": "Персональні дані споживачів (адреси тощо) мають рівень доступу restricted і недоступні ролі analyst.",
}


def input_guard(question):
    if not C.DEFENSES:
        return None
    if INJECTION.search(question):
        return "injection"
    if PII.search(question):
        return "pii"
    if WRITE.search(question):
        return "write"
    return None


def validate_call(name, args, specs):
    if name not in specs:
        return f"інструмент {name} не дозволено"
    try:
        jsonschema.validate(args, specs[name]["parameters"])
    except jsonschema.ValidationError as e:
        return f"аргументи {name}: {e.message[:160]}"
    return None


def loop_guard(state, name, args):
    key = name + json.dumps(args, ensure_ascii=False, sort_keys=True)
    if C.DEFENSES and key in state["seen_calls"]:
        return "повторний ідентичний виклик (захист від зациклення)"
    if state["tool_calls"] >= C.LIMITS["max_tool_calls"]:
        return f"вичерпано ліміт викликів ({C.LIMITS['max_tool_calls']})"
    if state["tokens"] >= C.LIMITS["max_tokens"]:
        return f"вичерпано ліміт токенів ({C.LIMITS['max_tokens']})"
    if time.perf_counter() - state["t0"] > C.LIMITS["max_seconds"]:
        return f"вичерпано ліміт часу ({C.LIMITS['max_seconds']} с)"
    state["seen_calls"].append(key)
    return None


def isolate_output(name, items):
    """→ (items для контексту, кількість нейтралізованих інструкцій, кількість відкинутих restricted-фрагментів)."""
    if not C.DEFENSES:
        return items, 0, 0
    clean, neutral, dropped = [], 0, 0
    for it in items:
        if it.get("sensitivity") == "restricted":
            dropped += 1
            continue
        txt, n = DATA_INSTR.subn("[вилучено: інструкція в даних]", it["text"])
        txt = ADDRESS.sub("[адресу приховано]", txt)
        neutral += n
        clean.append({**it, "text": txt[: C.LIMITS["max_tool_chars"] // max(1, len(items))]})
    return clean, neutral, dropped


def output_guard(answer, system_text):
    """→ (відповідь, список спрацювань)."""
    if not C.DEFENSES:
        return answer, []
    hits = []
    if C.CANARY in answer:
        hits.append("canary")
    sys_lines = [l.strip() for l in system_text.splitlines() if len(l.strip()) >= 30]
    if any(l in answer for l in sys_lines):
        hits.append("system_prompt")
    if ADDRESS.search(answer):
        hits.append("address")
    if hits:
        return "Не можу надати цю інформацію: відповідь містила службові або конфіденційні дані.", hits
    return answer, hits
