import csv
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

HEADERS = ("question", "questions", "control", "requirement")
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NUMBERED = re.compile(r"^\s*(\d+[\.\)]|Q\d+[\.\):]?)\s+\S")
BAD_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _ext(path):
    return os.path.splitext(str(path))[1].lower()


def _col_index(letters):
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch.upper()) - 64
    return n - 1


def _col_letters(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _xlsx_rows(path):
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise ValueError(f"{os.path.basename(str(path))} is not a valid .xlsx file")
    with z:
        sst = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            sst = ["".join(t.text or "" for t in si.iter(NS + "t")) for si in root.iter(NS + "si")]
        sheets = sorted((n for n in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)),
                        key=lambda n: int(re.findall(r"\d+", n)[0]))
        if not sheets:
            raise ValueError("No worksheet found in the .xlsx file")
        root = ET.fromstring(z.read(sheets[0]))
        out = []
        for row in root.iter(NS + "row"):
            cells, nxt = {}, 0
            for c in row.iter(NS + "c"):
                ref = c.get("r") or ""
                m = re.match(r"([A-Za-z]+)", ref)
                idx = _col_index(m.group(1)) if m else nxt
                nxt = idx + 1
                t, v = c.get("t"), c.find(NS + "v")
                if t == "s" and v is not None and v.text is not None:
                    val = sst[int(v.text)] if int(v.text) < len(sst) else ""
                elif t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter(NS + "t"))
                else:
                    val = v.text if v is not None and v.text else ""
                cells[idx] = val
            if cells:
                out.append([cells.get(i, "") for i in range(max(cells) + 1)])
        return out


def _write_xlsx(path, rows):
    def cell(r, c, v):
        v = BAD_XML.sub("", str(v))
        return f'<c r="{_col_letters(c)}{r}" t="inlineStr"><is><t xml:space="preserve">{escape(v)}</t></is></c>'
    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><cols>'
             '<col min="1" max="1" width="60" customWidth="1"/><col min="2" max="2" width="80" customWidth="1"/>'
             '</cols><sheetData>' +
             "".join(f'<row r="{r}">' + "".join(cell(r, c, v) for c, v in enumerate(row)) + "</row>"
                     for r, row in enumerate(rows, 1)) + "</sheetData></worksheet>")
    parts = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Answers" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": sheet,
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            z.writestr(name, data)


def _docx_questions(path):
    try:
        with zipfile.ZipFile(path) as z:
            root = ET.fromstring(z.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError):
        raise ValueError(f"{os.path.basename(str(path))} is not a valid .docx file")
    qs = []
    for p in root.iter(W + "p"):
        t = re.sub(r"\s+", " ", "".join(x.text or "" for x in p.iter(W + "t"))).strip()
        if t and (t.endswith("?") or NUMBERED.match(t)) and len(t) > 10:
            qs.append(t)
    return qs


def _load_rows(path):
    ext = _ext(path)
    if ext == ".csv":
        with open(path, newline="", encoding="utf-8-sig") as f:
            return [r for r in csv.reader(f) if r and any(c.strip() for c in r)]
    if ext == ".xlsx":
        return [r for r in _xlsx_rows(path) if any(str(c).strip() for c in r)]
    raise ValueError(f"Unsupported questionnaire type '{ext}'. Use .csv, .xlsx or .docx")


def _save_rows(path, rows):
    if _ext(path) == ".xlsx":
        _write_xlsx(path, rows)
    else:
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows)


def read_questions(path):
    if _ext(path) == ".docx":
        return _docx_questions(path)
    rows = _load_rows(path)
    if not rows:
        return []
    header = [str(c).strip().lower() for c in rows[0]]
    col = 0
    for name in HEADERS:
        if name in header:
            col = header.index(name)
            rows = rows[1:]
            break
    return [str(r[col]).strip() for r in rows if len(r) > col and str(r[col]).strip()]


def write_answers(path, results):
    rows = [["question", "answer", "confidence", "source", "status"]]
    for r in results:
        src = r["citations"][0]["chunk_id"] if r["citations"] else ""
        rows.append([r["question"], r["answer"], r["confidence"], src,
                     "needs_review" if r["needs_review"] else "ok"])
    _save_rows(path, rows)


def finalize(out_csv, final_csv, queue_items):
    """Merge human review decisions into the answered file (.csv or .xlsx)."""
    data = _load_rows(out_csv)
    head = [str(c).strip() for c in data[0]]
    rows = [dict(zip(head, [str(c) for c in r] + [""] * (len(head) - len(r)))) for r in data[1:]]
    final = []
    for r in rows:
        ans, status = r["answer"], "auto" if r["status"] == "ok" else "PENDING REVIEW"
        if r["status"] != "ok":
            for it in reversed(queue_items):
                if it["question"] == r["question"]:
                    if it["status"] == "approved":
                        status = "approved"
                    elif it["status"] == "edited":
                        ans, status = it["final_answer"], "edited"
                    elif it["status"] == "rejected":
                        ans, status = "", "rejected"
                    break
        final.append([r["question"], ans, r["source"], status])
    _save_rows(final_csv, [["question", "answer", "source", "status"]] + final)
    return final
