import csv

HEADERS = ("question", "questions", "control", "requirement")


def read_questions(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = [r for r in csv.reader(f) if r and any(c.strip() for c in r)]
    if not rows:
        return []
    header = [c.strip().lower() for c in rows[0]]
    col = 0
    for name in HEADERS:
        if name in header:
            col = header.index(name)
            rows = rows[1:]
            break
    return [r[col].strip() for r in rows if len(r) > col and r[col].strip()]


def write_answers(path, results):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["question", "answer", "confidence", "source", "status"])
        for r in results:
            src = r["citations"][0]["chunk_id"] if r["citations"] else ""
            w.writerow([r["question"], r["answer"], r["confidence"], src,
                        "needs_review" if r["needs_review"] else "ok"])


def finalize(out_csv, final_csv, queue_items):
    """Merge human review decisions into the answered CSV."""
    with open(out_csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    final = []
    for r in rows:
        ans, status = r["answer"], "auto" if r["status"] == "ok" else "PENDING REVIEW"
        if r["status"] != "ok":
            for it in reversed(queue_items):
                if it["question"] == r["question"]:
                    if it["status"] == "approved":
                        status = "approved"
                    elif it["status"] == "edited":
                        ans, status = it["final_answer"], "edited"
                    elif it["status"] == "rejected":
                        ans, status = "", "rejected"
                    break
        final.append([r["question"], ans, r["source"], status])
    with open(final_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["question", "answer", "source", "status"])
        w.writerows(final)
    return final
