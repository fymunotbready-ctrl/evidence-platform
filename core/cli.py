import csv
import os
import sys
import tempfile

from .pipeline import Engine

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def demo():
    root = tempfile.mkdtemp(prefix="evidence-demo-")
    eng = Engine(root, "demo-co")
    eng.ingest(os.path.join(HERE, "samples", "security_policy.md"))
    with open(os.path.join(HERE, "samples", "questionnaire.csv"), newline="") as f:
        questions = [r[0] for r in csv.reader(f) if r and r[0].strip()]
    for q in questions:
        r = eng.ask(q)
        cite = r["citations"][0]["chunk_id"] if r["citations"] else "-"
        flag = "REVIEW" if r["needs_review"] else "ok"
        print(f"Q: {q}\nA: {r['answer']}\n   [{flag}] confidence={r['confidence']} source={cite}\n")
    ok, bad = eng.audit.verify()
    print(f"Audit log intact: {ok}. Pending human review: {len(eng.queue.pending())}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        demo()
    else:
        print("Usage: python3 -m core.cli demo")
