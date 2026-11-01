"""
Статті й проєктні документи — ручна розмітка за інструкцією docs/extraction_schema.md (розділ MANUAL нижче:
сутності й відношення з дослівною цитатою-доказом). Реєстри gen01–gen07 згенеровано з графа ЛР9, тож відношення
для них беруться з CSV графа (істина генератора) і лишаються лише ті, обидві сутності яких названо в тому самому
розділі документа; сутності реєстрів — допоміжним сканером (scripts/gold_assist.py) з ручним переглядом.
Скрипт перевіряє кожну цитату й обчислює офсети від початку тексту документа.
"""
import csv, json, re, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.gold_assist import scan  
from src.schema import RELATION_TYPES  

from src.schema import DEV_DOCS as DEV 

S = lambda n: f"Substation_{n}"
MANUAL = {
    "kb01": {"ent": [("METHOD", "ARIMA", "ARIMA"), ("METHOD", "VAR", "VAR"), ("METHOD", "LSTM", "LSTM"),
                     ("METHOD", "GRU", "GRU"), ("WEATHER_FACTOR", "HDD", "HDD"), ("WEATHER_FACTOR", "CDD", "CDD"),
                     ("WEATHER_FACTOR", "TEMPERATURE", "температурою")], "rel": []},
    "kb02": {"ent": [("METHOD", "ARIMA", "ARIMA"), ("METHOD", "SARIMA", "SARIMA"), ("METHOD", "VAR", "VAR"),
                     ("METHOD", "LSTM", "LSTM"), ("METHOD", "GRU", "GRU"),
                     ("MODEL", "ForecastModel_ARIMA1", "ARIMA №1"), ("MODEL", "ForecastModel_VAR1", "VAR №1"),
                     ("MODEL", "ForecastModel_LSTM1", "№1 (точність 92 %)"), ("MODEL", "ForecastModel_LSTM2", "№2 (78 %"),
                     ("MODEL", "ForecastModel_LSTM3", "№3 (89 %)"), ("MODEL", "ForecastModel_GRU1", "GRU №1"),
                     ("SUBSTATION", S(3), "№3"), ("SUBSTATION", S(8), "№8"), ("SUBSTATION", S(2), "№2,"),
                     ("SUBSTATION", S(11), "№11"), ("SUBSTATION", S(12), "№12"),
                     ("WEATHER_FACTOR", "TEMPERATURE", "температуру")],
             "rel": [("FORECASTS_FOR", "ForecastModel_ARIMA1", S(3), "У мережі працює модель ARIMA №1 (точність 81 %), що прогнозує тижневе споживання для підстанцій №3 і №8."),
                     ("FORECASTS_FOR", "ForecastModel_ARIMA1", S(8), "У мережі працює модель ARIMA №1 (точність 81 %), що прогнозує тижневе споживання для підстанцій №3 і №8."),
                     ("FORECASTS_FOR", "ForecastModel_VAR1", S(2), "Модель VAR №1 (точність 84,5 %) прогнозує для підстанцій №2, №11 і №12."),
                     ("FORECASTS_FOR", "ForecastModel_VAR1", S(11), "Модель VAR №1 (точність 84,5 %) прогнозує для підстанцій №2, №11 і №12."),
                     ("FORECASTS_FOR", "ForecastModel_VAR1", S(12), "Модель VAR №1 (точність 84,5 %) прогнозує для підстанцій №2, №11 і №12."),
                     ("INSTANCE_OF", "ForecastModel_LSTM1", "LSTM", "У мережі працюють три моделі LSTM: №1 (точність 92 %), №2 (78 %, позначена як застаріла) і №3 (89 %)."),
                     ("INSTANCE_OF", "ForecastModel_LSTM2", "LSTM", "У мережі працюють три моделі LSTM: №1 (точність 92 %), №2 (78 %, позначена як застаріла) і №3 (89 %)."),
                     ("INSTANCE_OF", "ForecastModel_LSTM3", "LSTM", "У мережі працюють три моделі LSTM: №1 (точність 92 %), №2 (78 %, позначена як застаріла) і №3 (89 %).")]},
    "kb03": {"ent": [("METRIC", "MAE", "MAE"), ("METRIC", "RMSE", "RMSE"), ("METRIC", "MAPE", "MAPE"),
                     ("METRIC", "sMAPE", "sMAPE"), ("METRIC", "PINBALL", "pinball loss"),
                     ("MODEL", "ForecastModel_LSTM1", "LSTM №1"), ("MODEL", "ForecastModel_LSTM2", "LSTM №2")], "rel": []},
    "kb04": {"ent": [("WEATHER_FACTOR", "TEMPERATURE", "Температура"), ("WEATHER_FACTOR", "CLOUD_COVER", "Хмарність"),
                     ("WEATHER_FACTOR", "HUMIDITY", "Вологість"), ("WEATHER_FACTOR", "WIND", "вітер"),
                     ("WEATHER_FACTOR", "HDD", "HDD"), ("WEATHER_FACTOR", "CDD", "CDD"),
                     ("METHOD", "ARIMA", "ARIMA"), ("METHOD", "VAR", "VAR"), ("MODEL", "ForecastModel_LSTM2", "LSTM №2")], "rel": []},
    "kb05": {"ent": [("METER", "Meter_AMI77410", "AMI-77410"), ("CONSUMER", "Consumer_3310", "№3310"),
                     ("CONSUMER", "Consumer_5038", "№5038"), ("SUBSTATION", S(1), "№1"), ("MODEL", "ForecastModel_GRU1", "GRU №1")],
             "rel": [("HAS_METER", "Consumer_3310", "Meter_AMI77410", "Лічильник AMI-77410 комерційного споживача №3310 має статус «несправний»"),
                     ("CONNECTED_TO", "Consumer_5038", S(1), "промисловий споживач №5038, підключений до магістральної підстанції №1, має два лічильники")]},
    "kb06": {"ent": [("SUBSTATION", S(5), "№5"), ("SUBSTATION", S(4), "№4"), ("SUBSTATION", S(7), "№7"),
                     ("SUBSTATION", S(11), "№11"), ("SUBSTATION", S(1), "№1"), ("SUBSTATION", S(9), "№9"),
                     ("REGION", "Region_Zakarpattia", "Закарпатській області")],
             "rel": [("LOCATED_IN", S(9), "Region_Zakarpattia", "Підстанція №9 у Закарпатській області не має призначеного диспетчера.")]},
    "kb08": {"ent": [("MODEL", "ForecastModel_LSTM2", "LSTM №2"), ("MODEL", "ForecastModel_GRU1", "GRU №1")], "rel": []},
    "kb11": {"ent": [("MODEL", "ForecastModel_LSTM2", "LSTM №2"), ("SUBSTATION", S(11), "№11"), ("SUBSTATION", S(9), "№9"),
                     ("SUBSTATION", S(1), "№1"), ("REGION", "Region_Zakarpattia", "Закарпатській області")],
             "rel": [("FORECASTS_FOR", "ForecastModel_LSTM2", S(11), "прогноз на 4 жовтня 2026 року для підстанції №11 з похибкою 12,3 % згенеровано моделлю LSTM №2."),
                     ("LOCATED_IN", S(9), "Region_Zakarpattia", "Зараз це стосується підстанції №9 у Закарпатській області.")]},
    "kb12": {"ent": [("SUBSTATION", S(n), f"№{n}") for n in (1, 10, 2, 7, 4, 6, 3, 11, 5, 12, 9, 8)] +
                    [("REGION", "Region_Lviv", "Львівська область"), ("CONSUMER", "Consumer_4521", "№4521"),
                     ("CONSUMER", "Consumer_3310", "№3310"), ("CONSUMER", "Consumer_1002", "№1002")],
             "rel": [("LOCATED_IN", S(1), "Region_Lviv", "Магістральна підстанція №1 (Львівська область, 2500 кВт) живить підстанції №10, №2 і №7."),
                     ("FEEDS", S(1), S(10), "Магістральна підстанція №1 (Львівська область, 2500 кВт) живить підстанції №10, №2 і №7."),
                     ("FEEDS", S(1), S(2), "Магістральна підстанція №1 (Львівська область, 2500 кВт) живить підстанції №10, №2 і №7."),
                     ("FEEDS", S(1), S(7), "Магістральна підстанція №1 (Львівська область, 2500 кВт) живить підстанції №10, №2 і №7."),
                     ("FEEDS", S(10), S(4), "Далі №10 живить №4, а №4 — №6"), ("FEEDS", S(4), S(6), "Далі №10 живить №4, а №4 — №6"),
                     ("FEEDS", S(2), S(3), "№2 живить №3, а №3 — №11"), ("FEEDS", S(3), S(11), "№2 живить №3, а №3 — №11"),
                     ("FEEDS", S(7), S(5), "№7 живить №5, а №5 — №12"), ("FEEDS", S(5), S(12), "№7 живить №5, а №5 — №12"),
                     ("FEEDS", S(9), S(8), "Окремий ланцюг утворюють закарпатські підстанції: №9 живить №8."),
                     ("CONNECTED_TO", "Consumer_4521", S(7), "промисловий №4521 (450 кВт) на №7"),
                     ("CONNECTED_TO", "Consumer_3310", S(5), "комерційний №3310 (120 кВт) на №5"),
                     ("CONNECTED_TO", "Consumer_1002", S(12), "побутовий №1002 (10 кВт) на №12")]},
    "kb14": {"ent": [("METER", "Meter_AMI77410", "AMI-77410"), ("CONSUMER", "Consumer_3310", "№3310"), ("SUBSTATION", S(5), "№5")],
             "rel": [("HAS_METER", "Consumer_3310", "Meter_AMI77410", "AMI-77410 комерційного споживача №3310 на підстанції №5"),
                     ("CONNECTED_TO", "Consumer_3310", S(5), "AMI-77410 комерційного споживача №3310 на підстанції №5")]},
    "kb15": {"ent": [("DISPATCHER", f"Dispatcher_{n}", f"диспетчер №{n}") for n in (3, 6, 5, 2)] +
                    [("MODEL", "ForecastModel_LSTM2", "LSTM №2"), ("MODEL", "ForecastModel_VAR1", "VAR №1"),
                     ("MODEL", "ForecastModel_ARIMA1", "ARIMA №1"), ("MODEL", "ForecastModel_GRU1", "GRU №1"),
                     ("CONSUMER", "Consumer_5031", "№5031"), ("CONSUMER", "Consumer_5009", "№5009"),
                     ("CONSUMER", "Consumer_3310", "№3310"), ("CONSUMER", "Consumer_5011", "№5011"),
                     ("CONSUMER", "Consumer_5038", "№5038"), ("METER", "Meter_AMI77410", "AMI-77410"),
                     ("METER", "Meter_AMI27192", "AMI-27192"), ("METER", "Meter_AMI66829", "AMI-66829")] +
                    [("SUBSTATION", S(n), f"№{n}") for n in (5, 4, 10, 1, 9, 11, 12, 7, 2, 3, 6)] +
                    [("REGION", "Region_Volyn", "Волинська область"), ("REGION", "Region_Ternopil", "Тернопільська область"),
                     ("REGION", "Region_Zakarpattia", "Закарпатська область")],
             "rel": [("LOCATED_IN", S(5), "Region_Volyn", "Підстанція №5 (Волинська область) працює із завантаженням 468 кВт"),
                     ("MANAGES", "Dispatcher_3", S(5), "Відповідальний — диспетчер №3 (нічна зміна)."),
                     ("CONNECTED_TO", "Consumer_5031", S(5), "Найбільші споживачі підстанції: комерційні №5031"),
                     ("CONNECTED_TO", "Consumer_5009", S(5), "Найбільші споживачі підстанції: комерційні №5031 (196,5 кВт, м. Луцьк, вул. Соборна, 99) і №5009"),
                     ("HAS_METER", "Consumer_3310", "Meter_AMI77410", "Трифазний лічильник AMI-77410 комерційного споживача №3310"),
                     ("CONNECTED_TO", "Consumer_3310", S(5), "комерційного споживача №3310 (м. Львів, просп. Свободи, 28), підключеного до підстанції №5"),
                     ("LOCATED_IN", S(4), "Region_Ternopil", "Підстанція №4 (Тернопільська область) завантажена на 90 %"),
                     ("MANAGES", "Dispatcher_6", S(4), "Відповідальний — диспетчер №6."),
                     ("FEEDS", S(10), S(4), "Підстанція живиться від №10, а та — від магістральної №1."),
                     ("FEEDS", S(1), S(10), "Підстанція живиться від №10, а та — від магістральної №1."),
                     ("LOCATED_IN", S(9), "Region_Zakarpattia", "підстанція №9 (Закарпатська область, 120 кВт із 400 кВт)"),
                     ("CONNECTED_TO", "Consumer_5011", S(9), "До неї підключено промислового споживача №5011"),
                     ("FORECASTS_FOR", "ForecastModel_LSTM2", S(11), "Прогноз згенеровано моделлю LSTM №2."),
                     ("MANAGES", "Dispatcher_2", S(11), "Відповідальний — диспетчер №2. Рішення"),
                     ("FORECASTS_FOR", "ForecastModel_LSTM2", S(12), "Прогноз на 06.10.2026 для підстанції №12 моделі LSTM №2 має похибку 10,4 %."),
                     ("FEEDS", S(7), S(5), "спершу ланцюг №7 → №5 → №12"), ("FEEDS", S(5), S(12), "спершу ланцюг №7 → №5 → №12"),
                     ("FEEDS", S(2), S(3), "далі №2 → №3 → №11"), ("FEEDS", S(3), S(11), "далі №2 → №3 → №11"),
                     ("FEEDS", S(10), S(4), "останнім — №10 → №4 → №6"), ("FEEDS", S(4), S(6), "останнім — №10 → №4 → №6")]},
    "prj10": {"ent": [("CONSUMER", "Consumer_3310", "Consumer_3310"), ("CONSUMER", "Consumer_5019", "Consumer_5019"),
                      ("SUBSTATION", S(12), "№12"), ("SUBSTATION", S(8), "№8"), ("SUBSTATION", S(9), "№9"),
                      ("SUBSTATION", S(5), "№5"), ("SUBSTATION", S(6), "№6"), ("SUBSTATION", S(4), "№4"),
                      ("REGION", "Region_Lviv", "Львівської"), ("REGION", "Region_Volyn", "Волинської"),
                      ("WEATHER_FACTOR", "TEMPERATURE", "температура")],
              "rel": [("LOCATED_IN", S(12), "Region_Lviv", "№12 у Львівській області перевантажена"),
                      ("CONNECTED_TO", "Consumer_5019", S(12), "№12 у Львівській області перевантажена через промислового споживача Consumer_5019 (349,3 кВт) на підстанції номіналом 250 кВт")]},
    "prj11": {"ent": [("MODEL", "ForecastModel_LSTM1", "LSTM №1"), ("METRIC", "WAPE", "WAPE")], "rel": []},
    "kb07": {"ent": [], "rel": []}, "kb09": {"ent": [], "rel": []}, "kb10": {"ent": [], "rel": []}, "kb13": {"ent": [], "rel": []},
}


