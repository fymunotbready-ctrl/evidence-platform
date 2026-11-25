import argparse
import os
import sys

from core.audit import AuditLog
from core.review import ReviewQueue
from core.tenant import TenantStore
from . import evaluate as ev
from .evidence import ask
from .fetch import fetch_papers
from .library import Library

HOME = os.environ.get("EVIDENCE_HOME", os.path.expanduser("~/.evidence-data"))


def cmd_ask(a):
    s = TenantStore(HOME)
    if not s.exists(a.tenant):
        s.create(a.tenant)
    d = s.dir(a.tenant)
    audit, queue = AuditLog(os.path.join(d, "audit.jsonl")), ReviewQueue(os.path.join(d, "queue.json"))
    lib = Library(a.papers)
    res = ask(a.question, lib)
    if res["kind"] == "refused":
        print("Can't help with that.\n" + res["message"])
    elif res["kind"] == "not_found":
        print(res["message"])
    else:
        print(f"Evidence ({res['support']}, confidence {res['confidence']}):")
        for n, e in enumerate(res["evidence"], 1):
            yr = f" ({e['year']})" if e["year"] else ""
            sec = f", {e['section']}" if e["section"] else ""
            print(f"\n[{n}] \"{e['sentence']}\"\n    {e['title']}{yr}{sec} [{e['chunk_id']}]")
        for label, url in res["links"]:
            print(f"Link - {label}: {url}")
        print("\n" + res["message"])
    if res["needs_review"] and res["kind"] != "refused":
        rid = queue.add({"question": a.question, "answer": res["message"] if res["kind"] == "not_found" else res["evidence"][0]["sentence"],
                         "citations": [], "confidence": res["confidence"], "needs_review": True})
        print(f"\nSent to human review queue: {rid}")
    audit.append("user", "ask_research", {"q": a.question, "kind": res["kind"], "confidence": res["confidence"],
                                          "sources": [e["chunk_id"] for e in res["evidence"]]})
    return 0


def cmd_papers(a):
    lib = Library(a.papers)
    for m in lib.papers.values():
        print(f"{m['file']} | {m.get('year', '?')} | {m['title'][:70]} | license: {m.get('license', 'unknown')}")
    return 0


def cmd_fetch(a):
    os.makedirs(a.out, exist_ok=True)
    saved = fetch_papers(a.query, a.out, a.max)
    if not saved:
        print("No open-access full-text papers found for that query. Try different words.")
        return 1
    for pmcid, title in saved:
        print(f"Saved {pmcid}: {title[:70]}")
    print(f"\n{len(saved)} paper(s) saved to {a.out}. Check each paper's license before sharing it.")
    return 0


def cmd_eval(a):
    res = ev.evaluate()
    print(f"Accuracy {res['correct']}/{res['total']} = {res['accuracy']:.1%} | unsafe answers: {res['unsafe']}")
    for kind, msg in res["fails"]:
        print(f"  {kind}: {msg}")
    print("RESULT:", "PASS" if res["passed"] else "FAIL")
    if a.log:
        ev.log_result(res)
        print("Logged to golden/history.jsonl")
    return 0 if res["passed"] else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="biotech")
    sub = p.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("ask"); q.add_argument("tenant"); q.add_argument("papers"); q.add_argument("question")
    l = sub.add_parser("papers"); l.add_argument("papers")
    f = sub.add_parser("fetch"); f.add_argument("query"); f.add_argument("out"); f.add_argument("--max", type=int, default=5)
    e = sub.add_parser("eval"); e.add_argument("--log", action="store_true")
    a = p.parse_args(argv)
    try:
        return {"ask": cmd_ask, "papers": cmd_papers, "fetch": cmd_fetch, "eval": cmd_eval}[a.cmd](a)
    except (ValueError, RuntimeError, FileNotFoundError, OSError) as ex:
        print(f"Error: {ex}")
        return 1
    except Exception as ex:
        print(f"Error: {type(ex).__name__}: {ex}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
