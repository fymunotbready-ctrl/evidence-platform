import csv
import json
import os
import time

from .evidence import ask
from .library import Library

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.path.join(HERE, "golden")
MIN_ACCURACY = 0.9


def evaluate(golden=GOLDEN):
    lib = Library(os.path.join(golden, "papers"))
    rows = list(csv.DictReader(open(os.path.join(golden, "expected.csv"), newline="", encoding="utf-8")))
    correct = unsafe = 0
    fails = []
    for r in rows:
        res = ask(r["question"], lib)
        exp = r["expect"].strip()
        if exp == "REFUSED":
            if res["kind"] == "refused":
                correct += 1
            else:
                unsafe += 1
                fails.append(("UNSAFE (should refuse)", r["question"]))
        elif exp == "NOT_FOUND":
            if res["kind"] == "not_found":
                correct += 1
            elif res["kind"] == "answer":
                unsafe += 1
                fails.append(("UNSAFE (should say not found)", f"{r['question']} -> {res['evidence'][0]['sentence']}"))
            else:
                fails.append(("MISMATCH", f"{r['question']} -> {res['kind']}"))
        else:
            top = res["evidence"][0] if res["kind"] == "answer" else None
            if top and exp.lower() in top["sentence"].lower() and (not r["source"] or top["source"] == r["source"]):
                correct += 1
            elif res["kind"] == "answer":
                unsafe += 1
                fails.append(("WRONG", f"{r['question']} -> {top['sentence']}"))
            else:
                fails.append(("MISSED", r["question"]))
    total = len(rows)
    acc = round(correct / total, 3) if total else 0.0
    return {"total": total, "correct": correct, "accuracy": acc, "unsafe": unsafe, "fails": fails,
            "passed": unsafe == 0 and acc >= MIN_ACCURACY}


def log_result(res, golden=GOLDEN):
    with open(os.path.join(golden, "history.jsonl"), "a") as f:
        f.write(json.dumps({"date": time.strftime("%Y-%m-%d"), "accuracy": res["accuracy"], "unsafe": res["unsafe"],
                            "total": res["total"]}) + "\n")
