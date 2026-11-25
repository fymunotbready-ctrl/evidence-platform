import argparse
import os
import sys
from datetime import date

from core.audit import AuditLog
from core.tenant import TenantStore
from . import data
from .bill import extract_bill, read_bill_text
from .pdf import make_pdf
from .projects import Projects, STATUSES
from .quote import quote_lines
from .sizing import InputError, calculate

HOME = os.environ.get("EVIDENCE_HOME", os.path.expanduser("~/.evidence-data"))


def _tenant(tid):
    s = TenantStore(HOME)
    if not s.exists(tid):
        s.create(tid)
    d = s.dir(tid)
    return Projects(os.path.join(d, "projects.json")), AuditLog(os.path.join(d, "audit.jsonl"))


def resolve(a):
    """Turn user flags into calculator inputs plus honest notes about where each number came from."""
    state = a.state.upper() if a.state else None
    if state and state not in data.SUN_HOURS:
        raise InputError(f"Unknown state {state}. Known: {', '.join(sorted(data.SUN_HOURS))}. Or pass --psh and --rate.")
    notes, bill = [], None
    if a.kwh_year:
        annual, quality, src = a.kwh_year, "high", "customer-provided annual usage"
    elif a.monthly_kwh:
        try:
            vals = [float(x) for x in a.monthly_kwh.split(",") if x.strip()]
        except ValueError:
            raise InputError("--monthly-kwh must be numbers separated by commas")
        if not vals or any(v <= 0 for v in vals):
            raise InputError("--monthly-kwh needs positive numbers")
        annual = sum(vals) / len(vals) * 12
        quality = "high" if len(vals) == 12 else "medium"
        src = f"{len(vals)} monthly values, annualized"
    elif a.bill_file:
        bill = extract_bill(read_bill_text(a.bill_file))
        if bill["kwh"] is None:
            hint = f" Candidates found: {bill['candidates']}." if bill["candidates"] else ""
            raise InputError("Could not find one clear kWh-used figure in the bill." + hint + " Use --kwh-year or --monthly-kwh.")
        annual = bill["kwh"] / bill["days"] * 365 if bill["days"] else bill["kwh"] * 12
        quality = "low"
        src = f"one bill ({bill['kwh_line']})"
        notes.append("Annualized from a single bill; seasonal swings are not captured. Get 12 months if you can.")
    elif a.bill:
        if not (a.rate or a.state):
            raise InputError("--bill needs --rate or --state to convert dollars to kWh")
        rate_for_usage = a.rate or data.RATES[state]
        annual, quality, src = a.bill / rate_for_usage * 12, "low", f"monthly bill ${a.bill:,.0f} / rate, x12"
        notes.append("Usage derived from dollars, not kWh; bills include fixed fees, so real kWh may be lower.")
    else:
        raise InputError("Give usage: --kwh-year, --monthly-kwh, --bill-file or --bill")
    if a.rate:
        rate, rsrc = a.rate, "customer-provided"
    elif bill and bill["rate"]:
        rate, rsrc = bill["rate"], "from the bill"
    elif state:
        rate, rsrc = data.RATES[state], f"APPROXIMATE {state} average"
        notes.append("Rate is a rough state average; use the customer's real rate before quoting.")
    else:
        raise InputError("Need a rate: --rate, a bill with a rate line, or --state")
    if a.psh:
        psh, psrc = a.psh, "customer/installer-provided"
    elif state:
        psh, psrc = data.SUN_HOURS[state], f"APPROXIMATE {state} average"
        notes.append("Sun hours are a rough state average; check NREL PVWatts for the exact site.")
    else:
        raise InputError("Need sun hours: --psh or --state")
    inputs = {"annual_kwh": annual, "psh": psh, "rate": rate, "derate": a.derate, "offset_pct": a.offset,
              "panel_w": a.panel_watts, "price_per_watt": a.price_per_watt, "battery_load_kw": a.battery_kw,
              "battery_hours": a.battery_hours, "battery_kwh": a.battery_kwh, "battery_price": a.battery_price,
              "incentive_pct": a.incentive_pct, "escalation": (a.escalation / 100.0 if a.escalation is not None else None)}
    meta = {"usage_source": src, "data_quality": quality, "rate_source": rsrc, "psh_source": psrc, "assumptions": notes}
    return inputs, meta


