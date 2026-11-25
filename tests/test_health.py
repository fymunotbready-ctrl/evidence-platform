import os
import tempfile
import unittest
from datetime import date

from core.ingest import load_dir
from core.retrieve import BM25
from modules.healthcare import cli
from modules.healthcare.appeal import build_case
from modules.healthcare.evaluate import evaluate
from modules.healthcare.parse import InputError, parse_denial, parse_facts

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(HERE, "modules", "healthcare", "golden")
POL = os.path.join(G, "policies")
D01 = os.path.join(G, "denials", "d01.txt")
TODAY = date(2026, 11, 1)


def case(name, facts_file=None):
    idx = BM25(load_dir(POL))
    facts = parse_facts(open(os.path.join(G, "denials", facts_file)).read()) if facts_file else {}
    return build_case(parse_denial(open(os.path.join(G, "denials", name)).read()), facts, idx, TODAY)


class GuardTests(unittest.TestCase):
    def test_refuses_non_synthetic(self):
        with self.assertRaises(InputError):
            parse_denial("Payer: X\nClaim #: 1\nDate of denial: 2026-01-01\nReason code: CO-50\n")

    def test_refuses_ssn(self):
        with self.assertRaises(InputError):
            parse_denial("SYNTHETIC\nPayer: X\nNote: 123-45-6789\n")

    def test_missing_fields_named(self):
        with self.assertRaises(InputError) as cm:
            parse_denial("SYNTHETIC\nPayer: X\n")
        self.assertIn("claim", str(cm.exception))

    def test_bad_date(self):
        with self.assertRaises(InputError):
            parse_denial("SYNTHETIC\nPayer: X\nClaim #: 1\nDate of denial: 10/20/2026\nReason code: CO-50\n")


class LogicTests(unittest.TestCase):
    def test_parse_fields(self):
        c = case("d01.txt")
        self.assertEqual((c["claim"], c["code"], c["procedure_code"]), ("SYN-1001", "CO-50", "72148"))
        self.assertEqual(c["window_days"], 180)

    def test_deadline_math(self):
        c = case("d01.txt")
        self.assertEqual(str(c["deadline"]), "2027-04-18")
        self.assertEqual(c["days_left"], 168)
        self.assertTrue(case("d11.txt", "f_clinical.txt")["deadline_passed"])

    def test_strong_only_with_facts(self):
        self.assertEqual(case("d01.txt")["strength"], "medium")
        self.assertEqual(case("d02.txt", "f_clinical.txt")["strength"], "strong")

    def test_no_policy_means_weak_and_review(self):
        c = case("d10.txt", "f_clinical.txt")
        self.assertIsNone(c["support"])
        self.assertEqual(c["strength"], "weak")
        self.assertTrue(c["needs_review"])
        self.assertIn("[TO ADD: payer policy", c["letter"])

    def test_letter_never_invents_facts(self):
        letter = case("d01.txt")["letter"]
        self.assertIn("[TO ADD: supporting facts", letter)
        self.assertIn("DRAFT", letter)
        self.assertIn("6 weeks of conservative therapy", letter)

    def test_unknown_code_goes_to_review(self):
        c = case("d12.txt")
        self.assertEqual(c["recommendation"], "manual_review")
        self.assertIsNone(c["letter"])


class GoldenTests(unittest.TestCase):
    def test_golden_set(self):
        res = evaluate()
        self.assertEqual(res["unsafe"], 0, res["fails"])
        self.assertEqual(res["invented"], 0, res["fails"])
        self.assertGreaterEqual(res["accuracy"], 0.9, res["fails"])


class CliTests(unittest.TestCase):
    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            cli.HOME = d
            out = os.path.join(d, "letter.txt")
            self.assertEqual(cli.main(["appeal", "acme", POL, D01, "--today", "2026-11-01", "--out", out]), 0)
            self.assertIn("Appeal of claim SYN-1001", open(out).read())
            self.assertEqual(cli.main(["appeal", "acme", POL, os.path.join(G, "denials", "d10.txt"), "--today", "2026-11-01",
                                       "--out", out]), 0)
            self.assertTrue(os.path.exists(os.path.join(d, "acme", "queue.json")))
            self.assertEqual(cli.main(["appeal", "acme", POL, "nofile.txt"]), 1)


if __name__ == "__main__":
    unittest.main()
