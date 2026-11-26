import os, shutil, tempfile, threading, unittest, urllib.error, urllib.request
from modules.cybersecurity import cli, memory

KEYS = ("EP_DATA", "EP_ADMIN_TOKEN", "EP_LLM_URL", "EP_RATE_IP", "EP_TRUST_PROXY")


class ProxyIpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.saved = {k: os.environ.get(k) for k in KEYS}
        os.environ["EP_DATA"] = self.tmp
        os.environ["EP_ADMIN_TOKEN"] = "admin-secret"
        os.environ["EP_RATE_IP"] = "2"
        os.environ.pop("EP_LLM_URL", None)
        os.environ.pop("EP_TRUST_PROXY", None)
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

    def health(self, xff):
        r = urllib.request.Request(self.base + "/api/health", headers={"X-Forwarded-For": xff})
        try:
            with urllib.request.urlopen(r, timeout=30) as resp:
                return resp.status
        except urllib.error.HTTPError as e:
            return e.code

    def test_header_ignored_by_default(self):
        codes = [self.health("9.9.9.%d" % i) for i in range(3)]
        self.assertEqual(codes, [200, 200, 429])

    def test_header_used_when_trusted(self):
        os.environ["EP_TRUST_PROXY"] = "1"
        codes = [self.health("9.9.9.1") for _ in range(3)]
        self.assertEqual(codes, [200, 200, 429])
        self.assertEqual(self.health("9.9.9.2"), 200)


if __name__ == "__main__":
    unittest.main()
