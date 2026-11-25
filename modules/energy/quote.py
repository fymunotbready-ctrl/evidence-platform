def _m(x):
    return f"${x:,.0f}"


def quote_lines(p):
    r, i = p["results"], p["results"]["inputs"]
    meta = p["meta"]
    L = ["SOLAR + BATTERY ESTIMATE  (NOT A BINDING QUOTE)",
         f"Project: {p['name']} ({p['id']})    Date: {p['created']}", "=" * 60, "", "USAGE",
         f"  Annual usage:         {i['annual_kwh']:,.0f} kWh",
         f"  Source:               {meta['usage_source']}",
         f"  Data quality:         {meta['data_quality']}", "", "SYSTEM",
         f"  Panels:               {r['panels']} x {i['panel_w']:.0f} W = {r['kw_dc']:.2f} kW DC",
         f"  Est. annual output:   {r['production_kwh']:,.0f} kWh ({r['offset_actual_pct']:.0f}% of usage)"]
    if r["battery_units"]:
        L.append(f"  Battery backup:       {r['battery_units']} x {i['battery_kwh']:g} kWh = {r['battery_nominal_kwh']:.1f} kWh "
                 f"({i['battery_load_kw']:g} kW for {i['battery_hours']:g} h)")
    L += ["", "COST  (default prices are SAMPLES - set your own)",
          f"  Solar system:         {_m(r['system_cost'])}"]
    if r["battery_units"]:
        L.append(f"  Battery:              {_m(r['battery_cost'])}")
    L += [f"  Gross cost:           {_m(r['gross_cost'])}",
          f"  {'Incentives (' + format(i['incentive_pct'], 'g') + '%):':<22}-{_m(r['incentive'])}",
          f"  NET COST:             {_m(r['net_cost'])}", ""]
    if r["year1_savings"] is not None:
        pb = f"{r['payback_years']:.1f} years" if r["payback_years"] else "n/a"
        L += ["SAVINGS", f"  Rate used:            ${i['rate']:.3f}/kWh ({meta['rate_source']})",
              f"  Year-1 savings:       {_m(r['year1_savings'])}", f"  Simple payback:       {pb}",
              f"  {int(i['years'])}-year savings:      {_m(r['lifetime_savings'])}",
              f"  {int(i['years'])}-year net:          {_m(r['lifetime_net'])}", ""]
    L.append("ASSUMPTIONS")
    L += [f"  - Peak sun hours {i['psh']:g}/day ({meta['psh_source']}); system losses {round((1 - i['derate']) * 100)}%",
          f"  - Panel degradation {i['degradation'] * 100:.1f}%/yr; price escalation {i['escalation'] * 100:.1f}%/yr",
          "  - Battery savings (backup value, time-of-use) are not modeled"]
    L += [f"  - {a}" for a in meta["assumptions"]] + [f"  - {w}" for w in r["warnings"]]
    L += ["", "IMPORTANT",
          "  Estimate only. Final design and price need a site survey (roof, shading,",
          "  structure), permits, interconnection approval and current incentive rules."]
    return L
