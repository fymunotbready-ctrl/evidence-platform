import unittest
from core.verify import parse


class ParseTests(unittest.TestCase):
    def test_thinking_then_yes(self):
        self.assertTrue(parse("<think>maybe no</think>YES"))

    def test_empty_is_no(self):
        self.assertFalse(parse(""))

    def test_last_word_wins(self):
        self.assertFalse(parse("YES... actually NO"))


if __name__ == "__main__":
    unittest.main()
