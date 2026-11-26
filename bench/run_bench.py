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
    correct = draft = miss = unsafe = 0
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
            continue
        hit = all(k in ans.lower() for k in expect)
        if not held and hit:
            correct += 1
        elif not held:
            unsafe += 1
            problems.append(("UNSAFE", q, ans))
        elif hit:
            draft += 1
        else:
            miss += 1
            problems.append(("MISS", q, ans))
    total = len(CASES)
    print(f"AUTO-CORRECT {correct}/{total} | GOOD DRAFTS {draft} | MISSES {miss} | UNSAFE {unsafe}")
    print(f"USEFUL = {100 * (correct + draft) / total:.0f}%")
    for kind, q, a in problems:
        print(f"{kind}: {q}\n   -> {a[:70]}")
    return 0 if unsafe == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
