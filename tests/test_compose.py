import unittest
from core.compose import compose


class ComposeTests(unittest.TestCase):
    def test_yes_and_heading_removed(self):
        self.assertEqual(
            compose("Do you encrypt data at rest?", "# Policy\nAll customer data is encrypted at rest with AES-256."),
            ("Yes. All customer data is encrypted at rest with AES-256.", False))

    def test_negated_evidence_goes_to_human(self):
        self.assertEqual(compose("Do you encrypt backups?", "Backups are not encrypted."),
                         ("Backups are not encrypted.", True))

    def test_curly_apostrophe_negation(self):
        self.assertTrue(compose("Is MFA required?", "MFA isn\u2019t required for contractors.")[1])

    def test_open_question_no_yes(self):
        self.assertEqual(compose("How often do you run penetration tests?", "We run penetration tests annually"),
                         ("We run penetration tests annually.", False))


if __name__ == "__main__":
    unittest.main()
