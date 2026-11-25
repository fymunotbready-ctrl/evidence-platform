"""Approved-answer memory: only human-verified answers are learned."""
import json, os, re

TENANT_RE = re.compile(r"^[a-z0-9-]{1,40}$")
STOP = set("a an the do does you your is are of to for and or in on with we our how what".split())
ROOT = os.environ.get("EP_MEMORY_DIR", "data/memory")


def _path(tenant):
    if not TENANT_RE.match(tenant or ""):
        raise ValueError("Invalid tenant id (use a-z, 0-9, hyphen; max 40 chars)")
    return os.path.join(ROOT, tenant + ".json")


def _tokens(q):
    return {w for w in re.findall(r"[a-z0-9]+", q.lower()) if w not in STOP}


def load(tenant):
    p = _path(tenant)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def learn(tenant, final_rows):
    """final_rows: [question, answer, source, status] rows from finalize()."""
    mem = {m["question"]: m for m in load(tenant)}
    added = 0
    for q, ans, src, status in final_rows:
        if status in ("approved", "edited") and str(ans).strip():
            mem[q] = {"question": q, "answer": ans, "source": src, "status": status}
            added += 1
    os.makedirs(ROOT, exist_ok=True)
    tmp = _path(tenant) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(list(mem.values()), f, indent=1)
    os.replace(tmp, _path(tenant))
    return added


def lookup(tenant, question, threshold=0.6):
    t = _tokens(question)
    if not t:
        return None
    best, score = None, 0.0
    for m in load(tenant):
        u = _tokens(m["question"])
        s = len(t & u) / len(t | u) if u else 0.0
        if s > score:
            best, score = m, s
    if best and score >= threshold:
        return dict(best, match=round(score, 2))
    return None
