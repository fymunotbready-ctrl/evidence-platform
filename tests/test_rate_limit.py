import json, os, shutil, tempfile, threading, unittest, urllib.error, urllib.request
from modules.cybersecurity import cli, memory

KEYS = ("EP_DATA", "EP_ADMIN_TOKEN", "EP_LLM_URL", "EP_RATE_IP", "EP_RATE_TENANT", "EP_RATE_FAIL")


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.saved = {k: os.environ.get(k) for k in KEYS}
        os.environ["EP_DATA"] = self.tmp
        os.environ["EP_ADMIN_TOKEN"] = "admin-secret"
        os.environ.pop("EP_LLM_URL", None)
        self.old_mem, self.old_home = memory.ROOT, cli.HOME
        memory.ROOT = os.path.join(self.tmp, "memory")
        cli.HOME = os.path.join(self.tmp, "engine")
        os.makedirs(cli.HOME, exist_ok=True)
        from server import app
        self.httpd = app.serve(0)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        memory.ROOT, cli.HOME = self.old_mem, self.old_home
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def req(self, method, path, body=None, headers=None):
        r = urllib.request.Request(self.base + path, data=body, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(r, timeout=30) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def workspace(self):
        code, out = self.req("POST", "/api/workspaces", json.dumps({"name": "rl-test"}).encode(),
                             {"X-Admin-Token": "admin-secret", "Content-Type": "application/json"})
        self.assertEqual(code, 201, out)
        return json.loads(out)["token"]

    def test_ip_limit(self):
        os.environ["EP_RATE_IP"] = "5"
        codes = [self.req("GET", "/api/health")[0] for _ in range(6)]
        self.assertEqual(codes, [200] * 5 + [429])

    def test_tenant_limit(self):
        os.environ["EP_RATE_IP"] = "1000"
        os.environ["EP_RATE_TENANT"] = "3"
        h = {"Authorization": "Bearer " + self.workspace()}
        codes = [self.req("GET", "/api/files/" + "0" * 32 + "/answers.xlsx", headers=h)[0] for _ in range(4)]
        self.assertEqual(codes, [404, 404, 404, 429])

    def test_failed_auth_lockout(self):
        os.environ["EP_RATE_IP"] = "1000"
        os.environ["EP_RATE_FAIL"] = "3"
        h = {"Authorization": "Bearer nope"}
        codes = [self.req("GET", "/api/runs/" + "0" * 32 + "/review", headers=h)[0] for _ in range(4)]
        self.assertEqual(codes, [401, 401, 401, 429])

    def test_log_has_no_secrets(self):
        token = self.workspace()
        self.req("GET", "/api/health?token=SECRETQUERY", headers={"Authorization": "Bearer " + token})
        self.req("GET", "/api/health")
        with open(os.path.join(self.tmp, "access.log")) as f:
            log = f.read()
        self.assertIn("/api/health", log)
        self.assertIn("rl-test", log)
        self.assertNotIn(token, log)
        self.assertNotIn("SECRETQUERY", log)


if __name__ == "__main__":
    unittest.main()