def cmd_quote(a):
    projects, audit = _tenant(a.tenant)
    inputs, meta = resolve(a)
    results = calculate(inputs)
    today = a.today or date.today().isoformat()
    proj = projects.add(a.name, results, meta, today)
    proj["meta"] = meta
    lines = quote_lines(proj)
    txt = a.txt or f"quote_{proj['id']}.txt"
    open(txt, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    r = results
    print(f"{proj['id']} {a.name}: {r['panels']} panels = {r['kw_dc']:.2f} kW | output {r['production_kwh']:,.0f} kWh/yr "
          f"({r['offset_actual_pct']:.0f}%)")
    print(f"Net cost ${r['net_cost']:,.0f}" + (f" | payback {r['payback_years']:.1f} yrs" if r["payback_years"] else ""))
    print(f"Data quality: {meta['data_quality']}")
    for n in meta["assumptions"] + r["warnings"]:
        print(f"Note: {n}")
    print(f"Saved: {txt}")
    if a.pdf:
        open(a.pdf, "wb").write(make_pdf(lines))
        print(f"PDF: {a.pdf}")
    audit.append("user", "quote", {"id": proj["id"], "kw": round(r["kw_dc"], 2), "quality": meta["data_quality"]})
    return 0


def cmd_projects(a):
    items = _tenant(a.tenant)[0].all()
    if not items:
        print("No projects yet.")
    for i in items:
        r = i["results"]
        print(f"{i['id']} | {i['name']} | {r['kw_dc']:.1f} kW | ${r['net_cost']:,.0f} | {i['status']} | {i['created']}")
    return 0


def cmd_show(a):
    p = _tenant(a.tenant)[0].get(a.id)
    print("\n".join(quote_lines(p)))
    return 0


def cmd_status(a):
    projects, audit = _tenant(a.tenant)
    projects.set_status(a.id, a.status, a.today or date.today().isoformat())
    audit.append("user", "status", {"id": a.id, "status": a.status})
    print(f"{a.id} -> {a.status}")
    return 0


def cmd_eval(a):
    from . import evaluate as ev
    res = ev.evaluate()
    print(f"Worked examples {res['correct']}/{res['total']} correct")
    for f in res["fails"]:
        print("  FAIL:", f)
    print("RESULT:", "PASS" if res["passed"] else "FAIL")
    if a.log:
        ev.log_result(res)
        print("Logged to golden/history.jsonl")
    return 0 if res["passed"] else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="energy")
    sub = p.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("quote")
    q.add_argument("tenant"); q.add_argument("name")
    q.add_argument("--kwh-year", type=float); q.add_argument("--monthly-kwh"); q.add_argument("--bill-file")
    q.add_argument("--bill", type=float, help="monthly bill in dollars")
    q.add_argument("--rate", type=float, help="$/kWh"); q.add_argument("--state"); q.add_argument("--psh", type=float)
    q.add_argument("--offset", type=float); q.add_argument("--panel-watts", type=float); q.add_argument("--derate", type=float)
    q.add_argument("--price-per-watt", type=float); q.add_argument("--battery-kw", type=float)
    q.add_argument("--battery-hours", type=float); q.add_argument("--battery-kwh", type=float)
    q.add_argument("--battery-price", type=float); q.add_argument("--incentive-pct", type=float)
    q.add_argument("--escalation", type=float, help="percent per year, e.g. 3")
    q.add_argument("--pdf"); q.add_argument("--txt"); q.add_argument("--today")
    v = sub.add_parser("projects"); v.add_argument("tenant")
    s = sub.add_parser("show"); s.add_argument("tenant"); s.add_argument("id")
    t = sub.add_parser("status"); t.add_argument("tenant"); t.add_argument("id"); t.add_argument("status", choices=STATUSES); t.add_argument("--today")
    g = sub.add_parser("eval"); g.add_argument("--log", action="store_true")
    a = p.parse_args(argv)
    try:
        return {"quote": cmd_quote, "projects": cmd_projects, "show": cmd_show, "status": cmd_status, "eval": cmd_eval}[a.cmd](a)
    except (InputError, ValueError, KeyError, RuntimeError, FileNotFoundError, OSError) as ex:
        print(f"Error: {ex}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
