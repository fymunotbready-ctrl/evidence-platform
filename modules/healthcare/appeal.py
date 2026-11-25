from datetime import timedelta

from .policy import find_support, policy_window

REC = {"medical_necessity": "appeal", "authorization": "appeal", "timely_filing": "appeal",
       "missing_info": "resubmit_corrected_claim", "duplicate": "verify_original_claim",
       "unknown": "manual_review"}
ATTACH = {
    "medical_necessity": ["Copy of the denial letter", "Medical records for the date of service",
                          "Letter of medical necessity from the treating clinician"],
    "authorization": ["Copy of the denial letter", "Authorization number or proof it was requested"],
    "timely_filing": ["Copy of the denial letter", "Proof of timely submission (e.g. clearinghouse acceptance report)"],
}
DISCLAIMER = "DRAFT - must be reviewed by the provider's billing/clinical staff before sending. Not medical or legal advice."


def rate(cat, support, facts, deadline_passed):
    if cat in ("missing_info", "duplicate"):
        return "n/a"
    if cat == "unknown" or deadline_passed or support is None:
        return "weak"
    if cat == "medical_necessity":
        return "strong" if facts.get("clinical") else "medium"
    if cat == "authorization":
        return "strong" if facts.get("auth_number") else ("medium" if facts.get("urgent") else "weak")
    if cat == "timely_filing":
        return "strong" if facts.get("proof") else "weak"
    return "weak"


def _missing_facts(cat, facts):
    need = {"medical_necessity": ("clinical", "Clinical facts from the treating clinician showing each policy criterion is met"),
            "authorization": ("auth_number", "Authorization number (or proof of urgency for retroactive authorization)"),
            "timely_filing": ("proof", "Proof of timely submission")}
    if cat in need and not facts.get(need[cat][0]):
        return [need[cat][1]]
    return []


def _facts_block(cat, facts):
    lines = []
    if cat == "medical_necessity":
        lines = [f"- {v}" for v in facts.get("clinical", [])]
    elif cat == "authorization":
        lines = [f"- Authorization number: {v}" for v in facts.get("auth_number", [])]
        lines += [f"- Urgency: {v}" for v in facts.get("urgent", [])]
    elif cat == "timely_filing":
        lines = [f"- Proof of timely submission: {v}" for v in facts.get("proof", [])]
    return "\n".join(lines) if lines else "[TO ADD: supporting facts from the provider - none were supplied]"


def draft(c):
    cat, sup = c["category"], c["support"]
    if cat == "unknown":
        return None
    if cat == "missing_info":
        return ("ACTION NOTE (not an appeal): this claim was denied as incomplete.\n"
                f"Fix the information named in the denial and submit a corrected claim for {c['claim']}.\n"
                + (f"Policy ({sup['source']}): \"{sup['text']}\"\n" if sup else "") + DISCLAIMER + "\n")
    if cat == "duplicate":
        return ("ACTION NOTE (not an appeal): this claim was denied as a duplicate.\n"
                f"Check the status of the original claim before doing anything for {c['claim']}.\n"
                + (f"Policy ({sup['source']}): \"{sup['text']}\"\n" if sup else "") + DISCLAIMER + "\n")
    svc = f"{c['procedure_code']} {c['procedure_desc']}".strip() if c["procedure_code"] else "the billed service"
    policy_line = (f"Policy basis - {c['payer']} policy ({sup['source']}{', ' + sup['section'] if sup['section'] else ''}): "
                   f"\"{sup['text']}\"") if sup else "[TO ADD: payer policy supporting this request - none was found automatically]"
    enclosures = "\n".join(f"- {a}" for a in ATTACH[cat])
    return (f"{DISCLAIMER}\n\n"
            f"RE: Appeal of claim {c['claim']} - denial dated {c['denial_date']}\n\n"
            f"To the Appeals Department, {c['payer']}:\n\n"
            f"We are appealing the denial of {svc} (claim {c['claim']}), denied on {c['denial_date']} "
            f"under reason code {c['code']} ({c['meaning']}).\n\n"
            f"{policy_line}\n\n"
            f"Supporting facts:\n{_facts_block(cat, c['facts'])}\n\n"
            "We ask that you reconsider and overturn this denial and process the claim for payment.\n\n"
            f"Enclosures:\n{enclosures}\n\nSincerely,\n[PROVIDER NAME / CONTACT]\n")


def build_case(denial, facts, idx, today):
    c = dict(denial)
    c["facts"] = facts
    cat = c["category"]
    ch = find_support(cat, c["procedure_desc"], idx)
    c["support"] = ({"source": ch["source"], "chunk_id": ch["id"], "section": ch.get("section", ""), "text": ch["text"]}
                    if ch else None)
    pdays, _pch = policy_window(idx)
    window = c["window_days"] or pdays
    c["window_days"] = window
    c["deadline"], c["days_left"] = None, None
    passed = None
    if cat in ATTACH and window:
        c["deadline"] = c["denial_date"] + timedelta(days=window)
        c["days_left"] = (c["deadline"] - today).days
        passed = c["days_left"] < 0
    c["deadline_passed"] = passed
    c["recommendation"] = REC[cat]
    c["strength"] = rate(cat, c["support"], facts, passed)
    reasons = []
    if cat == "unknown":
        reasons.append("Reason code not recognised - needs a human")
    if cat in ATTACH and c["support"] is None:
        reasons.append("No matching policy passage found for this denial")
    if passed:
        reasons.append(f"Appeal deadline passed {-c['days_left']} days ago")
    if cat in ATTACH and window is None:
        reasons.append("Appeal window not found in letter or policy")
    c["missing"] = _missing_facts(cat, facts) if cat in ATTACH else []
    c["reasons"] = reasons
    c["needs_review"] = c["strength"] == "weak" or c["recommendation"] == "manual_review"
    c["letter"] = draft(c)
    return c
