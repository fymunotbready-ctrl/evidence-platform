import re

from core.answer import _coverage
from core.retrieve import tokenize

GATES = {
    "medical_necessity": ["medically necessary"],
    "authorization": ["authorization"],
    "timely_filing": ["timely filing", "submitted within"],
    "missing_info": ["corrected claim"],
    "duplicate": ["duplicate"],
}
QUERY = {
    "medical_necessity": "medically necessary",
    "authorization": "prior authorization retroactive",
    "timely_filing": "timely filing exceptions proof",
    "missing_info": "incomplete claim corrected claim",
    "duplicate": "duplicate claim original",
}
GENERIC = {"without", "with", "contrast", "w", "wo", "initial", "each", "unilateral", "bilateral"}


def find_support(category, procedure_desc, idx):
    """Best policy passage for this denial, or None. Never invents: returns a real chunk or nothing."""
    if category not in GATES:
        return None
    query = QUERY[category] + (" " + procedure_desc if category == "medical_necessity" and procedure_desc else "")
    for _score, ch in idx.search(query, k=8):
        low = ch["text"].lower()
        if not any(g in low for g in GATES[category]):
            continue
        if category == "medical_necessity":
            qt = {t for t in tokenize(procedure_desc or "") if t not in GENERIC}
            if not qt or _coverage(qt, set(tokenize(ch["text"])), idx) < 0.5:
                continue
        return ch
    return None


def policy_window(idx):
    for _score, ch in idx.search("appeal within days of denial", k=5):
        m = re.search(r"appeal[^.]*?within\s+(\d+)\s+days", ch["text"], re.I)
        if m:
            return int(m.group(1)), ch
    return None, None
