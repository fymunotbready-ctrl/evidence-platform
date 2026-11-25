import argparse
import os
import sys

from core.ingest import SUPPORTED
from core.pipeline import Engine
from . import evaluate as ev
from .questionnaire import finalize, read_questions, write_answers

HOME = os.environ.get("EVIDENCE_HOME", os.path.expanduser("~/.evidence-data"))


def _engine(tenant):
    return Engine(HOME, tenant)


def cmd_run(a):
    eng = _engine(a.tenant)
    files = [os.path.join(a.policies, n) for n in sorted(os.listdir(a.policies))
             if os.path.splitext(n)[1].lower() in SUPPORTED]
    if not files:
        print(f"No supported policy files in {a.policies} ({', '.join(SUPPORTED)})")
        return 1
    for f in files:
        print(f"Ingested {os.path.basename(f)}: {eng.ingest(f)} passages")
    qs = read_questions(a.questions)
    if not qs:
        print("No questions found in the CSV.")
        return 1
    results = [eng.ask(q) for q in qs]
    write_answers(a.out, results)
    review = sum(1 for r in results if r["needs_review"])
    print(f"\n{len(results) - review}/{len(results)} answered with citations, {review} need review.")
    print(f"Saved: {a.out}")
    if review:
        print(f"Next: python3 -m modules.cybersecurity.cli review {a.tenant}")
    return 0


def cmd_review(a):
    items = _engine(a.tenant).queue.pending()
    if not items:
        print("Nothing pending.")
        return 0
    for i in items:
        print(f"[{i['id']}] {i['question']}\n   -> {i['answer']} (conf {i['confidence']})")
    print("\napprove ID | reject ID | edit ID \"your answer\"")
    return 0


def cmd_decide(a, status):
    try:
        _engine(a.tenant).queue.decide(a.id, status, a.reviewer, getattr(a, "text", None))
    except (KeyError, ValueError) as e:
        print(f"Error: {e}")
        return 1
    print(f"{a.id} -> {status}")
    return 0


def cmd_finalize(a):
    items = _engine(a.tenant).queue.all()
    rows = finalize(a.out_csv, a.final_csv, items)
    pend = sum(1 for r in rows if r[3] == "PENDING REVIEW")
    print(f"Saved {a.final_csv}. Still pending review: {pend}")
    return 0


def cmd_eval(a):
    res = ev.evaluate()
    print(f"Accuracy {res['correct']}/{res['total']} = {res['accuracy']:.1%} | unsafe answers: {res['unsafe']} | safe misses: {res['missed']}")
    for kind, q, ans in res["fails"]:
        print(f"  {kind}: {q} {('-> ' + ans) if ans else ''}")
    print("RESULT:", "PASS" if res["passed"] else "FAIL")
    if a.log:
        ev.log_result(res)
        print("Logged to golden/history.jsonl")
    return 0 if res["passed"] else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="cybersecurity")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("tenant"); r.add_argument("policies"); r.add_argument("questions"); r.add_argument("out")
    v = sub.add_parser("review"); v.add_argument("tenant")
    for name in ("approve", "reject"):
        s = sub.add_parser(name); s.add_argument("tenant"); s.add_argument("id"); s.add_argument("--reviewer", default="me")
    e = sub.add_parser("edit"); e.add_argument("tenant"); e.add_argument("id"); e.add_argument("text"); e.add_argument("--reviewer", default="me")
    f = sub.add_parser("finalize"); f.add_argument("tenant"); f.add_argument("out_csv"); f.add_argument("final_csv")
    g = sub.add_parser("eval"); g.add_argument("--log", action="store_true")
    a = p.parse_args(argv)
    try:
        if a.cmd == "run": return cmd_run(a)
        if a.cmd == "review": return cmd_review(a)
        if a.cmd == "approve": return cmd_decide(a, "approved")
        if a.cmd == "reject": return cmd_decide(a, "rejected")
        if a.cmd == "edit": return cmd_decide(a, "edited")
        if a.cmd == "finalize": return cmd_finalize(a)
        if a.cmd == "eval": return cmd_eval(a)
    except (ValueError, RuntimeError, FileNotFoundError) as ex:
        print(f"Error: {ex}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
