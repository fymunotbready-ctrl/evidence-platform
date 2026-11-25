import csv
import json
import os
import time

from core.answer import NOT_FOUND, answer
from core.ingest import load_dir
from core.retrieve import BM25

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.path.join(HERE, "golden")
MIN_ACCURACY = 0.85


def evaluate(golden_dir=GOLDEN):
    idx = BM25(load_dir(os.path.join(golden_dir, "docs")))
    with open(os.path.join(golden_dir, "golden.csv"), newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    correct, unsafe, missed, fails = 0, 0, 0, []
    for r in rows:
        q, expect = r["question"], r["expect"].strip()
        res = answer(q, idx)
        got_nf = res["answer"] == NOT_FOUND
        if expect == "NOT_FOUND":
            if got_nf:
                correct += 1
            else:
                unsafe += 1
                fails.append(("UNSAFE", q, res["answer"]))
        else:
            if (not got_nf) and res["citations"] and expect.lower() in res["answer"].lower():
                correct += 1
            elif got_nf:
                missed += 1
                fails.append(("MISSED", q, ""))
            else:
                unsafe += 1
                fails.append(("WRONG", q, res["answer"]))
    total = len(rows)
    acc = round(correct / total, 3) if total else 0.0
    return {"total": total, "correct": correct, "accuracy": acc, "unsafe": unsafe,
            "missed": missed, "passed": unsafe == 0 and acc >= MIN_ACCURACY, "fails": fails}


def log_result(res, golden_dir=GOLDEN):
    rec = {"date": time.strftime("%Y-%m-%d"), "accuracy": res["accuracy"], "unsafe": res["unsafe"], "total": res["total"]}
    with open(os.path.join(golden_dir, "history.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")
