import os, sys, json, csv, io, glob, subprocess, zipfile, urllib.request, urllib.error
import xml.etree.ElementTree as ET
sys.path.insert(0, ".")
from bench.cases import CASES, R
BASE = "https://evidence-platform-production.up.railway.app"
AT = os.environ["AT"]; tmp = os.environ["TMPDIR"]

def call(method, path, headers=None, data=None):
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

def up(path, token, f):
    out = subprocess.run(["curl","-s","-m","600","-w","\n%{http_code}","-H","Authorization: Bearer "+token,"-F","file=@"+f,BASE+path],capture_output=True,text=True).stdout
    body, _, code = out.rpartition("\n")
    return int(code or 0), body

def xlsx_rows(b):
    z = zipfile.ZipFile(io.BytesIO(b)); ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(ns+"si"):
            shared.append("".join(t.text or "" for t in si.iter(ns+"t")))
    rows = []
    for n in z.namelist():
        if n.startswith("xl/worksheets/sheet"):
            for row in ET.fromstring(z.read(n)).iter(ns+"row"):
                cells = []
                for c in row.iter(ns+"c"):
                    t = c.get("t"); v = c.find(ns+"v")
                    if t == "s": cells.append(shared[int(v.text)] if v is not None else "")
                    elif t == "inlineStr": cells.append("".join(x.text or "" for x in c.iter(ns+"t")))
                    else: cells.append(v.text if v is not None and v.text else "")
                rows.append(cells)
    return rows

st, body = call("POST", "/api/workspaces", {"X-Admin-Token": AT, "Content-Type": "application/json"}, json.dumps({"name": "benchlive"}).encode())
print("create workspace:", st)
try:
    w = json.loads(body); tok = next(v for k, v in w.items() if "token" in k.lower())
except Exception:
    print("could not read workspace response; keys/body start:", body[:80]); sys.exit(1)
H = {"Authorization": "Bearer " + tok}
try:
    for p in sorted(glob.glob("bench/policies/*.md")):
        print("policy", os.path.basename(p), up("/api/policies", tok, p)[0])
    qf = os.path.join(tmp, "bench_questions.csv")
    with open(qf, "w", newline="") as f:
        wr = csv.writer(f)
        for q, _ in CASES: wr.writerow([q])
    code, resp = up("/api/questionnaires", tok, qf)
    print("questionnaire:", code)
    r = json.loads(resp)
    print("response keys:", sorted(r.keys()))
    print({k: r[k] for k in ("questions", "answered", "needs_review") if k in r})
    run = r.get("run_id") or r.get("run")
    s1, rv = call("GET", "/api/runs/%s/review" % run, H)
    s2, xb = call("GET", "/api/files/%s/answers.xlsx" % run, H)
    print("review:", s1, "answers.xlsx:", s2)
    dump = rv.decode("utf-8", "replace").lower()
    rows = xlsx_rows(xb)
    auto = draft = rev_ok = 0; bad = []
    for q, exp in CASES:
        ql = q.lower(); flagged = ql in dump
        ans = ""
        for cells in rows:
            if any(c.strip().lower() == ql for c in cells):
                ans = " ".join(c for c in cells if c.strip().lower() != ql).lower(); break
        if exp == R:
            if flagged: rev_ok += 1
            else: bad.append("UNSAFE (should be review): " + q)
        elif flagged: draft += 1
        elif all(k in ans for k in exp): auto += 1
        else: bad.append("UNSAFE/MISS (auto, wrong): " + q)
    print("AUTO-CORRECT", auto, "| FLAGGED FOR REVIEW (expected answers)", draft, "| REVIEW-OK", rev_ok, "| PROBLEMS", len(bad))
    for b in bad: print(" ", b[:100])
    print("VERDICT:", "UNSAFE=0 on live" if not bad else "CHECK PROBLEMS ABOVE")
finally:
    print("delete workspace:", call("DELETE", "/api/workspace", H)[0])
