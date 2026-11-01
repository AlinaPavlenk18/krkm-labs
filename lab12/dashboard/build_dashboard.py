import base64, sys
from pathlib import Path
import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from semantic.semantic import metric_sql  

OUT = ROOT / "dashboard"
con = duckdb.connect(str(ROOT / "data/warehouse.duckdb"), read_only=True)
q = lambda s: con.sql(s).df()
COL = {"Побутовий споживач": "#2a78d6", "Комерційний споживач": "#eb6834", "Промисловий споживач": "#1baf7a"}
INK, MUTED, GRID, CRIT = "#0b0b0b", "#52514e", "#e6e5e1", "#d03b3b"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True})


def v1(ax):  # B1: енергія за підкласами таксономії
    df = q(metric_sql("total_energy", by=["class"])).sort_values("total_energy")
    mwh = df["total_energy"] / 1000
    ax.barh(df["class"], mwh, color=[COL[c] for c in df["class"]], height=0.55)
    for y, v in enumerate(mwh):
        ax.text(v + 15, y, f"{v:,.1f} МВт·год ({100 * v / mwh.sum():.1f} %)".replace(",", " "),
                va="center", color=INK, fontsize=9)
    ax.set_xlim(0, mwh.max() * 1.45)
    ax.set_xlabel("МВт·год")
    ax.set_title("B1. Спожита енергія за підкласами таксономії, січень 2026", loc="left", fontsize=11)
    ax.grid(axis="y", visible=False)


def v2(ax):  # B7: добове споживання + ковзне середнє 7 днів
    df = q((ROOT / "sql/olap/q07_window_cumulative.sql").read_text(encoding="utf-8"))
    ax.plot(df["дата"], df["мвт_год"], color="#86b6ef", lw=2, marker="o", ms=4, label="за добу")
    ax.plot(df["дата"], df["ковз_7д_мвт_год"], color="#2a78d6", lw=2, label="ковзне середнє, 7 днів")
    ax.set_ylabel("МВт·год / добу")
    ax.set_ylim(0, df["мвт_год"].max() * 1.15)
    ax.legend(loc="lower left", frameon=False)
    ax.set_title("B7. Добове споживання мережі", loc="left", fontsize=11)
    ax.tick_params(axis="x", rotation=30)


def v3(ax):  # B2: добовий профіль за класами (частка енергії класу за годину)
    df = q("""SELECT k.class_label AS cls, f.hour_key AS h,
                     100 * sum(f.energy_kwh) / sum(sum(f.energy_kwh)) OVER (PARTITION BY k.class_label) AS pct
              FROM fact_consumption f JOIN dim_consumer_class k USING (class_key) GROUP BY k.class_label, f.hour_key
              ORDER BY cls, h""")
    for cls, g in df.groupby("cls"):
        ax.plot(g["h"], g["pct"], color=COL[cls], lw=2, label=cls.replace(" споживач", ""))
        ax.text(23.3, g["pct"].iloc[-1], cls.split()[0], color=INK, fontsize=8, va="center")
    for a, b in [(8, 10), (18, 21)]:
        ax.axvspan(a - 0.5, b + 0.5, color="#f0efec", zorder=0)
    ax.set_xticks(range(0, 24, 3))
    ax.set_xlim(0, 26)
    ax.set_xlabel("година (сірим — пікові години)")
    ax.set_ylabel("% енергії класу")
    ax.legend(loc="upper left", frameon=False, fontsize=8)
    ax.set_title("B2. Добовий профіль споживання за класами", loc="left", fontsize=11)


def v4(ax):  # B4: пікове завантаження підстанцій
    df = q((ROOT / "sql/olap/q08_window_rank_substation.sql").read_text(encoding="utf-8")).sort_values("завантаження_pct")
    over = df["завантаження_pct"] >= 85
    ax.barh(df["підстанція"].str.replace("Підстанція ", "ПС "), df["завантаження_pct"],
            color=[CRIT if o else "#2a78d6" for o in over], height=0.6)
    ax.axvline(85, color=MUTED, ls="--", lw=1)
    ax.text(86, len(df) - 0.3, "поріг :OverloadedSubstation — 85 %", color=MUTED, fontsize=8)
    for y, (v, o) in enumerate(zip(df["завантаження_pct"], over)):
        ax.text(v + 1.5, y, f"{v:.1f} %" + ("  ⚠ перевантаження" if o else ""), va="center", fontsize=8, color=INK)
    ax.set_xlim(0, 160)
    ax.set_ylim(-0.6, len(df) + 0.3)
    ax.set_xlabel("пікове навантаження, % номіналу")
    ax.set_title("B4. Пікове завантаження підстанцій", loc="left", fontsize=11)
    ax.grid(axis="y", visible=False)


