import csv
import json
import os
import re
import time
from datetime import date

from core.ingest import load_dir
from core.retrieve import BM25
from .appeal import build_case
from .parse import parse_denial, parse_facts

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.path.join(HERE, "golden")
TODAY = date(2026, 11, 1)
RANK = {"weak": 0, "medium": 1, "n/a": 1, "strong": 2}
MIN_ACCURACY = 0.9


def _norm(s):
    return re.sub(r"\s+", " ", s).strip()


def evaluate(golden=GOLDEN, today=TODAY):
    pdir = os.path.join(golden, "policies")
    idx = BM25(load_dir(pdir))
    source_text = {n: _norm(open(os.path.join(pdir, n), encoding="utf-8").read()) for n in os.listdir(pdir)}
    rows = list(csv.DictReader(open(os.path.join(golden, "expected.csv"), newline="", encoding="utf-8")))
    correct = unsafe = invented = 0
    fails = []
    for r in rows:
        text = open(os.path.join(golden, "denials", r["file"]), encoding="utf-8").read()
        facts = parse_facts(open(os.path.join(golden, "denials", r["facts"]), encoding="utf-8").read()) if r["facts"] else {}
        c = build_case(parse_denial(text), facts, idx, today)
        src = c["support"]["source"] if c["support"] else ""
        if c["support"] and _norm(c["support"]["text"]) not in source_text.get(src, ""):
            invented += 1
            fails.append(("INVENTED CITATION", r["file"]))
        ok = (c["code"] == r["code"] and c["category"] == r["category"] and c["recommendation"] == r["recommendation"]
              and c["strength"] == r["strength"] and src == r["policy_source"])
        if ok:
            correct += 1
        else:
            if RANK[c["strength"]] > RANK[r["strength"]]:
                unsafe += 1
            fails.append(("MISMATCH", f"{r['file']}: got {c['category']}/{c['recommendation']}/{c['strength']}/{src or '-'}"))
    total = len(rows)
    acc = round(correct / total, 3) if total else 0.0
    return {"total": total, "correct": correct, "accuracy": acc, "unsafe": unsafe, "invented": invented,
            "passed": unsafe == 0 and invented == 0 and acc >= MIN_ACCURACY, "fails": fails}


def log_result(res, golden=GOLDEN):
    rec = {"date": time.strftime("%Y-%m-%d"), "accuracy": res["accuracy"], "unsafe": res["unsafe"],
           "invented": res["invented"], "total": res["total"]}
    with open(os.path.join(golden, "history.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")
