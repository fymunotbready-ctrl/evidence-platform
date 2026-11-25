import os
import shutil
import subprocess
import tempfile
import unittest

from modules.energy import cli
from modules.energy.bill import extract_bill
from modules.energy.evaluate import evaluate
from modules.energy.pdf import make_pdf
from modules.energy.sizing import InputError, calculate

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BILL = os.path.join(HERE, "samples", "sample_bill.txt")


class HandWorkedExamples(unittest.TestCase):
    """Numbers below were worked out by hand."""

    def test_example_1(self):
        r = calculate({"annual_kwh": 10800, "psh": 5.0, "rate": 0.15})
        self.assertAlmostEqual(r["raw_kw"], 7.39726, places=4)      # 10800 / (5*365*0.8)
        self.assertEqual(r["panels"], 19)
        self.assertAlmostEqual(r["kw_dc"], 7.6)
        self.assertAlmostEqual(r["production_kwh"], 11096.0)        # 7.6 * 1460
        self.assertAlmostEqual(r["system_cost"], 22800.0)           # 7600 W * $3.00
        self.assertAlmostEqual(r["year1_savings"], 1664.4)          # 11096 * 0.15
        self.assertAlmostEqual(r["payback_years"], 22800 / 1664.4, places=6)

    def test_example_2(self):
        r = calculate({"annual_kwh": 12000, "psh": 4.0})
        self.assertEqual(r["panels"], 26)
        self.assertAlmostEqual(r["kw_dc"], 10.4)
        self.assertAlmostEqual(r["production_kwh"], 12147.2)

    def test_battery(self):
        r = calculate({"annual_kwh": 10800, "psh": 5.0, "battery_load_kw": 2, "battery_hours": 10})
        self.assertEqual(r["battery_units"], 2)                     # 20 kWh / 0.9 = 22.2 -> 2 x 13.5
        self.assertAlmostEqual(r["battery_nominal_kwh"], 27.0)
        self.assertAlmostEqual(r["gross_cost"], 22800 + 18000)

    def test_incentive_and_lifetime(self):
        r = calculate({"annual_kwh": 10800, "psh": 5.0, "rate": 0.15, "incentive_pct": 10, "years": 2, "degradation": 0.01})
        self.assertAlmostEqual(r["net_cost"], 22800 * 0.9)
        self.assertAlmostEqual(r["lifetime_savings"], 11096 * 0.15 * (1 + 0.99))

    def test_deterministic(self):
        a = calculate({"annual_kwh": 9000, "psh": 4.2, "rate": 0.2})
        b = calculate({"annual_kwh": 9000, "psh": 4.2, "rate": 0.2})
        self.assertEqual(a, b)


class ValidationTests(unittest.TestCase):
    def test_bad_values_rejected(self):
        for bad in ({"annual_kwh": 0, "psh": 5}, {"annual_kwh": 9000, "psh": 20}, {"annual_kwh": 9000, "psh": 5, "derate": 1.5},
                    {"annual_kwh": 9000, "psh": 5, "panel_w": 10}, {"annual_kwh": 9000, "psh": 5, "offset_pct": 500}):
            with self.assertRaises(InputError):
                calculate(bad)

    def test_missing_required(self):
        with self.assertRaises(InputError):
            calculate({"psh": 5})


class BillTests(unittest.TestCase):
    def test_extract(self):
        b = extract_bill(open(BILL).read())
        self.assertEqual((b["kwh"], b["days"], b["rate"]), (842.0, 30, 0.145))
        self.assertIn("842", b["kwh_line"])

    def test_ambiguous_returns_none(self):
        b = extract_bill("Usage this month: 500 kWh\nUsage last month: 600 kWh\n")
        self.assertIsNone(b["kwh"])
        self.assertEqual(b["candidates"], [500.0, 600.0])

    def test_no_usage(self):
        self.assertIsNone(extract_bill("Amount due: $50.00")["kwh"])


class PdfTests(unittest.TestCase):
    def test_structure_and_text(self):
        data = make_pdf(["SOLAR TEST (parens) \\ back", "line two"] * 40)
        self.assertTrue(data.startswith(b"%PDF-1.4") and data.rstrip().endswith(b"%%EOF"))
        x = int(data.split(b"startxref\n")[1].split(b"\n")[0])
        self.assertEqual(data[x:x + 4], b"xref")
        if shutil.which("pdftotext"):
            with tempfile.TemporaryDirectory() as d:
                p = os.path.join(d, "t.pdf")
                open(p, "wb").write(data)
                out = subprocess.run(["pdftotext", p, "-"], capture_output=True, text=True).stdout
                self.assertIn("SOLAR TEST (parens)", out)


class FlowTests(unittest.TestCase):
    def run_cli(self, d, *args):
        cli.HOME = d
        return cli.main(list(args))

    def test_quote_from_bill_and_leads(self):
        with tempfile.TemporaryDirectory() as d:
            txt, pdf = os.path.join(d, "q.txt"), os.path.join(d, "q.pdf")
            self.assertEqual(self.run_cli(d, "quote", "acme", "Smith house", "--bill-file", BILL, "--state", "AZ",
                                          "--txt", txt, "--pdf", pdf, "--today", "2026-11-01"), 0)
            text = open(txt).read()
            self.assertIn("NOT A BINDING QUOTE", text)
            self.assertIn("one bill", text)
            self.assertIn("low", text)
            self.assertTrue(os.path.getsize(pdf) > 500)
            self.assertEqual(self.run_cli(d, "status", "acme", "P-0001", "won", "--today", "2026-11-05"), 0)
            self.assertEqual(self.run_cli(d, "projects", "acme"), 0)
            self.assertEqual(self.run_cli(d, "show", "acme", "P-0001"), 0)

    def test_errors_are_clean(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self.run_cli(d, "quote", "acme", "x"), 1)                         # no usage
            self.assertEqual(self.run_cli(d, "quote", "acme", "x", "--kwh-year", "9000"), 1)  # no psh/rate
            self.assertEqual(self.run_cli(d, "quote", "acme", "x", "--kwh-year", "9000", "--state", "ZZ"), 1)
            self.assertEqual(self.run_cli(d, "status", "acme", "P-9999", "won"), 1)
            self.assertEqual(self.run_cli(d, "quote", "../bad", "x", "--kwh-year", "9000", "--state", "AZ"), 1)

    def test_same_inputs_same_quote(self):
        with tempfile.TemporaryDirectory() as d:
            for n in ("a.txt", "b.txt"):
                self.run_cli(d, "quote", "acme", "H", "--kwh-year", "10800", "--psh", "5", "--rate", "0.15",
                             "--txt", os.path.join(d, n), "--today", "2026-11-01")
            a = open(os.path.join(d, "a.txt")).read().replace("P-0001", "ID")
            b = open(os.path.join(d, "b.txt")).read().replace("P-0002", "ID")
            self.assertEqual(a, b)


class GoldenTests(unittest.TestCase):
    def test_worked_examples(self):
        res = evaluate()
        self.assertTrue(res["passed"], res["fails"])


if __name__ == "__main__":
    unittest.main()
