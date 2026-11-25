import argparse
import os
import re
import sys
from datetime import date

from core.ingest import SUPPORTED
from core.pipeline import Engine
from . import evaluate as ev
from .appeal import build_case
from .parse import InputError, parse_denial, parse_facts

HOME = os.environ.get("EVIDENCE_HOME", os.path.expanduser("~/.evidence-data"))


def cmd_appeal(a):
    denial = parse_denial(open(a.denial, encoding="utf-8").read())
    facts = parse_facts(open(a.facts, encoding="utf-8").read()) if a.facts else {}
    today = date.fromisoformat(a.today) if a.today else date.today()
    eng = Engine(HOME, a.tenant)
    files = [os.path.join(a.policies, n) for n in sorted(os.listdir(a.policies))
             if os.path.splitext(n)[1].lower() in SUPPORTED]
    if not files:
        print(f"No supported policy files in {a.policies}")
        return 1
    for f in files:
        eng.ingest(f)
    c = build_case(denial, facts, eng.index, today)
    print(f"Claim {c['claim']} | {c['code']} -> {c['category']}")
    print(f"Recommendation: {c['recommendation']} | Strength: {c['strength']}")
    if c["deadline"]:
        state = f"{c['days_left']} days left" if c["days_left"] >= 0 else f"PASSED {-c['days_left']} days ago"
        print(f"Appeal deadline: {c['deadline']} ({state})")
    if c["support"]:
        s = c["support"]
        print(f"Policy cited: {s['source']} [{s['chunk_id']}]")
    for r in c["reasons"]:
        print(f"Flag: {r}")
    for m in c["missing"]:
        print(f"Still needed: {m}")
    if c["letter"]:
        out = a.out or "appeal_" + re.sub(r"[^A-Za-z0-9_-]", "_", c["claim"]) + ".txt"
        open(out, "w", encoding="utf-8").write(c["letter"])
        print(f"Draft saved: {out}")
    if c["needs_review"]:
        rid = eng.queue.add({"question": f"Appeal {c['claim']}: {c['code']} {c['category']}",
                             "answer": f"{c['strength']} / {c['recommendation']}: " + "; ".join(c["reasons"] or ["needs human check"]),
                             "citations": [], "confidence": 0.3, "needs_review": True})
        print(f"Sent to human review queue: {rid}")
    eng.audit.append("user", "appeal_case", {"claim": c["claim"], "code": c["code"], "strength": c["strength"],
                                             "recommendation": c["recommendation"],
                                             "source": c["support"]["chunk_id"] if c["support"] else None})
    return 0


def cmd_eval(a):
    res = ev.evaluate()
    print(f"Cases {res['correct']}/{res['total']} = {res['accuracy']:.1%} | unsafe: {res['unsafe']} | invented citations: {res['invented']}")
    for kind, msg in res["fails"]:
        print(f"  {kind}: {msg}")
    print("RESULT:", "PASS" if res["passed"] else "FAIL")
    if a.log:
        ev.log_result(res)
        print("Logged to golden/history.jsonl")
    return 0 if res["passed"] else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="healthcare")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("appeal")
    s.add_argument("tenant"); s.add_argument("policies"); s.add_argument("denial")
    s.add_argument("--facts"); s.add_argument("--today"); s.add_argument("--out")
    g = sub.add_parser("eval"); g.add_argument("--log", action="store_true")
    a = p.parse_args(argv)
    try:
        return cmd_appeal(a) if a.cmd == "appeal" else cmd_eval(a)
    except (InputError, ValueError, RuntimeError, FileNotFoundError, OSError) as ex:
        print(f"Error: {ex}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
