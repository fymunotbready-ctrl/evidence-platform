import unittest
from core.compose import compose


class MoreComposeTests(unittest.TestCase):
    def test_prohibited_goes_to_human(self):
        self.assertTrue(compose("Are shared accounts allowed?", "Shared accounts are prohibited.")[1])

    def test_scope_only_goes_to_human(self):
        self.assertTrue(compose("Can AI agents connect to any destination?",
                                "AI agents can only connect to approved destinations.")[1])

    def test_plain_all_still_yes(self):
        self.assertEqual(compose("Do all employees use MFA?", "All employees must use MFA.")[0],
                         "Yes. All employees must use MFA.")


if __name__ == "__main__":
    unittest.main()
