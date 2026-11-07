"""Р4: pytest-обгортка над перевірками checks.py (кожне правило — окремий тест).

  pytest -q quality/tests                       # поточна версія (data_after/, якщо є)
  $env:QUALITY_VERSION = "baseline"; pytest -q quality/tests
Тест падає, якщо в правилі є порушення, не описані у quality/waivers.json.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from checks import CHECKS, Ctx, run_all 
from common import LAB  

VERSION = os.environ.get("QUALITY_VERSION", "after" if (LAB / "data_after").exists() else "baseline")
BASE = LAB / ("data_after" if VERSION == "after" else "data")
RESULTS = {r["id"]: r for r in run_all(Ctx(BASE / "store", BASE / "corpus" / "docs.jsonl", ref_date=os.environ.get("QUALITY_REF_DATE")))}


@pytest.mark.parametrize("cid", [c[0] for c in CHECKS])
def test_rule(cid):
    r = RESULTS[cid]
    assert r["blocking"] == 0, f"{cid} ({r['title']}): " + "; ".join(r["details"][:5])
