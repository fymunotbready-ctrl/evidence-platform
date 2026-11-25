import tempfile, unittest
from modules.cybersecurity import cli, memory


class FakeEngine:
    def __init__(self):
        self.asked = []

    def ask(self, q):
        self.asked.append(q)
        return {"question": q, "answer": "# Policy\nWe encrypt data.", "confidence": 0.9,
                "citations": [{"chunk_id": "p.md#1"}], "needs_review": False}


class RunMemoryTests(unittest.TestCase):
    def setUp(self):
        memory.ROOT = tempfile.mkdtemp()

    def test_clean_answer_drops_headings(self):
        self.assertEqual(cli.clean_answer("# Security Policy\nAll data is encrypted."), "All data is encrypted.")

    def test_clean_answer_keeps_plain_text(self):
        t = "Not found in the provided documents."
        self.assertEqual(cli.clean_answer(t), t)

    def test_memory_hit_skips_engine(self):
        memory.learn("acme", [["How often are penetration tests run?", "Yearly.", "", "edited"]])
        eng = FakeEngine()
        res = cli._answer_all(eng, "acme", ["How often do you run penetration tests?", "Do you encrypt data?"])
        self.assertEqual(res[0]["answer"], "Yearly.")
        self.assertFalse(res[0]["needs_review"])
        self.assertEqual(eng.asked, ["Do you encrypt data?"])
        self.assertEqual(res[1]["answer"], "We encrypt data.")

    def test_weak_match_goes_to_engine(self):
        memory.learn("acme", [["Do you encrypt data at rest?", "Yes.", "", "approved"]])
        eng = FakeEngine()
        cli._answer_all(eng, "acme", ["Do you encrypt data in transit?"])
        self.assertEqual(eng.asked, ["Do you encrypt data in transit?"])


if __name__ == "__main__":
    unittest.main()
