import csv
import re
import shutil
import subprocess
import zipfile
from html import unescape
from pathlib import Path

SENT = re.compile(r"(?<=[.!?])\s+")
SUPPORTED = (".txt", ".md", ".csv", ".docx", ".pdf")


def chunk_text(text, source, max_chars=500):
    chunks, section = [], ""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    for p in paras:
        if all(line.lstrip().startswith("#") for line in p.splitlines()):
            section = p.splitlines()[-1].lstrip("# ").strip()  # headings label the next chunks, not answers
            continue
        if len(p) <= max_chars:
            pieces = [p]
        else:
            pieces, cur = [], ""
            for s in SENT.split(p):
                if cur and len(cur) + len(s) + 1 > max_chars:
                    pieces.append(cur)
                    cur = s
                else:
                    cur = (cur + " " + s).strip()
            if cur:
                pieces.append(cur)
        for piece in pieces:
            chunks.append({"id": f"{source}#{len(chunks) + 1}", "source": source, "section": section, "text": piece})
    return chunks


def read_docx(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    xml = re.sub(r"</w:p>", "\n\n", xml)
    xml = re.sub(r"<w:tab/>", " ", xml)
    return unescape(re.sub(r"<[^>]+>", "", xml))


def read_pdf(path):
    exe = shutil.which("pdftotext")
    if not exe:
        raise RuntimeError("PDF support needs poppler. Run: pkg install poppler -y")
    out = subprocess.run([exe, "-layout", str(path), "-"], capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        raise RuntimeError(f"Could not read PDF {path}: {out.stderr.strip()[:200]}")
    return out.stdout.replace("\f", "\n\n")


def load_file(path):
    p = Path(path)
    suf = p.suffix.lower()
    if suf in (".txt", ".md"):
        text = p.read_text(encoding="utf-8", errors="replace")
    elif suf == ".csv":
        with p.open(newline="", encoding="utf-8", errors="replace") as f:
            text = "\n\n".join(" | ".join(r) for r in csv.reader(f) if any(c.strip() for c in r))
    elif suf == ".docx":
        text = read_docx(p)
    elif suf == ".pdf":
        text = read_pdf(p)
    else:
        raise ValueError(f"Unsupported file type: {suf} (supported: .txt .md .csv .docx .pdf)")
    return chunk_text(text, p.name)


def load_dir(directory):
    chunks = []
    for p in sorted(Path(directory).iterdir()):
        if p.is_file() and p.suffix.lower() in SUPPORTED:
            chunks.extend(load_file(p))
    return chunks
