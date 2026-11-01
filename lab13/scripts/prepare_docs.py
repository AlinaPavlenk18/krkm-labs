import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = []
    for f in sorted((ROOT / "data/raw").glob("*.md")):
        raw = f.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n", raw, re.S)
        meta = dict(l.split(": ", 1) for l in m.group(1).splitlines() if ": " in l)
        text = raw[m.end():].strip() + "\n"
        out.append({"doc_id": meta["doc_id"], "title": meta["title"], "type": meta["type"],
                    "sensitivity": meta["sensitivity"], "date": meta["date"], "source_url": meta["source_url"],
                    "words": len(text.split()), "text": text})
    with open(ROOT / "data/docs.jsonl", "w", encoding="utf-8") as fh:
        for d in out:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")
    print(f"{len(out)} документів, {sum(d['words'] for d in out)} слів;",
          ", ".join(f"{d['doc_id']}({d['type']},{d['sensitivity']})" for d in out))


if __name__ == "__main__":
    main()
