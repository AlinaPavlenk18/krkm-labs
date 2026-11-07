"""Р5. propose_fact — запис знання лише через валідацію, оцінку ризику і (за потреби) схвалення людини.

пропозиція (суб'єкт, предикат, об'єкт, джерело, цитата)
  → валідація: словник предикатів і тип значення, суб'єкт/об'єкт існують, цитата дослівно є в документі-джерелі,
    SHACL (форми ЛР8 + ЛР14) на сховищі з новим фактом
  → ризик: high — порушення SHACL або джерело не підтверджує (відхилення);
           medium — зміна наявного значення, новий зв'язок, критичний предикат або restricted-джерело (схвалення людини);
           low — нове значення некритичної властивості з підтвердженим джерелом (автоматично)
  → запис лише схвалених фактів у kb/facts.csv з provenance (джерело, цитата, хто схвалив, коли); усі події — kb/audit.jsonl.
"""
import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from agent import config as C

PROPOSALS = C.KB / "proposals.json"
AUDIT = C.KB / "audit.jsonl"
FACTS = C.KB / "facts.csv"
EX = "http://www.semanticweb.org/energy-forecasting#"
ANNOTATION = {"status": "string", "note": "string"}                
CRITICAL = {"nominalCapacity", "currentLoad", "managedByDispatcher", "upstreamOf", "trainingDate", "accuracy",
            "connectedToSubstation", "contractLimit"}
FORBIDDEN = {"address", "rdf:type", "skos:prefLabel"}                 


def now():
    return datetime.now().isoformat(timespec="seconds")