def v5(ax):  # B3: температура ↔ добова енергія на лічильник (будні)
    df = q("""SELECT k.class_label AS cls, d.date, avg(f.temperature_c) AS t,
                     sum(f.energy_kwh) / count(DISTINCT f.meter_id) AS e
              FROM fact_consumption f JOIN dim_consumer_class k USING (class_key) JOIN dim_date d USING (date_key)
              WHERE NOT d.is_weekend AND k.class_label = 'Побутовий споживач' GROUP BY ALL""")
    ax.scatter(df["t"], df["e"], s=36, color=COL["Побутовий споживач"], edgecolor="white", linewidth=1.5)
    r = q("""SELECT corr(e, t) AS r, regr_slope(e, t) AS b, regr_intercept(e, t) AS a FROM (
               SELECT d.date, avg(f.temperature_c) AS t, sum(f.energy_kwh) / count(DISTINCT f.meter_id) AS e
               FROM fact_consumption f JOIN dim_consumer_class k USING (class_key) JOIN dim_date d USING (date_key)
               WHERE NOT d.is_weekend AND k.class_label = 'Побутовий споживач' GROUP BY d.date)""").iloc[0]
    xs = [df["t"].min(), df["t"].max()]
    ax.plot(xs, [r["a"] + r["b"] * x for x in xs], color=MUTED, lw=1.5, ls="--")
    ax.text(0.98, 0.95, f"r = {r['r']:.3f}\n{r['b']:.2f} кВт·год на 1 °C", transform=ax.transAxes,
            ha="right", va="top", fontsize=9, color=INK)
    ax.set_xlabel("середня температура доби, °C")
    ax.set_ylabel("кВт·год / добу на лічильник")
    ax.set_title("B3. Температура і споживання побутових (будні)", loc="left", fontsize=11)


VIS = [
    (v1, "v1_taxonomy.png", "B1. Скільки енергії спожито за класами таксономії?",
     "Промислові споживачі (7 із 41) дають 77,0 % енергії, побутові (23 із 41) — лише 4,1 %. Для прогнозу "
     "загального навантаження найважливіша точність саме для підкласу ef:IndustrialConsumer."),
    (v2, "v2_daily.png", "B7. Яка динаміка добового споживання?",
     "Чіткий тижневий цикл: у вихідні споживання падає майже вдвічі (≈ 37–40 проти ≈ 72 МВт·год). Ковзне середнє "
     "стабільне (60,9–63,6 МВт·год після першого тижня); спад наприкінці місяця пов'язаний із вибуттям 5 несправних лічильників."),
    (v3, "v3_profile.png", "B2. Яка частка енергії припадає на пікові години в різних класах?",
     "Побутовий профіль має ранковий і вечірній максимуми, що збігаються з піковими годинами; комерційний — денне «плато» "
     "08–19; промисловий — найрівніший. Отже, вечірній пік мережі формують побутові, а денний — комерційні споживачі."),
    (v4, "v4_substations.png", "B4. Які підстанції перевантажені в пік?",
     "Чотири підстанції (№12, №8, №9, №5) перевищують поріг 85 % класу :OverloadedSubstation; №12 — 120,2 % номіналу "
     "через промислового споживача на підстанції 250 кВт. Це кандидати на перерозподіл навантаження."),
    (v5, "v5_temperature.png", "B3. Як температура впливає на споживання?",
     "У будні добове споживання побутового лічильника майже лінійно зростає з похолоданням (сильна від'ємна кореляція): "
     "температура — обов'язкова ознака моделі прогнозу для побутового підкласу."),
]


def main():
    for fn, name, *_ in VIS:
        fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=150)
        fn(ax)
        fig.tight_layout()
        fig.savefig(OUT / name, facecolor="#fcfcfb")
        plt.close(fig)
    fig, axes = plt.subplots(3, 2, figsize=(15, 13), dpi=110)
    for (fn, *_), ax in zip(VIS, axes.flat):
        fn(ax)
    axes.flat[-1].axis("off")
    fig.suptitle("Domain Knowledge Hub · Погодинне споживання електроенергії, січень 2026", x=0.01, ha="left", fontsize=14)
    fig.tight_layout()
    fig.savefig(OUT / "dashboard.png", facecolor="#fcfcfb")
    plt.close(fig)

    cards = []
    for _, name, title, text in VIS:
        b64 = base64.b64encode((OUT / name).read_bytes()).decode()
        cards.append(f'<section><h2>{title}</h2><img src="data:image/png;base64,{b64}" alt="{title}">'
                     f'<p><b>Інтерпретація.</b> {text}</p></section>')
    html = f"""<!DOCTYPE html><html lang="uk"><head><meta charset="utf-8">
<title>Панель: погодинне споживання електроенергії</title>
<style>body{{font-family:'Segoe UI',Arial,sans-serif;background:#fcfcfb;color:#0b0b0b;margin:24px;max-width:1500px}}
main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(620px,1fr));gap:20px}}
section{{border:1px solid #e6e5e1;border-radius:8px;padding:12px 16px;background:#fff}}
h1{{font-size:22px}} h2{{font-size:16px;margin:4px 0 8px}} img{{width:100%}} p{{color:#52514e;line-height:1.45}}</style>
</head><body><h1>Domain Knowledge Hub · Погодинне споживання електроенергії (січень 2026, синтетичні дані v1.0.0)</h1>
<p>Джерело: сховище DuckDB (зірка fact_consumption), метрики — семантичний шар semantic/metrics.yml.</p>
<main>{''.join(cards)}</main></body></html>"""
    (OUT / "index.html").write_text(html, encoding="utf-8")
    print("→ dashboard/index.html, dashboard/dashboard.png, 5 PNG")


if __name__ == "__main__":
    main()
