"""Генерує 7 документів-реєстрів бази знань з даних графа ЛР9 (data/source/lab09_graph/*.csv).

Документи синтетичні (як і дані ЛР9) і детерміновані: той самий вхід -> той самий текст.
Результат: data/raw/generated/gen01..gen07*.md з YAML-заголовком метаданих.

Запуск: python scripts/generate_docs.py
"""
import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "source" / "lab09_graph"
OUT = ROOT / "data" / "raw" / "generated"
REPO_URL = "https://github.com/AlinaPavlenk18/krkm-labs/blob/main/lab10/data/raw/generated/"


def nodes(name):
    return {r["id"]: r for r in csv.DictReader(open(SRC / f"nodes_{name}.csv", encoding="utf-8"))}


def rels(name):
    return list(csv.DictReader(open(SRC / f"rels_{name}.csv", encoding="utf-8")))


def num(x):
    v = float(x)
    s = f"{v:.1f}".rstrip("0").rstrip(".")
    return s.replace(".", ",").replace("-", "\u2212")


def short(i):  # Substation_7 -> №7, Consumer_4521 -> №4521
    return "№" + i.split("_", 1)[1]


def meter_name(i):  # Meter_AMI77410 -> AMI-77410
    return "AMI-" + i.replace("Meter_AMI", "")


def model_name(i):  # ForecastModel_LSTM2 -> LSTM №2
    t = i.replace("ForecastModel_", "")
    return f"{t.rstrip('0123456789')} №{t[len(t.rstrip('0123456789')):]}"


def ddmmyyyy(iso):
    y, m, d = iso[:10].split("-")
    return f"{d}.{m}.{y}"


def header(doc_id, title, typ, date, sens, fname):
    return (f"---\ndoc_id: {doc_id}\ntitle: {title}\ntype: {typ}\ndate: {date}\nsensitivity: {sens}\n"
            f"source_url: {REPO_URL}{fname}\nlicense: CC BY 4.0 (Павленко А. С.); синтетичні дані ЛР9 (seed = 42)\n"
            f"origin: generated (scripts/generate_docs.py з data/source/lab09_graph)\n---\n\n# {title}\n\n")


