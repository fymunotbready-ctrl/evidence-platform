import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
XLINK = "{http://www.w3.org/1999/xlink}href"


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "evidence-platform/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _text(el):
    parts = [el.text or ""]
    for c in el:
        if c.tag != "xref":
            parts.append(_text(c))
        parts.append(c.tail or "")
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _sections(sec, level, out):
    t = sec.find("title")
    if t is not None and _text(t):
        out.append("#" * min(level, 3) + " " + _text(t))
    for child in sec:
        if child.tag == "p" and _text(child):
            out.append(_text(child))
        elif child.tag == "sec":
            _sections(child, level + 1, out)


def jats_to_md(xml_text, meta):
    root = ET.fromstring(xml_text)
    title_el = root.find(".//article-title")
    title = _text(title_el) if title_el is not None else meta.get("title", "")
    lic = ""
    lic_el = root.find(".//license")
    if lic_el is not None:
        lic = lic_el.get(XLINK) or _text(lic_el)[:120]
    head = [("Title", title), ("Authors", meta.get("authorString", "")), ("Journal", meta.get("journalTitle", "")),
            ("Year", meta.get("pubYear", "")), ("PMCID", meta.get("pmcid", "")), ("PMID", meta.get("pmid", "")),
            ("DOI", meta.get("doi", "")), ("License", lic or "see article"), ("Source", "Europe PMC (open access)")]
    out = []
    ab = root.find(".//abstract")
    if ab is not None:
        ps = [_text(p) for p in ab.iter("p") if _text(p)]
        if ps:
            out.append("# Abstract")
            out.extend(ps)
    body = root.find(".//body")
    if body is not None:
        for sec in body.findall("sec"):
            _sections(sec, 1, out)
        for p in body.findall("p"):
            if _text(p):
                out.append(_text(p))
    header = "\n".join(f"{k}: {v}" for k, v in head if v)
    return header + "\n\n" + "\n\n".join(out) + "\n"


def fetch_papers(query, outdir, max_results=5, getter=_get):
    q = f"({query}) AND OPEN_ACCESS:y"
    url = (f"{BASE}/search?query={urllib.parse.quote(q)}&format=json&resultType=lite"
           f"&pageSize={min(max_results * 3, 25)}")
    results = json.loads(getter(url)).get("resultList", {}).get("result", [])
    keep = [r for r in results if re.fullmatch(r"PMC\d+", str(r.get("pmcid", "")))
            and str(r.get("isOpenAccess", "")).upper() == "Y"][:max_results]
    saved = []
    for r in keep:
        xml = getter(f"{BASE}/{r['pmcid']}/fullTextXML")
        md = jats_to_md(xml, r)
        path = f"{outdir}/{r['pmcid']}.md"
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        saved.append((r["pmcid"], r.get("title", "")))
    return saved
