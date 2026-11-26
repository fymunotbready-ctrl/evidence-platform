"""Realistic benchmark. Run from repo root: python3 -m bench.run_bench"""
import os, sys
from modules.cybersecurity.cli import _engine
from bench.cases import CASES

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    eng = _engine("bench")
    pol = os.path.join(HERE, "policies")
    for n in sorted(os.listdir(pol)):
        eng.ingest(os.path.join(pol, n))
    correct = unsafe = miss = 0
    problems = []
    for q, expect in CASES:
        r = eng.ask(q)
        ans = r["answer"]
        held = r["needs_review"] or not r["citations"]
        if expect == "REVIEW":
            if held:
                correct += 1
            else:
                unsafe += 1
                problems.append(("UNSAFE", q, ans))
        elif held:
            miss += 1
            problems.append(("MISS", q, ans))
        elif all(k in ans.lower() for k in expect):
            correct += 1
        else:
            unsafe += 1
            problems.append(("UNSAFE", q, ans))
    total = len(CASES)
    print(f"BENCH {correct}/{total} correct = {100 * correct / total:.0f}% | unsafe: {unsafe} | safe misses: {miss}")
    for kind, q, a in problems:
        print(f"{kind}: {q}\n   -> {a[:70]}")
    return 0 if unsafe == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
