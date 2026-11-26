import json, os, tempfile, threading, unittest, urllib.error, urllib.request, uuid
from modules.cybersecurity import memory
from modules.cybersecurity.questionnaire import _write_xlsx


def multipart(files):
    b = "----ep" + uuid.uuid4().hex
    body = b""
    for name, data in files:
        body += (f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
                 "Content-Type: application/octet-stream\r\n\r\n").encode() + data + b"\r\n"
    body += f"--{b}--\r\n".encode()
    return body, f"multipart/form-data; boundary={b}"


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        os.environ["EP_DATA"] = cls.tmp
        os.environ["EP_ADMIN_TOKEN"] = "admin-secret"
        os.environ.pop("EP_LLM_URL", None)
        memory.ROOT = os.path.join(cls.tmp, "memory")
        from server import app
        cls.httpd = app.serve(0)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        os.environ.pop("EP_DATA", None)
        os.environ.pop("EP_ADMIN_TOKEN", None)

    def req(self, method, path, body=None, headers=None):
        r = urllib.request.Request(self.base + path, data=body, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(r, timeout=30) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def workspace(self):
        name = "t-" + uuid.uuid4().hex[:8]
        code, out = self.req("POST", "/api/workspaces", json.dumps({"name": name}).encode(),
                             {"X-Admin-Token": "admin-secret", "Content-Type": "application/json"})
        self.assertEqual(code, 201, out)
        return {"Authorization": "Bearer " + json.loads(out)["token"]}

    def upload(self, path, h, files):
        body, ct = multipart(files)
        return self.req("POST", path, body, dict(h, **{"Content-Type": ct}))

    def test_health(self):
        self.assertEqual(self.req("GET", "/api/health")[0], 200)

    def test_admin_token_required(self):
        self.assertEqual(self.req("POST", "/api/workspaces", b'{"name": "x"}', {"X-Admin-Token": "wrong"})[0], 403)

    def test_bad_token_rejected(self):
        self.assertEqual(self.req("GET", "/api/files/" + "0" * 32 + "/answers.xlsx",
                                  headers={"Authorization": "Bearer nope"})[0], 401)

    def test_full_run_and_download(self):
        h = self.workspace()
        self.assertEqual(self.upload("/api/policies", h, [("security.md", b"# Policy\nAll customer data is encrypted at rest with AES-256.\n")])[0], 200)
        code, out = self.upload("/api/questionnaires", h, [("q.csv", b"Question\nDo you encrypt data at rest?\nDo you have a bug bounty program?\n")])
        self.assertEqual(code, 200, out)
        res = json.loads(out)
        self.assertEqual((res["questions"], res["answered"], res["needs_review"]), (2, 1, 1))
        code, data = self.req("GET", res["download"], headers=h)
        self.assertEqual(code, 200)
        self.assertTrue(data.startswith(b"PK"))

    def test_real_excel_upload(self):
        h = self.workspace()
        self.upload("/api/policies", h, [("p.md", b"We require MFA for all staff accounts.\n")])
        path = os.path.join(self.tmp, "q.xlsx")
        _write_xlsx(path, [["Question"], ["Do you require MFA for all staff?"]])
        with open(path, "rb") as f:
            code, out = self.upload("/api/questionnaires", h, [("q.xlsx", f.read())])
        self.assertEqual(code, 200, out)
        self.assertEqual(json.loads(out)["questions"], 1)

    def test_other_workspace_cannot_download(self):
        h1, h2 = self.workspace(), self.workspace()
        self.upload("/api/policies", h1, [("p.md", b"All customer data is encrypted at rest with AES-256.\n")])
        res = json.loads(self.upload("/api/questionnaires", h1, [("q.csv", b"Question\nDo you encrypt data at rest?\n")])[1])
        self.assertEqual(self.req("GET", res["download"], headers=h2)[0], 404)

    def test_bad_policy_type_rejected(self):
        h = self.workspace()
        self.assertEqual(self.upload("/api/policies", h, [("evil.exe", b"MZ")])[0], 400)

    def test_delete_workspace(self):
        h = self.workspace()
        self.assertEqual(self.req("DELETE", "/api/workspace", headers=h)[0], 200)
        self.assertEqual(self.req("DELETE", "/api/workspace", headers=h)[0], 401)


if __name__ == "__main__":
    unittest.main()
