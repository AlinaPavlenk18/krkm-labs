"""Контроль розмітки: порівнює розмітку людини (data/gold.csv) з незалежною чернеткою асистента"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.common import gold, sentences  


def main():
    H, A, S = gold("data/gold.csv"), gold("data/gold_assistant_draft.csv"), {s["id"]: s["text"] for s in sentences()}
    both = sum(len(H[i] & A[i]) for i in H)
    only_h = [(i, t) for i in H for t in sorted(H[i] - A[i])]
    only_a = [(i, t) for i in H for t in sorted(A[i] - H[i])]
    union = both + len(only_h) + len(only_a)
    same_sent = sum(H[i] == A[i] for i in H)
    md = ["# Узгодженість розмітки: людина vs чернетка асистента", "",
          f"Трійок у людини: {sum(map(len, H.values()))}; у чернетці: {sum(map(len, A.values()))}; спільних: {both}.",
          f"Збіг за трійками (Jaccard): {both / union:.3f}; речень з однаковою розміткою: {same_sent} з {len(H)}.", "",
          "| Речення | Є лише в | Трійка | Текст |", "|---|---|---|---|"]
    md += [f"| {i} | людина | {' '.join(t)} | {S[i]} |" for i, t in only_h]
    md += [f"| {i} | чернетка | {' '.join(t)} | {S[i]} |" for i, t in only_a]
    (ROOT / "docs/agreement_auto.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md[:4]))
    print(f"розбіжностей: {len(only_h) + len(only_a)} → docs/agreement_auto.md")


if __name__ == "__main__":
    main()
