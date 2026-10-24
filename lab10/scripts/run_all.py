import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def step(name, args):
    print(f"\n=== {name}: {' '.join(args)}", flush=True)
    t = time.perf_counter()
    r = subprocess.run([PY] + args, cwd=ROOT)
    if r.returncode != 0:
        sys.exit(f"Крок {name} завершився з помилкою (код {r.returncode}). Надішліть вивід вище.")
    return round(time.perf_counter() - t, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-bge", action="store_true")
    ap.add_argument("--from", dest="start", default="r1")
    a = ap.parse_args()
    steps = [("r1", ["scripts/r1_build_corpus.py"]), ("gold", ["scripts/make_gold.py"]),
             ("r2", ["scripts/r2_chunking.py"]), ("r3", ["scripts/r3_embeddings.py"]),
             ("upsert", ["scripts/r3_upsert.py"]), ("r4", ["scripts/r4_hybrid.py"]),
             ("r5", ["scripts/r5_eval.py"] + (["--with-bge"] if a.with_bge else []))]
    if a.with_bge:
        steps.insert(6, ("r4bge", ["scripts/r4_hybrid.py", "--reranker", "bge-m3"]))
    names = [s[0] for s in steps]
    times = {}
    for name, args in steps[names.index(a.start):]:
        times[name] = step(name, args)
    import platform
    env = {"python": platform.python_version(), "platform": platform.platform(), "processor": platform.processor()}
    for mod in ["torch", "sentence_transformers", "faiss", "rank_bm25", "numpy", "transformers"]:
        try:
            m = __import__(mod)
            env[mod] = getattr(m, "__version__", "?")
        except Exception:
            env[mod] = None
    (ROOT / "results" / "environment.json").write_text(json.dumps({"env": env, "step_seconds": times}, ensure_ascii=False, indent=2),
                                                        encoding="utf-8")
    summary = []
    for f in ["chunking_cmp.md", "embeddings_cmp.md", "hybrid_report.md", "search_eval.md"]:
        p = ROOT / "docs" / f
        if p.exists():
            summary.append(p.read_text(encoding="utf-8"))
    (ROOT / "results" / "SUMMARY.md").write_text("\n\n".join(summary), encoding="utf-8")
    print("\nГотово. Час кроків (с):", times)
    print("Надішліть папку results/ (без results/cache) і docs/*.md.")


if __name__ == "__main__":
    main()
