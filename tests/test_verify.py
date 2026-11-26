import os, unittest
from core.verify import verify


class VerifyTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("EP_LLM_URL", None)

    def test_off_by_default(self):
        self.assertTrue(verify("Q?", "E."))

    def test_yes_passes(self):
        self.assertTrue(verify("Q?", "E.", call=lambda p: " yes"))

    def test_no_fails(self):
        self.assertFalse(verify("Q?", "E.", call=lambda p: "NO"))

    def test_error_fails_safe(self):
        def boom(p):
            raise OSError("network down")
        self.assertFalse(verify("Q?", "E.", call=boom))

    def test_prompt_contains_question_and_evidence(self):
        seen = []
        verify("Are incidents documented?", "We have a plan.", call=lambda p: seen.append(p) or "NO")
        self.assertIn("Are incidents documented?", seen[0])
        self.assertIn("We have a plan.", seen[0])


if __name__ == "__main__":
    unittest.main()
