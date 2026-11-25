import tempfile, unittest
from modules.cybersecurity import memory


class MemoryTests(unittest.TestCase):
    def setUp(self):
        memory.ROOT = tempfile.mkdtemp()

    def test_only_human_verified_rows_are_learned(self):
        n = memory.learn("acme", [
            ["Do you encrypt data?", "Yes.", "p.md#1", "auto"],
            ["Pen test frequency?", "Yearly.", "", "edited"],
            ["Bug bounty?", "", "", "rejected"],
        ])
        self.assertEqual(n, 1)
        self.assertEqual([m["question"] for m in memory.load("acme")], ["Pen test frequency?"])

    def test_paraphrase_hits(self):
        memory.learn("acme", [["How often are penetration tests run?", "Yearly.", "", "approved"]])
        hit = memory.lookup("acme", "How often do you run penetration tests?")
        self.assertEqual(hit["answer"], "Yearly.")

    def test_unrelated_misses(self):
        memory.learn("acme", [["How often are penetration tests run?", "Yearly.", "", "approved"]])
        self.assertIsNone(memory.lookup("acme", "Do you require MFA for all staff?"))

    def test_edit_replaces_old_answer(self):
        memory.learn("acme", [["Pen test frequency?", "Yearly.", "", "approved"]])
        memory.learn("acme", [["Pen test frequency?", "Twice a year.", "", "edited"]])
        self.assertEqual(memory.lookup("acme", "Pen test frequency?")["answer"], "Twice a year.")

    def test_bad_tenant_is_rejected(self):
        with self.assertRaises(ValueError):
            memory.load("CLIENT")


if __name__ == "__main__":
    unittest.main()
