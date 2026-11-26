import unittest
from core import verify as v

class T(unittest.TestCase):
    def setUp(self):
        v.reset_stats()
    def test_counts(self):
        self.assertTrue(v.verify("q", "e", call=lambda p: "YES"))
        self.assertFalse(v.verify("q", "e", call=lambda p: "NO"))
        self.assertFalse(v.verify("q", "e", call=lambda p: ""))
        def boom(p):
            raise OSError("x")
        self.assertFalse(v.verify("q", "e", call=boom))
        s = v.snapshot()
        self.assertEqual((s["yes"], s["model_said_no"], s["empty_reply"], s["OSError:"]), (1, 1, 1, 1))

if __name__ == "__main__":
    unittest.main()