def audit(event, **kw):
    C.KB.mkdir(exist_ok=True)
    with open(AUDIT, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": now(), "event": event, **kw}, ensure_ascii=False) + "\n")


def load():
    return json.loads(PROPOSALS.read_text(encoding="utf-8")) if PROPOSALS.exists() else []


def save(ps):
    C.KB.mkdir(exist_ok=True)
    PROPOSALS.write_text(json.dumps(ps, ensure_ascii=False, indent=1), encoding="utf-8")


def store_triples():
    with open(C.STORE / "store" / "triples.csv", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def vocabulary(triples):
    voc = {}
    for t in triples:
        if t["predicate"] not in FORBIDDEN:
            voc.setdefault(t["predicate"], "iri" if t["object_type"] == "iri" else (t["datatype"] or "string"))
    return {**voc, **ANNOTATION}


def source_ok(doc_id, quote):
    for line in open(C.STORE / "corpus" / "docs.jsonl", encoding="utf-8"):
        d = json.loads(line)
        if d["doc_id"] == doc_id:
            text = re.sub(r"\s+", " ", " ".join(s["text"] for s in d["sections"]))
            return re.sub(r"\s+", " ", quote).strip() in text, d["sensitivity"]
    return False, None


def shacl(triples, fact):
    """SHACL на сховищі з новим фактом (наявне значення функціональної властивості замінюється)."""
    from pyshacl import validate
    from rdflib import Graph, Literal, Namespace, RDF, XSD
    ns, skos = Namespace(EX), Namespace("http://www.w3.org/2004/02/skos/core#")
    dt = {"double": XSD.double, "string": XSD.string, "date": XSD.date, "dateTime": XSD.dateTime, "integer": XSD.integer}
    g = Graph()
    for r in triples:
        if r["subject"] == fact["subject"] and r["predicate"] == fact["predicate"] and fact["kind"] != "iri":
            continue
        p = r["predicate"]
        pred = RDF.type if p == "rdf:type" else skos.prefLabel if p == "skos:prefLabel" else ns[p]
        o = (ns[r["object"]] if r["object_type"] == "iri" else
             Literal(r["object"], lang=r["lang"]) if r["lang"] else Literal(r["object"], datatype=dt.get(r["datatype"])))
        g.add((ns[r["subject"]], pred, o))
    o = ns[fact["object"]] if fact["kind"] == "iri" else Literal(fact["object"], datatype=dt.get(fact["kind"]))
    g.add((ns[fact["subject"]], ns[fact["predicate"]], o))
    g.parse(C.STORE / "store" / "ontology" / "lab08_vocabulary.ttl")
    sh = Graph().parse(C.STORE / "store" / "ontology" / "lab08_shapes.ttl")
    sh.parse(C.LAB14 / "quality" / "shapes.ttl")
    _, rg, _ = validate(g, shacl_graph=sh, inference="rdfs")
    SH = Namespace("http://www.w3.org/ns/shacl#")
    return [str(rg.value(r, SH.resultMessage)) for r in rg.subjects(RDF.type, SH.ValidationResult)
            if str(rg.value(r, SH.focusNode)).endswith("#" + fact["subject"])]


def assess(fact):
    triples = store_triples()
    voc = vocabulary(triples)
    reasons, checks = [], {}
    nodes = {t["subject"] for t in triples if t["predicate"] == "rdf:type"}
    p = fact["predicate"]
    checks["predicate"] = p in voc
    if not checks["predicate"]:
        reasons.append(f"предикат {p} не входить до словника або заборонений")
    fact["kind"] = voc.get(p, "string")
    checks["subject"] = fact["subject"] in nodes
    if not checks["subject"]:
        reasons.append(f"суб'єкта {fact['subject']} немає в графі")
    if fact["kind"] == "iri":
        checks["object"] = fact["object"] in nodes
    elif fact["kind"] in ("double", "integer"):
        checks["object"] = bool(re.fullmatch(r"-?\d+(\.\d+)?", str(fact["object"])))
    else:
        checks["object"] = bool(str(fact["object"]).strip())
    if not checks["object"]:
        reasons.append(f"значення «{fact['object']}» не відповідає типу {fact['kind']}")
    checks["source"], sens = source_ok(fact["source"], fact["quote"])
    if not checks["source"]:
        reasons.append("цитати немає в документі-джерелі (або документа немає)")
    viol = shacl(triples, fact) if all(checks.values()) else []
    checks["shacl"] = not viol
    reasons += [f"SHACL: {v}" for v in viol]
    current = [t["object"] for t in triples if t["subject"] == fact["subject"] and t["predicate"] == p]
    if not all(checks.values()):
        risk = "high"
    else:
        medium = []
        if current and str(fact["object"]) not in current:
            medium.append(f"змінює наявне значення {current}")
        if fact["kind"] == "iri":
            medium.append("новий зв'язок у графі")
        if p in CRITICAL:
            medium.append(f"критичний предикат {p}")
        if sens == "restricted":
            medium.append("джерело restricted")
        risk = "medium" if medium else "low"
        reasons += medium
    return risk, checks, reasons, current


def write_fact(pr):
    new = not FACTS.exists()
    with open(FACTS, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["subject", "predicate", "object", "object_type", "datatype", "lang", "source", "confidence", "valid_from",
                        "proposal_id", "quote", "approved_by", "approved_at"])
        w.writerow([pr["subject"], pr["predicate"], pr["object"], "iri" if pr["kind"] == "iri" else "literal",
                    "" if pr["kind"] == "iri" else pr["kind"], "", f"agent:propose_fact; doc={pr['source']}", "0.9",
                    pr["decided_at"][:10], pr["id"], pr["quote"], pr["decided_by"], pr["decided_at"]])


def propose(subject, predicate, object, source, quote, proposed_by="agent"):
    ps = load()
    pr = {"id": f"P-{len(ps) + 1:04d}", "subject": subject, "predicate": predicate, "object": str(object), "source": source,
          "quote": quote, "proposed_by": proposed_by, "proposed_at": now()}
    audit("proposed", id=pr["id"], fact={k: pr[k] for k in ("subject", "predicate", "object", "source")}, by=proposed_by)
    risk, checks, reasons, current = assess(pr)
    pr.update({"risk": risk, "checks": checks, "reasons": reasons, "current_value": current})
    audit("assessed", id=pr["id"], risk=risk, checks=checks, reasons=reasons)
    if risk == "low":
        pr.update({"status": "approved", "decided_by": "auto (низький ризик)", "decided_at": now()})
        write_fact(pr)
    elif risk == "high":
        pr.update({"status": "rejected", "decided_by": "auto (високий ризик)", "decided_at": now()})
    else:
        pr.update({"status": "pending"})
    audit(pr["status"], id=pr["id"], by=pr.get("decided_by"))
    ps.append(pr)
    save(ps)
    return pr


def decide(pid, approve, by, reason=""):
    ps = load()
    pr = next((p for p in ps if p["id"] == pid), None)
    if pr is None or pr["status"] != "pending":
        sys.exit(f"{pid}: немає пропозиції в очікуванні схвалення")
    pr.update({"status": "approved" if approve else "rejected", "decided_by": by, "decided_at": now(), "decision_reason": reason})
    if approve:
        write_fact(pr)
    save(ps)
    audit(pr["status"], id=pid, by=by, reason=reason)
    return pr


def metrics():
    ps = load()
    dec = [p for p in ps if p["status"] != "pending"]
    human = [p for p in dec if not p["decided_by"].startswith("auto")]
    secs = [(datetime.fromisoformat(p["decided_at"]) - datetime.fromisoformat(p["proposed_at"])).total_seconds() for p in human]
    by_risk = {r: sum(p["risk"] == r for p in ps) for r in ("low", "medium", "high")}
    return {"proposals": len(ps), "by_risk": by_risk, "approved": sum(p["status"] == "approved" for p in ps),
            "rejected": sum(p["status"] == "rejected" for p in ps), "pending": sum(p["status"] == "pending" for p in ps),
            "approved_share": round(sum(p["status"] == "approved" for p in dec) / len(dec), 3) if dec else None,
            "auto_share": round(sum(p["decided_by"].startswith("auto") for p in dec) / len(dec), 3) if dec else None,
            "human_decisions": len(human), "avg_human_decision_s": round(sum(secs) / len(secs), 1) if secs else None}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("propose")
    for k in ("subject", "predicate", "object", "source", "quote"):
        p.add_argument(f"--{k}", required=True)
    p.add_argument("--by", default="agent")
    sub.add_parser("list")
    for k in ("approve", "reject"):
        q = sub.add_parser(k)
        q.add_argument("--id", required=True)
        q.add_argument("--by", required=True)
        q.add_argument("--reason", default="")
    sub.add_parser("metrics")
    a = ap.parse_args()
    if a.cmd == "propose":
        r = propose(a.subject, a.predicate, a.object, a.source, a.quote, a.by)
        print(json.dumps({k: r[k] for k in ("id", "risk", "status", "checks", "reasons", "current_value")}, ensure_ascii=False, indent=1))
    elif a.cmd == "list":
        for r in load():
            print(f"{r['id']} {r['status']:<9} {r['risk']:<7} {r['subject']} {r['predicate']} {r['object']} ({r['source']})")
    elif a.cmd == "metrics":
        print(json.dumps(metrics(), ensure_ascii=False, indent=1))
    else:
        r = decide(a.id, a.cmd == "approve", a.by, a.reason)
        print(f"{r['id']} → {r['status']} ({r['decided_by']}, {r['decided_at']})")
