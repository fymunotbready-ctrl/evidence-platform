import math

DEFAULTS = {
    "derate": 0.80, "offset_pct": 100.0, "panel_w": 400.0, "price_per_watt": 3.00,
    "battery_load_kw": 0.0, "battery_hours": 0.0, "battery_kwh": 13.5, "battery_dod": 0.90,
    "battery_price": 9000.0, "incentive_pct": 0.0, "escalation": 0.0, "degradation": 0.005, "years": 25,
}
BOUNDS = {
    "annual_kwh": (1, 200000), "psh": (1.0, 9.0), "rate": (0.01, 2.0), "derate": (0.5, 0.95),
    "offset_pct": (10, 150), "panel_w": (250, 700), "price_per_watt": (0.5, 10),
    "battery_load_kw": (0, 50), "battery_hours": (0, 72), "battery_kwh": (1, 50), "battery_dod": (0.5, 1.0),
    "battery_price": (0, 50000), "incentive_pct": (0, 60), "escalation": (0, 0.10),
    "degradation": (0, 0.03), "years": (1, 40),
}


class InputError(ValueError):
    pass


def _ceil(x):
    return math.ceil(round(x, 9))  # guards float noise like 19.000000000001


def validate(inp):
    for k, (lo, hi) in BOUNDS.items():
        v = inp.get(k)
        if v is None:
            continue
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not (lo <= v <= hi):
            raise InputError(f"{k} must be between {lo} and {hi} (got {v})")


def calculate(raw):
    """All the math. Same inputs always give the same outputs."""
    inp = {**DEFAULTS, **{k: v for k, v in raw.items() if v is not None}}
    for need in ("annual_kwh", "psh"):
        if inp.get(need) is None:
            raise InputError(f"{need} is required")
    validate(inp)
    annual, psh, derate = inp["annual_kwh"], inp["psh"], inp["derate"]
    yield_per_kw = psh * 365 * derate                       # kWh per kW-DC per year
    target = annual * inp["offset_pct"] / 100.0
    raw_kw = target / yield_per_kw
    panels = max(1, _ceil(raw_kw * 1000 / inp["panel_w"]))
    kw = panels * inp["panel_w"] / 1000.0
    prod = kw * yield_per_kw
    out = {"yield_per_kw": yield_per_kw, "target_kwh": target, "raw_kw": raw_kw, "panels": panels,
           "kw_dc": kw, "production_kwh": prod, "offset_actual_pct": prod / annual * 100.0}
    # battery (backup sizing only)
    units, nominal = 0, 0.0
    if inp["battery_load_kw"] > 0 and inp["battery_hours"] > 0:
        usable = inp["battery_load_kw"] * inp["battery_hours"]
        units = _ceil(usable / inp["battery_dod"] / inp["battery_kwh"])
        nominal = units * inp["battery_kwh"]
    out.update(battery_units=units, battery_nominal_kwh=nominal)
    # cost
    system_cost = kw * 1000 * inp["price_per_watt"]
    battery_cost = units * inp["battery_price"]
    gross = system_cost + battery_cost
    incentive = gross * inp["incentive_pct"] / 100.0
    net = gross - incentive
    out.update(system_cost=system_cost, battery_cost=battery_cost, gross_cost=gross, incentive=incentive, net_cost=net)
    # savings
    rate = inp.get("rate")
    if rate:
        total = 0.0
        for y in range(1, int(inp["years"]) + 1):
            total += prod * (1 - inp["degradation"]) ** (y - 1) * rate * (1 + inp["escalation"]) ** (y - 1)
        y1 = prod * rate
        out.update(year1_savings=y1, payback_years=(net / y1 if y1 > 0 else None),
                   lifetime_savings=total, lifetime_net=total - net)
    else:
        out.update(year1_savings=None, payback_years=None, lifetime_savings=None, lifetime_net=None)
    warnings = []
    if out["offset_actual_pct"] > 110:
        warnings.append("Production is well above usage; excess is assumed credited at the retail rate (net metering). Many utilities pay less.")
    if kw > 20:
        warnings.append("System above 20 kW is unusual for a home; double-check the usage figure.")
    out["warnings"] = warnings
    out["inputs"] = inp
    return out
