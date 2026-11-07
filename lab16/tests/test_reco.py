from datetime import datetime

from reco.data import load_items
from reco.eval import CUT, END, load, split
from reco.explain import check, find_path, template
from reco.models import Filters, GraphPPR, recommend

ITEMS = load_items()


def it(**kw):
    base = dict(next(iter(ITEMS.values())))
    base.update(kw)
    return base


def test_role_filters():
    assert not Filters("external").allowed(it(sensitivity="internal"), set())[0]
    assert Filters("analyst").allowed(it(sensitivity="internal", verified=True), set())[0]
    assert not Filters("analyst").allowed(it(sensitivity="restricted"), set())[0]
    r = it(sensitivity="restricted", entities=["Substation_7"])
    assert Filters("dispatcher", zone={"Substation_7"}).allowed(r, set())[0]
    assert not Filters("dispatcher", zone={"Substation_2"}).allowed(r, set())[0]
    assert Filters("head").allowed(r, set())[0]


def test_quality_filters():
    assert not Filters("analyst").allowed(it(verified=False), set())[0]
    assert not Filters("analyst", max_age_days=5).allowed(it(age_days=30, verified=True), set())[0]
    assert not Filters("analyst").allowed(it(date="2026-11-07", verified=True), set(), datetime(2026, 10, 27))[0]


def test_temporal_split_no_leak():
    users, ev = load(42)
    train, hist, rel = split(ev, CUT, END)
    assert max(t for _, _, t in train) < CUT
    for u in rel:
        assert not rel[u] & {i for i, _ in hist[u]}
    u = next(u for u in hist if hist[u])
    recs, _ = recommend(GraphPPR(), {"role": "analyst", "history": hist[u], "now": CUT}, k=20)
    assert all(ITEMS[i]["date"] <= "2026-10-27" for i in recs)


def test_explanation_checker():
    path = find_path("kb06#s06", ["kb06#s05"])
    assert path and path[-1] == "kb06#s06"
    assert check(template(path), path)[0]
    ok, why = check(template(path) + " Також див. підстанцію №11 і модель LSTM №3, 95 %.", path)
    assert not ok and why["extra_entities"]


def test_explanation_v2_slots():
    from reco.explain import check_slots, slot_chain
    path = find_path("kb06#s06", ["kb06#s05"])
    assert check_slots("Рекомендовано, бо " + slot_chain(path) + ".", path)[0]
    assert not check_slots("Рекомендовано, бо ви переглядали [B] після [A].", path)[0]          
    assert not check_slots("Рекомендовано, бо ви переглядали [A] і вже читали [B].", path)[0]   
    assert not check_slots("Рекомендовано, бо [A] і [B] стосуються підстанції №5.", path)[0]    #


def test_template_direction():
    p = find_path("kb06#s01", ["kb06#s02"])
    assert "перед ним" in template(p) and "далі" not in template(p)
