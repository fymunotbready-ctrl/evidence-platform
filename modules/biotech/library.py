import re
from pathlib import Path

from core.ingest import chunk_text, read_docx, read_pdf
from core.retrieve import BM25

SUPPORTED = (".md", ".txt", ".pdf", ".docx")
HEADER_KEYS = {"title", "authors", "journal", "year", "pmcid", "pmid", "doi", "license", "source"}
HEADER_LINE = re.compile(r"^([A-Za-z ]{2,12}):\s*(.+)$")
IDENT = re.compile(r"\b[A-Za-z]{1,8}-?\d+[A-Za-z0-9]*\b")
DOI = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+")


def norm_ident(s):
    return s.replace("-", "").lower()


def idents(text):
    return {norm_ident(m) for m in IDENT.findall(text)}


def _split_header(text):
    meta, lines, i = {}, text.splitlines(), 0
    while i < len(lines):
        m = HEADER_LINE.match(lines[i].strip())
        if not m or m.group(1).strip().lower() not in HEADER_KEYS:
            break
        meta[m.group(1).strip().lower()] = m.group(2).strip()
        i += 1
    return (meta, "\n".join(lines[i:])) if meta else ({}, text)


class Library:
    """A folder of open-access papers turned into a searchable, citable index."""

    def __init__(self, folder):
        self.papers, chunks = {}, []
        folder = Path(folder)
        if not folder.is_dir():
            raise FileNotFoundError(f"Papers folder not found: {folder}")
        for p in sorted(folder.iterdir()):
            if not p.is_file() or p.suffix.lower() not in SUPPORTED:
                continue
            suf = p.suffix.lower()
            if suf == ".pdf":
                meta, text = {}, read_pdf(p)
            elif suf == ".docx":
                meta, text = {}, read_docx(p)
            else:
                meta, text = _split_header(p.read_text(encoding="utf-8", errors="replace"))
            if "doi" not in meta:
                m = DOI.search(text)
                if m:
                    meta["doi"] = m.group(0).rstrip(".,;)")
            meta.setdefault("title", p.stem)
            ch = chunk_text(text, p.name)
            meta["idents"] = idents(meta["title"] + " " + text)
            meta["file"] = p.name
            self.papers[p.name] = meta
            chunks.extend(ch)
        if not chunks:
            raise ValueError(f"No readable papers in {folder} (supported: {', '.join(SUPPORTED)})")
        self.chunks = chunks
        self.index = BM25(chunks)

    def meta(self, source):
        return self.papers[source]
