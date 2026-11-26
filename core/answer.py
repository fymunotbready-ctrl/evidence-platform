from .ingest import SENT
from .retrieve import tokenize
from .compose import compose

NOT_FOUND = "Not found in the provided documents."


def not_found(question):
    return {"question": question, "answer": NOT_FOUND, "citations": [], "confidence": 0.0, "needs_review": True}


def _coverage(qt, st, index):
    """IDF-weighted share of the question's words found in the sentence (0..1)."""
    total = sum(index.idf(t) for t in qt)
    return (sum(index.idf(t) for t in qt & st) / total) if total else 0.0


def answer(question, index, min_cov=0.5, review_below=0.75, llm=None):
    """Cited answer or 'not found'. Every real answer carries a citation.
    llm: optional callable(question, passage) -> str that rewrites the answer from the cited passage."""
    qt = set(tokenize(question))
    if not qt:
        return not_found(question)
    best = None
    for _score, ch in index.search(question, k=3):
        for sent in SENT.split(ch["text"]):
            cov = _coverage(qt, set(tokenize(sent)), index)
            if best is None or cov > best[0]:
                best = (cov, sent.strip(), ch)
    if best is None or best[0] < min_cov:
        return not_found(question)
    cov, sent, ch = best
    text, conf = sent, round(min(1.0, cov), 2)
    text, needs_human = compose(question, text)
    if needs_human:
        conf = min(conf, 0.5)
    if llm is not None:
        out = llm(question, ch["text"])
        if out and out.strip():
            text, conf = out.strip(), round(min(conf, 0.9), 2)  # model output never earns full confidence
    return {
        "question": question,
        "answer": text,
        "citations": [{"source": ch["source"], "chunk_id": ch["id"], "section": ch.get("section", ""), "passage": ch["text"]}],
        "confidence": conf,
        "needs_review": conf < review_below,
    }
