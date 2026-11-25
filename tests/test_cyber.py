import csv
import os
import tempfile
import unittest
import zipfile
from unittest import mock

from core import ingest
from core.review import ReviewQueue
from modules.cybersecurity import cli
from modules.cybersecurity.evaluate import MIN_ACCURACY, evaluate
from modules.cybersecurity.questionnaire import finalize, read_questions

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD = os.path.join(HERE, "modules", "cybersecurity", "golden", "docs")


class GoldenSetTests(unittest.TestCase):
    def test_zero_unsafe_and_accuracy_floor(self):
        res = evaluate()
        self.assertEqual(res["unsafe"], 0, res["fails"])
        self.assertGreaterEqual(res["accuracy"], MIN_ACCURACY, res["fails"])


class QuestionnaireTests(unittest.TestCase):
    def test_header_detection(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "q.csv")
            open(p, "w").write("id,Question\n1,Is X on?\n2,Is Y on?\n")
            self.assertEqual(read_questions(p), ["Is X on?", "Is Y on?"])
            open(p, "w").write("Is X on?\nIs Y on?\n")
            self.assertEqual(len(read_questions(p)), 2)


class FlowTests(unittest.TestCase):
    def test_run_review_finalize(self):
        with tempfile.TemporaryDirectory() as d:
            cli.HOME = d
            q = os.path.join(d, "q.csv")
            open(q, "w").write("question\nIs customer data encrypted at rest?\nDo you have a bug bounty program?\n")
            out, fin = os.path.join(d, "out.csv"), os.path.join(d, "fin.csv")
            self.assertEqual(cli.main(["run", "acme", GOLD, q, out]), 0)
            self.assertEqual(cli.main(["run", "acme", GOLD, q, out]), 0)  # rerun: no duplicate queue items
            qpath = os.path.join(d, "acme", "queue.json")
            items = ReviewQueue(qpath).pending()
            self.assertEqual(len(items), 1)
            cli.main(["finalize", "acme", out, fin])
            self.assertEqual(list(csv.DictReader(open(fin)))[1]["status"], "PENDING REVIEW")
            cli.main(["edit", "acme", items[0]["id"], "We do not run a bug bounty."])
            cli.main(["finalize", "acme", out, fin])
            rows = list(csv.DictReader(open(fin)))
            self.assertEqual(rows[1]["status"], "edited")
            self.assertEqual(rows[1]["answer"], "We do not run a bug bounty.")
            self.assertEqual(rows[0]["status"], "auto")

    def test_bad_tenant_and_missing_folder(self):
        with tempfile.TemporaryDirectory() as d:
            cli.HOME = d
            self.assertEqual(cli.main(["run", "acme", os.path.join(d, "none"), "q.csv", "o.csv"]), 1)
            self.assertEqual(cli.main(["run", "../bad", GOLD, "q.csv", "o.csv"]), 1)


class IngestFormatTests(unittest.TestCase):
    def test_docx(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.docx")
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("word/document.xml",
                           "<w:document><w:p><w:r><w:t>Backups run daily &amp; are kept.</w:t></w:r></w:p></w:document>")
            ch = ingest.load_file(p)
            self.assertEqual(ch[0]["text"], "Backups run daily & are kept.")

    def test_pdf_missing_tool_message(self):
        with mock.patch("core.ingest.shutil.which", return_value=None):
            with self.assertRaises(RuntimeError) as cm:
                ingest.read_pdf("x.pdf")
            self.assertIn("pkg install poppler", str(cm.exception))


def setUpModule():
    """Keep tests from writing to the real data/memory folder."""
    import tempfile
    from modules.cybersecurity import memory
    memory.ROOT = tempfile.mkdtemp()


if __name__ == "__main__":
    unittest.main()
