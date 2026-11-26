"""Evidence Engine web API (standard library only).
Run: EP_ADMIN_TOKEN=... python3 -m server.app --port 8080"""
import hashlib, json, os, re, secrets, shutil, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from core.ingest import SUPPORTED
from modules.cybersecurity import memory
from modules.cybersecurity import cli as _cli
from modules.cybersecurity.cli import _engine, _answer_all
from modules.cybersecurity.questionnaire import read_questions, write_answers, finalize as finalize_file

TENANT_RE = re.compile(r"^[a-z0-9-]{1,40}$")
MAX_BODY = 20 * 1024 * 1024
Q_EXT = (".xlsx", ".docx", ".csv")
LOCK = threading.Lock()
LOGLOCK = threading.Lock()


def _allow(srv, key, limit, window=60):
    now = time.monotonic()
    with srv.hits_lock:
        q = [x for x in srv.hits.get(key, []) if now - x < window]
        if len(q) >= limit:
            srv.hits[key] = q
            return False
        q.append(now)
        srv.hits[key] = q
        if len(srv.hits) > 10000:
            srv.hits = {k: v for k, v in srv.hits.items() if v and now - v[-1] < window}
        return True


def _count(srv, key, window=60):
    now = time.monotonic()
    with srv.hits_lock:
        return sum(1 for x in srv.hits.get(key, []) if now - x < window)


def root():
    return os.environ.get("EP_DATA", os.path.join("data", "server"))


def _tokens_path():
    return os.path.join(root(), "tokens.json")


def _load_tokens():
    try:
        with open(_tokens_path(), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def _save_tokens(t):
    os.makedirs(root(), exist_ok=True)
    tmp = _tokens_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(t, f)
    os.replace(tmp, _tokens_path())


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def tenant_dir(tenant, *parts):
    return os.path.join(root(), "tenants", tenant, *parts)


def safe_name(name):
    base = os.path.basename((name or "").replace("\\", "/"))
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base).lstrip(".")
    return base[:100]


