import json, os, shutil, tempfile, threading, unittest, urllib.error, urllib.request, uuid
from modules.cybersecurity import cli, memory


def multipart(files):
    b = "XBOUND123"
    out = b""
    for name, data in files:
        out += ('--%s\r\nContent-Disposition: form-data; name="file"; filename="%s"\r\n'
                'Content-Type: application/octet-stream\r\n\r\n' % (b, name)).encode() + data + b"\r\n"
    out += ("--%s--\r\n" % b).encode()
    return out, "multipart/form-data; boundary=" + b


class ReviewApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        os.environ["EP_DATA"] = cls.tmp
        os.environ["EP_ADMIN_TOKEN"] = "admin-secret"
        os.environ.pop("EP_LLM_URL", None)
        cls.old_mem, cls.old_home = memory.ROOT, cli.HOME
        memory.ROOT = os.path.join(cls.tmp, "memory")
        cli.HOME = os.path.join(cls.tmp, "engine")
        os.makedirs(cli.HOME, exist_ok=True)
        from server import app
        cls.httpd = app.serve(0)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        memory.ROOT, cli.HOME = cls.old_mem, cls.old_home
        shutil.rmtree(cls.tmp, ignore_errors=True)

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

    def post_json(self, path, h, obj):
        return self.req("POST", path, json.dumps(obj).encode(), dict(h, **{"Content-Type": "application/json"}))

    def make_run(self):
        h = self.workspace()
        self.upload("/api/policies", h, [("security.md", b"# Policy\nAll customer data is encrypted at rest with AES-256.\n")])
        code, out = self.upload("/api/questionnaires", h, [("q.csv", b"Question\nDo you encrypt data at rest?\nDo you have a bug bounty program?\n")])
        self.assertEqual(code, 200, out)
        return h, json.loads(out)["run_id"]

    def items(self, h, run_id):
        code, out = self.req("GET", f"/api/runs/{run_id}/review", headers=h)
        self.assertEqual(code, 200, out)
        return json.loads(out)

    def test_list_shows_flagged(self):
        h, run = self.make_run()
        res = self.items(h, run)
        self.assertEqual(len(res["items"]), 1)
        self.assertEqual(res["pending"], 1)
        self.assertEqual(res["items"][0]["status"], "pending")
        self.assertIn("bug bounty", res["items"][0]["question"])

    def test_approve(self):
        h, run = self.make_run()
        rid = self.items(h, run)["items"][0]["review_id"]
        code, out = self.post_json(f"/api/review/{rid}", h, {"decision": "approve", "reviewer": "Sam"})
        self.assertEqual(code, 200, out)
        res = self.items(h, run)
        self.assertEqual(res["pending"], 0)
        self.assertEqual(res["items"][0]["status"], "approved")
        self.assertEqual(res["items"][0]["reviewer"], "Sam")

    def test_edit_and_reject(self):
        h, run = self.make_run()
        rid = self.items(h, run)["items"][0]["review_id"]
        code, out = self.post_json(f"/api/review/{rid}", h, {"decision": "edit", "reviewer": "Sam", "text": "No public bug bounty yet."})
        self.assertEqual(code, 200, out)
        self.assertEqual(json.loads(out)["final_answer"], "No public bug bounty yet.")
        code, out = self.post_json(f"/api/review/{rid}", h, {"decision": "reject", "reviewer": "Sam"})
        self.assertEqual(code, 200, out)
        self.assertEqual(self.items(h, run)["items"][0]["status"], "rejected")

    def test_edit_requires_text(self):
        h, run = self.make_run()
        rid = self.items(h, run)["items"][0]["review_id"]
        self.assertEqual(self.post_json(f"/api/review/{rid}", h, {"decision": "edit", "reviewer": "Sam"})[0], 400)

    def test_reviewer_required(self):
        h, run = self.make_run()
        rid = self.items(h, run)["items"][0]["review_id"]
        self.assertEqual(self.post_json(f"/api/review/{rid}", h, {"decision": "approve", "reviewer": " "})[0], 400)

    def test_bad_decision(self):
        h, run = self.make_run()
        rid = self.items(h, run)["items"][0]["review_id"]
        self.assertEqual(self.post_json(f"/api/review/{rid}", h, {"decision": "maybe", "reviewer": "Sam"})[0], 400)

    def test_unknown_item_404(self):
        h, run = self.make_run()
        self.assertEqual(self.post_json("/api/review/deadbeef", h, {"decision": "approve", "reviewer": "Sam"})[0], 404)

    def test_other_workspace_blocked(self):
        h, run = self.make_run()
        rid = self.items(h, run)["items"][0]["review_id"]
        h2 = self.workspace()
        self.assertEqual(self.req("GET", f"/api/runs/{run}/review", headers=h2)[0], 404)
        self.assertEqual(self.post_json(f"/api/review/{rid}", h2, {"decision": "approve", "reviewer": "X"})[0], 404)

    def test_unauthenticated(self):
        self.assertEqual(self.req("GET", "/api/runs/" + "0" * 32 + "/review")[0], 401)
        self.assertEqual(self.req("POST", "/api/review/deadbeef", b"{}")[0], 401)

    def test_audit_logged(self):
        h, run = self.make_run()
        rid = self.items(h, run)["items"][0]["review_id"]
        self.post_json(f"/api/review/{rid}", h, {"decision": "approve", "reviewer": "AuditSam"})
        found = False
        for root, _, names in os.walk(cli.HOME):
            for n in names:
                if n == "audit.jsonl":
                    with open(os.path.join(root, n)) as f:
                        txt = f.read()
                    if "review_approved" in txt and "AuditSam" in txt:
                        found = True
        self.assertTrue(found)


if __name__ == "__main__":
    unittest.main()
