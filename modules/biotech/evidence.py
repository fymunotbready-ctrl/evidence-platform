from core.answer import _coverage
from core.ingest import SENT
from core.retrieve import tokenize
from .library import IDENT, norm_ident
from .links import data_links, paper_links
from .safety import check_question

DISCLAIMER = "Research summary from the cited papers. Not medical advice."
FILLER = {"many", "much", "each", "per"}  # question words that never appear in answers


def ask(question, lib, min_cov=0.5, review_below=0.75, max_items=3):
    refused, msg = check_question(question)
    if refused:
        return {"kind": "refused", "question": question, "message": msg, "evidence": [], "confidence": 0.0,
                "needs_review": False, "support": "none", "links": []}
    qt = set(tokenize(question)) - FILLER
    q_idents = {norm_ident(x) for x in IDENT.findall(question)}
    cands = []
    for _score, ch in lib.index.search(question, k=10):
        meta = lib.meta(ch["source"])
        if q_idents and not q_idents <= meta["idents"]:
            continue
        sec = set(tokenize(ch.get("section", "")))
        for sent in SENT.split(ch["text"]):
            cov = _coverage(qt, set(tokenize(sent)) | sec, lib.index) if qt else 0.0
            if cov >= min_cov:
                cands.append((cov, sent.strip(), ch))
    cands.sort(key=lambda c: -c[0])
    ev, seen, per_source = [], set(), {}
    for cov, sent, ch in cands:
        if sent in seen or per_source.get(ch["source"], 0) >= 2:
            continue
        seen.add(sent)
        per_source[ch["source"]] = per_source.get(ch["source"], 0) + 1
        m = lib.meta(ch["source"])
        ev.append({"sentence": sent, "source": ch["source"], "chunk_id": ch["id"], "section": ch.get("section", ""),
                   "title": m["title"], "year": m.get("year", ""), "coverage": round(cov, 2), "license": m.get("license", "")})
        if len(ev) == max_items:
            break
    if not ev:
        return {"kind": "not_found", "question": question, "message": "Not found in the provided papers.", "evidence": [],
                "confidence": 0.0, "needs_review": True, "support": "none", "links": []}
    conf = ev[0]["coverage"]
    sources = {e["source"] for e in ev}
    links, seen_l = [], set()
    for e in ev:
        passage = next(c["text"] for c in lib.chunks if c["id"] == e["chunk_id"])
        for item in (paper_links(lib.meta(e["source"])) if e["source"] not in seen_l else []) + data_links(passage):
            if item not in links:
                links.append(item)
        seen_l.add(e["source"])
    return {"kind": "answer", "question": question, "evidence": ev, "confidence": conf,
            "needs_review": conf < review_below, "support": "multiple papers" if len(sources) > 1 else "single paper",
            "links": links, "message": DISCLAIMER}