def parse_multipart(ctype, body):
    """Binary-safe multipart/form-data parser. Returns [(safe_filename, bytes)]."""
    m = re.search(r'boundary="?([^";]+)"?', ctype or "")
    if not m or not (ctype or "").startswith("multipart/form-data"):
        raise ValueError("Expected a multipart/form-data upload")
    delim = b"--" + m.group(1).encode()
    out = []
    for part in body.split(delim)[1:]:
        if part.startswith(b"--"):
            break
        if part.startswith(b"\r\n"):
            part = part[2:]
        head, sep, data = part.partition(b"\r\n\r\n")
        if not sep:
            continue
        if data.endswith(b"\r\n"):
            data = data[:-2]
        fm = re.search(rb'filename="([^"]*)"', head)
        if fm:
            out.append((safe_name(fm.group(1).decode("utf-8", "replace")), data))
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "EvidenceEngine/0.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, obj=None, raw=None, ctype="application/json"):
        data = raw if raw is not None else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self._log(code, len(data))
        self.end_headers()
        self.wfile.write(data)

    def _ip(self):
        ip = self.client_address[0]
        if os.environ.get("EP_TRUST_PROXY") == "1":
            try:
                hops = max(1, int(os.environ.get("EP_PROXY_HOPS", "2")))
            except ValueError:
                hops = 2
            parts = [x.strip() for x in self.headers.get("X-Forwarded-For", "").split(",")]
            if len(parts) >= hops:
                cand = parts[-hops]
                if re.fullmatch(r"[0-9a-fA-F:.]{3,45}", cand):
                    return cand
        return ip

    def _log(self, code, size):
        try:
            ip = self._ip()
            path = re.sub(r"[^\x21-\x7e]", "?", self.path.split("?")[0])[:200]
            t = self._tenant() or "-"
            line = "%s %s %s %s %s %s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"),
                                              ip, self.command, path, code, t, size)
            os.makedirs(root(), exist_ok=True)
            with LOGLOCK:
                with open(os.path.join(root(), "access.log"), "a") as f:
                    f.write(line)
            if code in (401, 403):
                _allow(self.server, "fail:" + ip, 10 ** 9)
        except Exception:
            pass

    def _limited(self):
        srv = self.server
        ip = self._ip()
        ok = _count(srv, "fail:" + ip) < int(os.environ.get("EP_RATE_FAIL", "20"))
        if ok:
            ok = _allow(srv, "ip:" + ip, int(os.environ.get("EP_RATE_IP", "300")))
        if ok:
            t = self._tenant()
            if t:
                ok = _allow(srv, "t:" + t, int(os.environ.get("EP_RATE_TENANT", "120")))
        if not ok:
            self._send(429, {"error": "Too many requests, slow down"})
            return True
        return False

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise ValueError("Upload too large (max 20 MB)")
        return self.rfile.read(n)

    def _tenant(self):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        return _load_tokens().get(_hash(auth[7:].strip()))

    def do_GET(self):
        if self._limited():
            return
        return self._do_GET()

    def _do_GET(self):
        if self.path == "/api/health":
            return self._send(200, {"ok": True})
        t = self._tenant()
        if not t:
            return self._send(401, {"error": "Missing or invalid token"})
        rv = re.fullmatch(r"/api/runs/([0-9a-f]{32})/review", self.path)
        if rv:
            return self._review_list(t, rv.group(1))
        m = re.fullmatch(r"/api/files/([0-9a-f]{32})/([A-Za-z0-9._-]+)", self.path)
        if m:
            p = tenant_dir(t, "runs", m.group(1), m.group(2))
            if os.path.isfile(p):
                with open(p, "rb") as f:
                    return self._send(200, raw=f.read(), ctype="application/octet-stream")
        return self._send(404, {"error": "Not found"})

    def do_POST(self):
        if self._limited():
            return
        return self._do_POST()

    def _do_POST(self):
        try:
            if self.path == "/api/workspaces":
                return self._create_workspace()
            t = self._tenant()
            if not t:
                return self._send(401, {"error": "Missing or invalid token"})
            if self.path == "/api/policies":
                return self._upload_policies(t)
            fz = re.fullmatch(r"/api/runs/([0-9a-f]{32})/finalize", self.path)
            if fz:
                return self._finalize(t, fz.group(1))
            rv = re.fullmatch(r"/api/review/([0-9a-f]{8})", self.path)
            if rv:
                return self._review_decide(t, rv.group(1))
            if self.path == "/api/questionnaires":
                return self._run(t)
            return self._send(404, {"error": "Not found"})
        except ValueError as e:
            return self._send(400, {"error": str(e)})
        except Exception:
            return self._send(500, {"error": "Internal error"})

    def do_DELETE(self):
        if self._limited():
            return
        return self._do_DELETE()

    def _do_DELETE(self):
        t = self._tenant()
        if not t:
            return self._send(401, {"error": "Missing or invalid token"})
        if self.path != "/api/workspace":
            return self._send(404, {"error": "Not found"})
        _save_tokens({h: n for h, n in _load_tokens().items() if n != t})
        with LOCK:
            shutil.rmtree(tenant_dir(t), ignore_errors=True)
            shutil.rmtree(os.path.join(_cli.HOME, t), ignore_errors=True)
        try:
            os.remove(memory._path(t))
        except FileNotFoundError:
            pass
        return self._send(200, {"deleted": t})

    def _create_workspace(self):
        admin = os.environ.get("EP_ADMIN_TOKEN", "")
        given = self.headers.get("X-Admin-Token", "")
        if not admin or not secrets.compare_digest(admin, given):
            return self._send(403, {"error": "Admin token required"})
        name = json.loads(self._body() or b"{}").get("name", "")
        if not TENANT_RE.match(name):
            raise ValueError("Invalid workspace name (a-z, 0-9, hyphen; max 40)")
        tokens = _load_tokens()
        if name in tokens.values():
            return self._send(409, {"error": "Workspace exists"})
        token = secrets.token_urlsafe(32)
        tokens[_hash(token)] = name
        _save_tokens(tokens)
        os.makedirs(tenant_dir(name, "policies"), exist_ok=True)
        return self._send(201, {"workspace": name, "token": token})

    def _upload_policies(self, t):
        files = parse_multipart(self.headers.get("Content-Type", ""), self._body())
        if not files:
            raise ValueError("No files uploaded")
        d = tenant_dir(t, "policies")
        os.makedirs(d, exist_ok=True)
        for name, _ in files:
            if not name or os.path.splitext(name)[1].lower() not in SUPPORTED:
                raise ValueError(f"Unsupported policy file: {name}")
        for name, data in files:
            with open(os.path.join(d, name), "wb") as f:
                f.write(data)
        return self._send(200, {"saved": [n for n, _ in files]})

    def _review_list(self, t, run_id):
        p = tenant_dir(t, "runs", run_id, "results.json")
        if not os.path.isfile(p):
            return self._send(404, {"error": "Not found"})
        with open(p) as f:
            results = json.load(f)
        state = {i["id"]: i for i in _engine(t).queue.all()}
        out = []
        for r in results:
            rid = r.get("review_id")
            if not r.get("needs_review") or not rid:
                continue
            q = state.get(rid, {})
            out.append({"review_id": rid, "question": r.get("question"),
                        "suggested_answer": r.get("answer"),
                        "confidence": r.get("confidence"),
                        "sources": [c.get("chunk_id") for c in r.get("citations", [])],
                        "status": q.get("status", "pending"),
                        "reviewer": q.get("reviewer"),
                        "final_answer": q.get("final_answer")})
        pending = sum(1 for i in out if i["status"] == "pending")
        return self._send(200, {"run_id": run_id, "items": out, "pending": pending})

    def _review_decide(self, t, item_id):
        try:
            body = json.loads(self._body() or b"{}")
        except ValueError:
            raise ValueError("Body must be JSON")
        if not isinstance(body, dict):
            raise ValueError("Body must be a JSON object")
        status = {"approve": "approved", "reject": "rejected",
                  "edit": "edited"}.get(body.get("decision"))
        if not status:
            raise ValueError("decision must be approve, reject or edit")
        reviewer = str(body.get("reviewer", "")).strip()
        if not reviewer or len(reviewer) > 60:
            raise ValueError("reviewer name required (max 60 characters)")
        text = None
        if status == "edited":
            text = body.get("text")
            if not isinstance(text, str) or not text.strip() or len(text) > 5000:
                raise ValueError("edit needs text (max 5000 characters)")
            text = text.strip()
        eng = _engine(t)
        with LOCK:
            try:
                item = eng.queue.decide(item_id, status, reviewer, text)
            except KeyError:
                return self._send(404, {"error": "Not found"})
            eng.audit.append(reviewer, "review_" + status, {"review_id": item_id})
        return self._send(200, {"review_id": item_id, "status": item["status"],
                                "reviewer": reviewer,
                                "final_answer": item["final_answer"]})

    def _finalize(self, t, run_id):
        rd = tenant_dir(t, "runs", run_id)
        rp = os.path.join(rd, "results.json")
        if not os.path.isfile(rp):
            return self._send(404, {"error": "Not found"})
        with LOCK:
            with open(rp) as f:
                results = json.load(f)
            eng = _engine(t)
            ids = {r.get("review_id") for r in results if r.get("review_id")}
            items = [i for i in eng.queue.all() if i["id"] in ids]
            pending = sum(1 for i in items if i["status"] == "pending")
            if pending:
                return self._send(409, {"error": "Review all flagged items first",
                                        "pending": pending})
            rows = finalize_file(os.path.join(rd, "answers.xlsx"),
                                 os.path.join(rd, "final.xlsx"), items)
            learned = memory.learn(t, rows)
            eng.audit.append("system", "finalize", {"run_id": run_id, "learned": learned})
        return self._send(200, {"run_id": run_id, "questions": len(rows),
                                "learned": learned,
                                "download": f"/api/files/{run_id}/final.xlsx"})

    def _run(self, t):
        files = parse_multipart(self.headers.get("Content-Type", ""), self._body())
        if len(files) != 1:
            raise ValueError("Upload exactly one questionnaire file")
        name, data = files[0]
        ext = os.path.splitext(name)[1].lower()
        if ext not in Q_EXT:
            raise ValueError("Questionnaire must be .xlsx, .docx or .csv")
        pol = tenant_dir(t, "policies")
        policies = sorted(os.listdir(pol)) if os.path.isdir(pol) else []
        if not policies:
            raise ValueError("Upload policy documents first")
        run_id = uuid.uuid4().hex
        rd = tenant_dir(t, "runs", run_id)
        os.makedirs(rd)
        qpath = os.path.join(rd, "input" + ext)
        with open(qpath, "wb") as f:
            f.write(data)
        with LOCK:
            qs = read_questions(qpath)
            if not qs:
                raise ValueError("No questions found in the file")
            eng = _engine(t)
            for p in policies:
                eng.ingest(os.path.join(pol, p))
            results = _answer_all(eng, t, qs)
            write_answers(os.path.join(rd, "answers.xlsx"), results)
        with open(os.path.join(rd, "results.json"), "w") as f:
            json.dump(results, f, default=str)
        review = sum(1 for r in results if r["needs_review"])
        return self._send(200, {"run_id": run_id, "questions": len(results),
                                "answered": len(results) - review, "needs_review": review,
                                "download": f"/api/files/{run_id}/answers.xlsx"})


def serve(port=8080, host="127.0.0.1"):
    srv = ThreadingHTTPServer((host, port), Handler)
    srv.hits = {}
    srv.hits_lock = threading.Lock()
    return srv


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080")))
    ap.add_argument("--host", default="0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")
    a = ap.parse_args()
    if not os.environ.get("EP_ADMIN_TOKEN"):
        raise SystemExit("Set EP_ADMIN_TOKEN first")
    print(f"Evidence Engine API on http://{a.host}:{a.port}")
    serve(a.port, a.host).serve_forever()


if __name__ == "__main__":
    main()