def rows(name):
    with open(ROOT / "data/source" / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def graph_facts():
    gen = {r["end"]: r["start"] for r in rows("rels_generated.csv")}
    model_sub = {(gen[r["start"]], r["end"]) for r in rows("rels_forecast_for.csv") if r["start"] in gen}
    models = {r["id"]: r["modelType"] for r in rows("nodes_forecastmodel.csv")}
    return {
        "FEEDS": {(r["start"], r["end"]) for r in rows("rels_feeds.csv")},
        "LOCATED_IN": {(r["start"], r["end"]) for r in rows("rels_located_in.csv")},
        "MANAGES": {(r["start"], r["end"]) for r in rows("rels_manages.csv")},
        "CONNECTED_TO": {(r["start"], r["end"]) for r in rows("rels_connected_to.csv")},
        "HAS_METER": {(r["start"], r["end"]) for r in rows("rels_has_meter.csv")},
        "FORECASTS_FOR": model_sub,
        "INSTANCE_OF": {(m, t) for m, t in models.items()},
    }


REG = {"Львівськ": "Region_Lviv", "Волинськ": "Region_Volyn", "Рівненськ": "Region_Rivne", "Тернопільськ": "Region_Ternopil",
       "Закарпатськ": "Region_Zakarpattia", "Івано-Франківськ": "Region_IvanoFrankivsk"}
MOD = r"(ARIMA|VAR|LSTM|GRU) №(\d+)"


def sentences(text, a, b):
    for m in re.finditer(r"[^\n]+?(?:\.(?=\s)|\.$|$)", text[a:b], re.M):
        if m.group(0).strip():
            yield m.group(0).strip(), a + m.start() + (len(m.group(0)) - len(m.group(0).lstrip()))


def register_relations(doc_id, text, facts):
    """Відношення реєстру за шаблоном розділу; кожну трійку звірено з графом ЛР9 (assert)."""
    out = []
    secs = [(m.group(1), m.start(), m.end()) for m in re.finditer(r"(?ms)^## (.*?)$.*?(?=^## |\Z)", text)]
    reg = lambda s: next(v for k, v in REG.items() if s.startswith(k))
    mod = lambda m: f"ForecastModel_{m.group(1)}{m.group(2)}"
    for title, a, b in secs:
        for sent, o in sentences(text, a, b):
            found = []
            if doc_id == "gen01" and title.startswith("Підстанція №"):
                n = int(title.split("№")[1]); me = f"Substation_{n}"
                if (m := re.search(r"розташована в області: (\S+)", sent)):
                    found.append(("LOCATED_IN", me, reg(m.group(1))))
                if "Сама живить підстанції" in sent:
                    found += [("FEEDS", me, f"Substation_{k}") for k in re.findall(r"№(\d+)", sent.split("Сама живить")[1])]
                if (m := re.search(r"живиться від підстанції №(\d+)", sent)):
                    found.append(("FEEDS", f"Substation_{m.group(1)}", me))
                if (m := re.search(r"Відповідальний — диспетчер №(\d+)", sent)):
                    found.append(("MANAGES", f"Dispatcher_{m.group(1)}", me))
                if sent.startswith("Безпосередньо підключено") or "Прогнози для підстанції" in sent:
                    found += [("FORECASTS_FOR", mod(m), me) for m in re.finditer(MOD, sent)]
            elif doc_id == "gen02" and title.startswith("Модель "):
                me = mod(re.search(MOD, title))
                if (m := re.search(r"типу (ARIMA|VAR|LSTM|GRU)\b", sent)):
                    found.append(("INSTANCE_OF", me, m.group(1)))
                found += [("FORECASTS_FOR", me, f"Substation_{k}") for k in re.findall(r"для підстанції №(\d+)", sent)]
            elif doc_id == "gen03" and title.startswith("Споживач №"):
                me = "Consumer_" + title.split("№")[1]
                if (m := re.search(r"Підключений до підстанції №(\d+) \((\S+)", sent)):
                    found += [("CONNECTED_TO", me, f"Substation_{m.group(1)}"), ("LOCATED_IN", f"Substation_{m.group(1)}", reg(m.group(2)))]
                if sent.startswith("Лічильники"):
                    found += [("HAS_METER", me, f"Meter_AMI{k}") for k in re.findall(r"AMI-(\d{5})", sent)]
            elif doc_id == "gen04":
                if (m := re.search(r"Належить споживачу №(\d+) \(\S+\) на підстанції №(\d+)", sent)):
                    meter = re.findall(r"AMI-(\d{5})", text[max(a, o - 200):o])[-1]
                    found += [("HAS_METER", f"Consumer_{m.group(1)}", f"Meter_AMI{meter}"),
                              ("CONNECTED_TO", f"Consumer_{m.group(1)}", f"Substation_{m.group(2)}")]
            elif doc_id == "gen05":
                if (m := re.search(r"для підстанції №(\d+) моделлю " + MOD, sent)):
                    found.append(("FORECASTS_FOR", f"ForecastModel_{m.group(2)}{m.group(3)}", f"Substation_{m.group(1)}"))
            elif doc_id == "gen07" and title.startswith("Диспетчер №"):
                me = "Dispatcher_" + title.split("№")[1]
                if "Зона відповідальності" in sent:
                    found += [("MANAGES", me, f"Substation_{k}") for k in re.findall(r"№(\d+)", sent.split("Зона відповідальності")[1])]
            for rel, h, t in found:
                assert (h, t) in facts[rel], ("немає в графі", doc_id, rel, h, t)
                out.append((rel, h, t, sent, o))
    return out


def main():
    docs = [json.loads(l) for l in open(ROOT / "data/docs.jsonl", encoding="utf-8")]
    facts = graph_facts()
    gold, n = [], 0
    for d in docs:
        did, text = d["doc_id"], d["text"]
        split = "dev" if did in DEV else "test"
        if did in MANUAL:
            ents = []
            for t, c, surf in MANUAL[did]["ent"]:
                mm = re.search(re.escape(surf) + (r"(?!\d)" if surf[-1].isdigit() else ""), text)
                o = mm.start() if mm else -1
                assert o >= 0, (did, surf)
                ents.append((t, c, surf, o))
            rels = []
            for rel, h, t, ev in MANUAL[did]["rel"]:
                o = text.find(ev)
                assert o >= 0, (did, ev)
                rels.append((rel, h, t, ev, o))
        else:
            ents = [(t, c, s, o) for (t, c), (s, o) in scan(text).items()]
            rels = register_relations(did, text, facts)
        known = {c for _, c, _, _ in ents}
        seen = {}
        for t, c, surf, o in ents:
            n += 1
            gold.append({"id": f"g{n:04d}", "doc_id": did, "split": split, "kind": "entity", "type": t,
                         "canonical": c, "text": surf, "start": o, "end": o + len(surf)})
        for rel, h, t, ev, o in rels:
            if (rel, h, t) in seen:   # та сама трійка ще раз у документі — додатковий доказ
                seen[(rel, h, t)].setdefault("alt_evidence", []).append(ev)
                continue
            assert h in known and t in known, (did, rel, h, t)
            ht, tt = RELATION_TYPES[rel]
            n += 1
            rec = {"id": f"g{n:04d}", "doc_id": did, "split": split, "kind": "relation", "type": rel,
                   "head": h, "tail": t, "evidence": ev, "start": o, "end": o + len(ev)}
            seen[(rel, h, t)] = rec
            gold.append(rec)
    with open(ROOT / "data/gold.jsonl", "w", encoding="utf-8") as f:
        for g in gold:
            f.write(json.dumps(g, ensure_ascii=False) + "\n")
    by = defaultdict(lambda: [0, 0])
    for g in gold:
        by[g["doc_id"]][g["kind"] == "relation"] += 1
    print(f"тверджень: {len(gold)} (сутностей {sum(v[0] for v in by.values())}, відношень {sum(v[1] for v in by.values())}); "
          f"документів із твердженнями: {sum(1 for v in by.values() if sum(v))} з {len(docs)}")
    for did in sorted(by):
        print(f"  {did:6s} {'dev ' if did in DEV else 'test'} сутн. {by[did][0]:3d}  відн. {by[did][1]:3d}")


if __name__ == "__main__":
    main()
