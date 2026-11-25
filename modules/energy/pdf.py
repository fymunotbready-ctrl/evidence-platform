import textwrap


def _esc(s):
    s = s.encode("latin-1", "replace").decode("latin-1")
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(lines, per_page=52, width=84):
    """Tiny dependency-free PDF writer (monospace text pages)."""
    wrapped = []
    for ln in lines:
        wrapped.extend(textwrap.wrap(ln, width, subsequent_indent="    ") or [""])
    pages = [wrapped[i:i + per_page] for i in range(0, len(wrapped), per_page)] or [[]]
    n = len(pages)
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n))
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode(),
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"]
    for i, pg in enumerate(pages):
        stream = "BT /F1 10 Tf 12 TL 50 750 Td\n" + "".join(f"({_esc(l)}) Tj T*\n" for l in pg) + "ET"
        sb = stream.encode("latin-1")
        objs.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {5 + 2 * i} 0 R "
                     "/Resources << /Font << /F1 3 0 R >> >> >>").encode())
        objs.append(b"<< /Length %d >>\nstream\n" % len(sb) + sb + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n")
    offs = []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for o in offs:
        out += f"{o:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n".encode()
    return bytes(out)
