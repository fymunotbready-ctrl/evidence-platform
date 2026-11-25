import re
from datetime import date

CARC = {
    "CO-50": "service not deemed medically necessary by the payer",
    "CO-197": "precertification, authorization or notification absent",
    "CO-29": "time limit for filing has expired",
    "CO-16": "claim lacks information needed for adjudication",
    "CO-18": "duplicate claim or service",
}
CATEGORY = {"CO-50": "medical_necessity", "CO-197": "authorization", "CO-29": "timely_filing",
            "CO-16": "missing_info", "CO-18": "duplicate"}
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


class InputError(ValueError):
    pass


def check_synthetic(text):
    """Hard rule: no real patient data until BAA + guardian/legal setup exist."""
    if "SYNTHETIC" not in text[:300].upper():
        raise InputError("Module A accepts SYNTHETIC test data only (first lines must say SYNTHETIC). "
                         "Real patient data needs legal agreements first.")
    if SSN.search(text):
        raise InputError("Text looks like it contains a Social Security number. Refusing.")


def _find(pat, text):
    m = re.search(pat, text, re.I | re.M)
    return m.group(1).strip() if m else None


def _date(label, value):
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise InputError(f"{label} must be YYYY-MM-DD, got: {value}")


def parse_denial(text):
    check_synthetic(text)
    code = _find(r"^Reason code:\s*([A-Z]{2}-\d+)", text)
    d = {
        "payer": _find(r"^Payer:\s*(.+)$", text),
        "claim": _find(r"^Claim\s*(?:#|number|no\.?):\s*(\S+)", text),
        "denial_date": _date("Date of denial", _find(r"^Date of denial:\s*(\S+)", text)),
        "service_date": _date("Date of service", _find(r"^Date of service:\s*(\S+)", text)),
        "code": code,
        "procedure_code": _find(r"^Service:\s*(?:CPT\s*)?(\d{5})", text),
        "procedure_desc": _find(r"^Service:\s*(?:CPT\s*)?\d{5}\s*[-:]\s*(.+)$", text),
        "reason_text": _find(r"^Reason:\s*(.+)$", text),
    }
    w = _find(r"appeal[^.\n]*?within\s+(\d+)\s+days", text)
    d["window_days"] = int(w) if w else None
    missing = [k for k in ("payer", "claim", "denial_date", "code") if not d[k]]
    if missing:
        raise InputError("Missing fields in denial letter: " + ", ".join(missing))
    d["category"] = CATEGORY.get(code, "unknown")
    d["meaning"] = CARC.get(code, "reason code not in the built-in list")
    return d


FACT_KEYS = ("clinical", "proof", "auth_number", "urgent")


def parse_facts(text):
    facts = {}
    for line in text.splitlines():
        if ":" in line and not line.strip().startswith("#"):
            k, v = line.split(":", 1)
            k, v = k.strip().lower(), v.strip()
            if k in FACT_KEYS and v:
                facts.setdefault(k, []).append(v)
    return facts
