"""python3 hub.py status  |  python3 hub.py serve (dashboard on http://localhost:8000)"""
import html, os, subprocess, sys, time
from http.server import BaseHTTPRequestHandler, HTTPServer

MODULES = [("Cybersecurity", "cybersecurity"), ("Healthcare", "healthcare"),
           ("Energy", "energy"), ("Biotech", "biotech")]
HOME = os.environ.get("EVIDENCE_HOME", os.path.expanduser("~/.evidence-data"))
_cache = {"t": 0, "rows": []}


def check(mod):
    try:
        r = subprocess.run([sys.executable, "-m", f"modules.{mod}.cli", "eval"], capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip().splitlines()
        passed = any("RESULT: PASS" in l for l in out)
        detail = next((l for l in out if l.lower().startswith(("accuracy", "cases", "worked"))), out[-1] if out else "no output")
        return passed, detail
    except Exception as ex:
        return False, f"{type(ex).__name__}: {ex}"


def status(force=False):
    if force or time.time() - _cache["t"] > 60:
        _cache["rows"] = [(n, *check(m)) for n, m in MODULES]
        _cache["t"] = time.time()
    return _cache["rows"]


def clients():
    out = []
    if os.path.isdir(HOME):
        for c in sorted(os.listdir(HOME)):
            a = os.path.join(HOME, c, "audit.jsonl")
            out.append((c, sum(1 for _ in open(a)) if os.path.exists(a) else 0))
    return out


def page():
    rows = "".join(f"<tr><td>{html.escape(n)}</td><td style='color:{'green' if ok else 'red'}'>{'PASS' if ok else 'FAIL'}</td>"
                   f"<td>{html.escape(d)}</td></tr>" for n, ok, d in status())
    cl = "".join(f"<tr><td>{html.escape(c)}</td><td>{n}</td></tr>" for c, n in clients()) or "<tr><td colspan=2>No clients yet</td></tr>"
    return ("<html><head><meta name=viewport content='width=device-width,initial-scale=1'><title>Evidence Platform</title>"
            "<style>body{font-family:sans-serif;margin:16px}td,th{padding:6px;border-bottom:1px solid #ccc;text-align:left}</style></head>"
            f"<body><h2>Evidence Platform</h2><h3>Modules</h3><table><tr><th>Module</th><th>Status</th><th>Detail</th></tr>{rows}</table>"
            f"<h3>Clients</h3><table><tr><th>Client</th><th>Logged actions</th></tr>{cl}</table></body></html>")


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        b = page().encode()
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        print("Dashboard: http://localhost:8000  (Ctrl+C to stop)")
        HTTPServer(("127.0.0.1", 8000), H).serve_forever()
    else:
        for n, ok, d in status(True):
            print(f"{'PASS' if ok else 'FAIL'}  {n}: {d}")
