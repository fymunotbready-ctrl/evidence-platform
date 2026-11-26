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


class DeleteApiTests(unittest.TestCase):
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
        cls.app = app
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
        return name, {"Authorization": "Bearer " + json.loads(out)["token"]}

    def upload(self, path, h, files):
        body, ct = multipart(files)
        return self.req("POST", path, body, dict(h, **{"Content-Type": ct}))

    def post_json(self, path, h, obj):
        return self.req("POST", path, json.dumps(obj).encode(), dict(h, **{"Content-Type": "application/json"}))

    def make_run(self):
        name, h = self.workspace()
        self.upload("/api/policies", h, [("security.md", b"# Policy\nAll customer data is encrypted at rest with AES-256.\n")])
        code, out = self.upload("/api/questionnaires", h, [("q.csv", b"Question\nDo you encrypt data at rest?\nDo you have a bug bounty program?\n")])
        self.assertEqual(code, 200, out)
        return name, h, json.loads(out)["run_id"]

    def test_delete_wipes_everything(self):
        t, h, run = self.make_run()
        code, out = self.req("GET", f"/api/runs/{run}/review", headers=h)
        rid = json.loads(out)["items"][0]["review_id"]
        self.post_json(f"/api/review/{rid}", h, {"decision": "edit", "reviewer": "Sam", "text": "No public bug bounty yet."})
        self.assertEqual(self.post_json(f"/api/runs/{run}/finalize", h, {})[0], 200)
        self.assertTrue(os.path.isdir(os.path.join(cli.HOME, t)))
        self.assertTrue(os.path.isfile(memory._path(t)))
        self.assertTrue(os.path.isdir(self.app.tenant_dir(t)))
        self.assertEqual(self.req("DELETE", "/api/workspace", headers=h)[0], 200)
        self.assertFalse(os.path.exists(os.path.join(cli.HOME, t)))
        self.assertFalse(os.path.exists(memory._path(t)))
        self.assertFalse(os.path.exists(self.app.tenant_dir(t)))
        self.assertEqual(self.req("GET", f"/api/runs/{run}/review", headers=h)[0], 401)

    def test_other_workspace_untouched(self):
        t1, h1, run1 = self.make_run()
        t2, h2, run2 = self.make_run()
        self.assertEqual(self.req("DELETE", "/api/workspace", headers=h1)[0], 200)
        self.assertTrue(os.path.isdir(os.path.join(cli.HOME, t2)))
        self.assertEqual(self.req("GET", f"/api/runs/{run2}/review", headers=h2)[0], 200)


if __name__ == "__main__":
    unittest.main()