ACC = {"ранкова": "ранкову", "вечірня": "вечірню", "нічна": "нічну", "денна": "денну"}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    S, C, M = nodes("substation"), nodes("consumer"), nodes("meter")
    X, W, FM = nodes("measurement"), nodes("weathercondition"), nodes("forecastmodel")
    F, D, R = nodes("forecast"), nodes("dispatcher"), nodes("region")

    region_of = {r["start"]: R[r["end"]]["name"] for r in rels("located_in")}
    manager = {r["end"]: r["start"] for r in rels("manages")}
    feeds_down, feeds_up = defaultdict(list), {}
    for r in rels("feeds"):
        feeds_down[r["start"]].append(r["end"])
        feeds_up[r["end"]] = r["start"]
    cons_of = defaultdict(list)
    sub_of = {}
    for r in rels("connected_to"):
        cons_of[r["end"]].append(r["start"])
        sub_of[r["start"]] = r["end"]
    meters_of, owner = defaultdict(list), {}
    for r in rels("has_meter"):
        meters_of[r["start"]].append(r["end"])
        owner[r["end"]] = r["start"]
    meas_of, meter_of_meas = defaultdict(list), {}
    for r in rels("recorded"):
        meas_of[r["start"]].append(r["end"])
        meter_of_meas[r["end"]] = r["start"]
    weather_of_meas = {r["end"]: r["start"] for r in rels("influences")}
    trained = defaultdict(list)
    for r in rels("trained_on"):
        trained[r["start"]].append(r["end"])
    gen_by, gen_list = {}, defaultdict(list)
    for r in rels("generated"):
        gen_by[r["end"]] = r["start"]
        gen_list[r["start"]].append(r["end"])
    target = {r["start"]: r["end"] for r in rels("forecast_for")}
    users = defaultdict(list)
    used_by_disp = defaultdict(list)
    for r in rels("uses_forecast"):
        users[r["end"]].append(r["start"])
        used_by_disp[r["start"]].append(r["end"])
    affects = defaultdict(list)
    for r in rels("affects_model"):
        affects[r["start"]].append(r["end"])

    def load_pct(s):
        return 100.0 * float(S[s]["currentLoad"]) / float(S[s]["nominalCapacity"])

    def level(p):
        return "червоний (критичне завантаження)" if p >= 95 else ("жовтий (перевантаження)" if p >= 85 else "зелений")

    sub_order = sorted(S, key=lambda i: int(i.split("_")[1]))
    disp_name = lambda d: f"диспетчер {short(d)}"

    t = header("gen01", "Паспорти підстанцій мережі", "register", "2026-10-15", "internal", "gen01_substation_passports.md")
    t += ("Паспорт підстанції містить її номінальні характеристики, поточне завантаження, місце в ланцюгу живлення, "
          "відповідального диспетчера та підключених споживачів. Дані актуальні на жовтень 2026 року.\n\n")
    for s in sub_order:
        p = load_pct(s)
        cons = cons_of[s]
        lim = sum(float(C[c]["contractLimit"]) for c in cons)
        cat = defaultdict(int)
        for c in cons:
            cat[C[c]["category"]] += 1
        cat_txt = ", ".join(f"{k} — {v}" for k, v in sorted(cat.items())) or "немає"
        up = f"живиться від підстанції {short(feeds_up[s])}" if s in feeds_up else "є головною у своєму ланцюгу (не має живлення від інших підстанцій мережі)"
        down = ", ".join(short(x) for x in sorted(feeds_down[s], key=lambda i: int(i.split('_')[1])))
        down_txt = f"Сама живить підстанції {down}." if down else "Інших підстанцій не живить."
        mgr = f"Відповідальний — {disp_name(manager[s])} ({D[manager[s]]['qualification']}, {D[manager[s]]['shift']} зміна)." if s in manager \
            else "Відповідального диспетчера не призначено; події обробляє провідний диспетчер."
        fcs = sorted([f for f in target if target[f] == s])
        fc_txt = "; ".join(f"{ddmmyyyy(F[f]['id'].split('_')[1][:4] + '-' + F[f]['id'].split('_')[1][4:6] + '-' + F[f]['id'].split('_')[1][6:8])} — {model_name(gen_by[f])}, похибка {num(F[f]['errorPercentage'])} %" for f in fcs)
        t += f"## Підстанція {short(s)}\n\n"
        t += (f"Підстанція {short(s)} розташована в області: {region_of[s]}. Номінальна потужність {num(S[s]['nominalCapacity'])} кВт, "
              f"поточне навантаження {num(S[s]['currentLoad'])} кВт, коефіцієнт завантаження {num(round(p, 1))} %, рівень — {level(p)}. "
              f"Підстанція {up}. {down_txt} {mgr}\n\n")
        t += (f"Безпосередньо підключено споживачів: {len(cons)} (за категоріями: {cat_txt}), сумарний договірний ліміт "
              f"{num(round(lim, 1))} кВт. Прогнози для підстанції: {fc_txt if fc_txt else 'немає'}.\n\n")
    (OUT / "gen01_substation_passports.md").write_text(t, encoding="utf-8")

    t = header("gen02", "Картки моделей прогнозування", "model_card", "2026-10-15", "internal", "gen02_model_cards.md")
    t += ("Картка моделі описує її тип, дату навчання, точність, навчальні дані та прогнози, які вона згенерувала. "
          "Картки оновлюються після кожного перенавчання.\n\n")
    for m in sorted(FM):
        r = FM[m]
        meas = trained[m]
        temps = sorted({float(W[weather_of_meas[x]]["temperature"]) for x in meas if x in weather_of_meas})
        days = sorted({X[x]["timestamp"][:10] for x in meas})
        faulty = sorted({meter_name(meter_of_meas[x]) for x in meas if x in meter_of_meas and M[meter_of_meas[x]]["status"] == "несправний"})
        fcs = sorted(gen_list[m])
        errs = [float(F[f]["errorPercentage"]) for f in fcs]
        fam = "статистична модель" if r["subLabel"] == "StatisticalModel" else "нейромережева модель (машинне навчання)"
        status = "застаріла, у черзі на перенавчання" if m.endswith("LSTM2") else (
            "у черзі на перенавчання через дані несправних лічильників" if m.endswith("GRU1") else "в експлуатації")
        t += f"## Модель {model_name(m)}\n\n"
        t += (f"Модель {model_name(m)} — {fam} типу {r['modelType']}. Дата навчання {ddmmyyyy(r['trainingDate'])}, точність {num(r['accuracy'])} %. "
              f"Статус: {status}.\n\n")
        t += (f"Навчальна вибірка: {len(meas)} вимірювань за {len(days)} {'дні' if len(days) in (2, 3, 4) else 'днів'} (з {ddmmyyyy(days[0])} по {ddmmyyyy(days[-1])}), "
              f"температура повітря в ці дні від {num(temps[0])} до {num(temps[-1])} °C. ")
        t += (f"У вибірці є вимірювання несправних лічильників: {', '.join(faulty)}.\n\n" if faulty
              else "Вимірювань несправних лічильників у вибірці немає.\n\n")
        flist = "; ".join(f"{F[f]['name'].replace('Прогноз на ', '')} для підстанції {short(target[f])} ({F[f]['forecastPeriod']}, похибка {num(F[f]['errorPercentage'])} %)" for f in fcs)
        t += (f"Згенеровані прогнози ({len(fcs)}): {flist}. Середня похибка прогнозів моделі {num(round(sum(errs) / len(errs), 2))} %, "
              f"найбільша {num(max(errs))} %.\n\n")
    (OUT / "gen02_model_cards.md").write_text(t, encoding="utf-8")

    t = header("gen03", "Реєстр споживачів", "register", "2026-10-15", "restricted", "gen03_consumer_register.md")
    t += ("Реєстр містить адреси та договірні ліміти споживачів і має обмежений доступ (персональні дані). "
          "Адреси синтетичні.\n\n")
    for c in sorted(C, key=lambda i: int(i.split("_")[1])):
        r = C[c]
        ms = meters_of[c]
        mt = ", ".join(f"{meter_name(x)} ({M[x]['meterType']}, {M[x]['status']})" for x in ms)
        t += f"## Споживач {short(c)}\n\n"
        t += (f"Споживач {short(c)} — {r['category']}, адреса: {r['address']}. Договірний ліміт {num(r['contractLimit'])} кВт. "
              f"Підключений до підстанції {short(sub_of[c])} ({region_of[sub_of[c]]}). Лічильники ({len(ms)}): {mt}.\n\n")
    (OUT / "gen03_consumer_register.md").write_text(t, encoding="utf-8")

    t = header("gen04", "Реєстр лічильників AMI", "register", "2026-10-15", "internal", "gen04_meter_register.md")
    t += "Реєстр лічильників інтелектуального обліку: тип, інтервал зчитування, статус і останнє вимірювання.\n\n"
    for st in ["несправний", "на повірці", "активний"]:
        t += f"## Лічильники зі статусом «{st}»\n\n"
        for m in sorted(M):
            if M[m]["status"] != st:
                continue
            xs = sorted(meas_of[m], key=lambda x: X[x]["timestamp"])
            last = (f" Останнє вимірювання {X[xs[-1]]['timestamp'].replace('T', ' ')[:16]}: {num(X[xs[-1]]['consumptionValue'])} кВт·год, напруга {num(X[xs[-1]]['voltage'])} В."
                    if xs else " Вимірювань у базі немає.")
            t += (f"Лічильник {meter_name(m)} — {M[m]['meterType']}, інтервал зчитування {M[m]['readingInterval']} хв, статус «{st}». "
                  f"Належить споживачу {short(owner[m])} ({C[owner[m]]['category']}) на підстанції {short(sub_of[owner[m]])}.{last}\n\n")
    (OUT / "gen04_meter_register.md").write_text(t, encoding="utf-8")

    t = header("gen05", "Журнал прогнозів", "forecast_log", "2026-10-15", "internal", "gen05_forecast_log.md")
    t += "Журнал прогнозів: період, прогнозоване споживання, фактична похибка, модель і диспетчери, що користуються прогнозом.\n\n"
    for f in sorted(F):
        r = F[f]
        e = float(r["errorPercentage"])
        q = "добра" if e <= 5 else ("прийнятна" if e <= 10 else "неприйнятна")
        t += f"## {r['name']}\n\n"
        t += (f"Прогноз {f} складено на період «{r['forecastPeriod']}» для підстанції {short(target[f])} моделлю {model_name(gen_by[f])}. "
              f"Прогнозоване споживання {num(r['predictedConsumption'])} кВт·год, фактична похибка {num(e)} % — якість {q}. "
              f"Прогнозом користується {', '.join(disp_name(d) for d in sorted(users[f]))}.\n\n")
    (OUT / "gen05_forecast_log.md").write_text(t, encoding="utf-8")

    t = header("gen06", "Довідник погодних умов навчальних періодів", "register", "2026-10-15", "public", "gen06_weather_reference.md")
    t += "Довідник погодних умов за дні, вимірювання яких використано для навчання моделей.\n\n"
    for w in sorted(W):
        r = W[w]
        nm = [x for x, ww in weather_of_meas.items() if ww == w]
        t += f"## {r['name']}\n\n"
        t += (f"{r['name']}: середньодобова температура повітря {num(r['temperature'])} °C, хмарність — {r['cloudCover']}. "
              f"Погода вплинула на {len(nm)} вимірювань цього дня. "
              + (f"Вплинула на навчання моделей: {', '.join(model_name(m) for m in sorted(affects[w]))}." if affects[w] else "На навчання моделей не впливала.")
              + "\n\n")
    (OUT / "gen06_weather_reference.md").write_text(t, encoding="utf-8")

    t = header("gen07", "Зони відповідальності диспетчерів", "register", "2026-10-15", "internal", "gen07_dispatcher_zones.md")
    t += "Розподіл підстанцій між диспетчерами та прогнози, якими кожен диспетчер користується.\n\n"
    for d in sorted(D):
        r = D[d]
        subs = sorted([s for s in manager if manager[s] == d], key=lambda i: int(i.split("_")[1]))
        fs = sorted(used_by_disp[d])
        t += f"## Диспетчер {short(d)}\n\n"
        t += (f"Диспетчер {short(d)} має кваліфікацію «{r['qualification']}» і працює в {ACC[r['shift']]} зміну. "
              f"Зона відповідальності: {('підстанції ' + ', '.join(short(s) for s in subs)) if subs else 'немає'}. "
              f"Користується прогнозами ({len(fs)}): {', '.join(F[f]['name'].replace('Прогноз на ', '') for f in fs)}.\n\n")
    (OUT / "gen07_dispatcher_zones.md").write_text(t, encoding="utf-8")
    print("generated:", sorted(p.name for p in OUT.glob("gen*.md")))


if __name__ == "__main__":
    main()
