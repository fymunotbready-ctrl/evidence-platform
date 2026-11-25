import re

from core.ingest import read_docx, read_pdf

USAGE_WORDS = ("used", "usage", "consumption", "total")
KWH_A = re.compile(r"([\d,]+(?:\.\d+)?)\s*kwh", re.I)
KWH_B = re.compile(r"kwh[^\d\n$]{0,25}([\d,]+(?:\.\d+)?)", re.I)
RATE = re.compile(r"\$\s?(0?\.\d{2,5})\s*(?:per|/)\s*kwh", re.I)
DAYS = re.compile(r"\(?\b(\d{2,3})\s*days\b", re.I)


def read_bill_text(path):
    p = str(path).lower()
    if p.endswith(".pdf"):
        return read_pdf(path)
    if p.endswith(".docx"):
        return read_docx(path)
    return open(path, encoding="utf-8", errors="replace").read()


def extract_bill(text):
    """Pull usage (kWh), billing days and rate from a bill, with the source line as the citation.
    Returns kwh=None when there is no clear single answer - never guesses between candidates."""
    found, rate, days = [], None, None
    for line in text.splitlines():
        low = line.lower()
        m = RATE.search(line)
        if m and rate is None:
            rate = (float(m.group(1)), line.strip())
        if days is None:
            d = DAYS.search(line)
            if d:
                days = int(d.group(1))
        if "kwh" in low and any(w in low for w in USAGE_WORDS) and "per kwh" not in low and "rate" not in low:
            m = KWH_B.search(line) or KWH_A.search(line)
            if m:
                found.append((float(m.group(1).replace(",", "")), line.strip()))
    values = {v for v, _ in found}
    if len(values) == 1:
        kwh, line = found[0]
    elif len(values) > 1:
        tot = [f for f in found if "total" in f[1].lower()]
        kwh, line = (tot[0] if tot and len({v for v, _ in tot}) == 1 else (None, None))
    else:
        kwh, line = None, None
    return {"kwh": kwh, "kwh_line": line, "days": days, "rate": rate[0] if rate else None,
            "rate_line": rate[1] if rate else None, "candidates": sorted(values)}
