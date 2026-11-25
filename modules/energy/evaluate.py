import csv
import json
import os
import time

from .sizing import calculate

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.path.join(HERE, "golden")


def evaluate(golden=GOLDEN):
    rows = list(csv.DictReader(open(os.path.join(golden, "worked_examples.csv"), newline="")))
    correct, fails = 0, []
    for r in rows:
        res = calculate({"annual_kwh": float(r["kwh_year"]), "psh": float(r["psh"]), "derate": float(r["derate"]),
                         "offset_pct": float(r["offset_pct"]), "panel_w": float(r["panel_w"])})
        ok = (res["panels"] == int(r["expect_panels"])
              and abs(res["kw_dc"] - float(r["expect_kw"])) < 0.005
              and abs(res["production_kwh"] - float(r["expect_prod_kwh"])) <= 0.005 * float(r["expect_prod_kwh"]))
        if ok:
            correct += 1
        else:
            fails.append(f"{r['name']}: got {res['panels']} panels, {res['kw_dc']:.2f} kW, {res['production_kwh']:.0f} kWh")
    total = len(rows)
    return {"total": total, "correct": correct, "fails": fails, "passed": total > 0 and correct == total}


def log_result(res, golden=GOLDEN):
    with open(os.path.join(golden, "history.jsonl"), "a") as f:
        f.write(json.dumps({"date": time.strftime("%Y-%m-%d"), "correct": res["correct"], "total": res["total"]}) + "\n")
