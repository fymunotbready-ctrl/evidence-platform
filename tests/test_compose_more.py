import unittest
from core.compose import compose


class MoreComposeTests(unittest.TestCase):
    def test_prohibited_goes_to_human(self):
        self.assertTrue(compose("Are shared accounts allowed?", "Shared accounts are prohibited.")[1])


if __name__ == "__main__":
    unittest.main()
