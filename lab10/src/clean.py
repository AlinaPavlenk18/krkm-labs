import json
import re
from collections import Counter

from common import RAW

FRONT_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
HEAD_RE = re.compile(r"^(#{1,4})\s+(.*)$")
SECRET_RE = re.compile(
    r"(?i)((?:password|passwd|пароль|token|api[_-]?key|secret)[\w$:\"']*\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|\S+)")
KEYLIKE_RE = re.compile(r"\b(sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b")


def parse_front_matter(text):
    m = FRONT_RE.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, text[m.end():]


def redact(line, stats):
    """R6 для рядків коду: прибирає лише секрети, решту коду не чіпає."""
    if SECRET_RE.search(line) or KEYLIKE_RE.search(line):
        stats["R6_secrets"] += 1
        line = SECRET_RE.sub(lambda m: m.group(1) + "[REDACTED]", line)
        line = KEYLIKE_RE.sub("[REDACTED]", line)
    return line


def clean_line(line, stats):
    raw = line
    if re.search(r"!\[[^\]]*\]\([^)]*\)", line):
        line = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", line); stats["R2_images"] += 1
    if re.search(r"<[^>]+>", line):
        line = re.sub(r"<!--.*?-->", "", line)
        line = re.sub(r"<[^>]+>", "", line); stats["R2_html"] += 1
    if re.search(r"\[([^\]]+)\]\(([^)]+)\)", line):
        line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", line); stats["R3_links"] += 1
    if SECRET_RE.search(line) or KEYLIKE_RE.search(line):
        line = SECRET_RE.sub(lambda m: m.group(1) + "[REDACTED]", line)
        line = KEYLIKE_RE.sub("[REDACTED]", line); stats["R6_secrets"] += 1
    if re.fullmatch(r"\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*", line):
        stats["R4_table_rules"] += 1
        return ""
    if line.strip().startswith("|") and line.strip().endswith("|"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        line = "; ".join(c for c in cells if c); stats["R4_table_rows"] += 1
    line = line.replace(" ", " ").replace("**", "").replace("`", "")
    line = re.sub(r"[ \t]+", " ", line).strip()
    if line != raw.strip():
        stats["R9_normalized_lines"] += 1
    return line


def md_to_sections(body, title, stats):
    sections, cur_path, buf = [], [], []
    in_code = False

    def flush():
        paras, seen, p = [], set(), []
        for ln in buf + [""]:
            if ln:
                p.append(ln)
            elif p:
                para = " ".join(p) if not in_code_para(p) else "\n".join(p)
                key = para.strip().lower()
                if key in seen:
                    stats["R10_dup_paragraphs"] += 1
                else:
                    seen.add(key); paras.append(para)
                p = []
        text = "\n\n".join(paras).strip()
        if text:
            sections.append({"section": " › ".join(cur_path) if cur_path else title, "text": text})
        elif cur_path:
            stats["R11_empty_sections"] += 1
        buf.clear()

    def in_code_para(p):
        return any(x.startswith("    ") for x in p)

    for line in body.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code; stats["R5_code_fences"] += 1
            buf.append("")
            continue
        if not in_code:
            m = HEAD_RE.match(line)
            if m:
                flush()
                level = len(m.group(1))
                name = clean_line(m.group(2), stats)
                if level == 1:
                    cur_path = []        
                    continue
                cur_path = cur_path[: level - 2] + [name]
                continue
        buf.append(clean_line(line, stats) if not in_code else redact(line.rstrip(), stats))
    flush()
    return sections


def docx_to_sections(path, title, stats):
    import docx  # python-docx
    d = docx.Document(path)
    body = d.element.body
    items = []  
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    for el in body.iterchildren():
        tag = el.tag.split("}")[1]
        if tag == "p":
            p = Paragraph(el, d)
            txt = p.text.strip()
            runs = [r for r in p.runs if r.text.strip()]
            bold = bool(runs) and all(r.bold for r in runs)
            items.append(("p", txt, bold and len(txt) < 120 and not txt.endswith(".")))
        elif tag == "tbl":
            t = Table(el, d)
            for row in t.rows:
                cells = []
                for c in row.cells:
                    ct = c.text.strip()
                    if ct and ct not in cells:
                        cells.append(ct)
                if cells:
                    items.append(("t", "; ".join(cells), False))

    start = next(i for i, it in enumerate(items) if it[1].startswith("Мета роботи"))
    stats["R7_title_page_lines"] += sum(1 for it in items[:start] if it[1])
    lines = []
    for kind, txt, is_head in items[start:]:
        if not txt:
            continue
        if re.fullmatch(r"[абвгд]\)", txt) or txt.startswith("[ВСТАВИТИ"):
            stats["R8_figure_stubs"] += 1
            continue
        if "Мета роботи:" in txt or "Висновок:" in txt or txt.startswith("Висновок до результату"):
            is_head = False
        if txt.startswith("Висновок:"):
            lines.append("## Висновок")
        if is_head:
            lines.append("## " + txt)
        else:
            lines.append(txt.lstrip("#").strip() if txt.startswith("#") else txt) 
            lines.append("")
    return md_to_sections("\n".join(lines), title, stats)


def load_documents():
    stats = Counter()
    docs = []
    for folder in ["kb", "generated"]:
        for p in sorted((RAW / folder).glob("*.md")):
            meta, body = parse_front_matter(p.read_text(encoding="utf-8"))
            if folder == "kb":
                meta.setdefault("origin", "kb_article")
            stats["R1_front_matter"] += 1
            sections = md_to_sections(body, meta["title"], stats)
            docs.append({**meta, "file": f"{folder}/{p.name}", "sections": sections})
    manifest = json.loads((RAW / "project" / "manifest.json").read_text(encoding="utf-8"))
    for m in manifest:
        p = RAW / "project" / m["file"]
        if p.suffix == ".docx":
            sections = docx_to_sections(p, m["title"], stats)
        else:
            sections = md_to_sections(p.read_text(encoding="utf-8"), m["title"], stats)
        docs.append({k: v for k, v in m.items() if k != "file"} | {"file": f"project/{m['file']}", "sections": sections})
    return docs, stats
