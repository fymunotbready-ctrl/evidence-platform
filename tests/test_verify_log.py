import contextlib, io, unittest
from core import verify as v


class VerifyLogTest(unittest.TestCase):
    def test_error_is_logged_without_message_and_fails_safe(self):
        def boom(prompt):
            raise RuntimeError("secret-text")
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            self.assertFalse(v.verify("q", "e", call=boom))
        out = buf.getvalue()
        self.assertIn("RuntimeError", out)
        self.assertNotIn("secret-text", out)


if __name__ == "__main__":
    unittest.main()
