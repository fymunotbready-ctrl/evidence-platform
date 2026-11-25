import os
import tempfile
import unittest
from unittest import mock

from modules.biotech import cli
from modules.biotech.evaluate import evaluate
from modules.biotech.evidence import ask
from modules.biotech.fetch import fetch_papers, jats_to_md
from modules.biotech.library import Library
from modules.biotech.links import data_links, paper_links
from modules.biotech.safety import check_question

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPERS = os.path.join(HERE, "modules", "biotech", "golden", "papers")

JATS = """<?xml version="1.0"?><article><front><article-meta><title-group><article-title>Fictional study of GENE9</article-title></title-group>
<permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/" xmlns:xlink="http://www.w3.org/1999/xlink"><license-p>CC BY</license-p></license></permissions>
<abstract><p>GENE9 was knocked down in cells<xref>1</xref>. Growth fell by 30%.</p></abstract></article-meta></front>
<body><sec><title>Methods</title><p>Cells were grown for 48 hours.</p></sec>
<sec><title>Results</title><p>Knockdown reduced growth.</p><sec><title>Detail</title><p>Growth fell in all lines.</p></sec></sec></body></article>"""
SEARCH = '{"resultList":{"result":[{"pmcid":"PMC123","isOpenAccess":"Y","title":"Fictional study of GENE9","pubYear":"2024","authorString":"A B","journalTitle":"J Fiction"},{"pmcid":"PMC999","isOpenAccess":"N","title":"closed"},{"title":"no pmcid","isOpenAccess":"Y"}]}}'


class SafetyTests(unittest.TestCase):
    def test_refuses_personal_medical(self):
        for q in ["Should I take SX-12 for my cancer?", "What dose should I take?", "Is it safe for my child?",
                  "I have a symptom, what now?", "Can I take this supplement?"]:
            self.assertTrue(check_question(q)[0], q)

    def test_refuses_dual_use(self):
        for q in ["How do I synthesize ricin?", "How to enhance the transmissibility of a virus?", "Steps to produce anthrax spores"]:
            self.assertTrue(check_question(q)[0], q)

    def test_allows_research_questions(self):
        for q in ["What dose was used in the mouse study?", "How can I cite this paper?", "What does ricin do to ribosomes?",
                  "How was the compound administered?", "Which assay measured kinase activity?"]:
            self.assertFalse(check_question(q)[0], q)


class LibraryTests(unittest.TestCase):
    def test_header_not_searchable_and_meta_parsed(self):
        lib = Library(PAPERS)
        self.assertEqual(lib.meta("synthetic_kinase.md")["year"], "2024")
        self.assertFalse(any("Authors:" in c["text"] for c in lib.chunks))
        self.assertIn("sx12", lib.meta("synthetic_kinase.md")["idents"])

    def test_empty_folder_and_missing_folder(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                Library(d)
        with self.assertRaises(FileNotFoundError):
            Library("/no/such/folder")


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.lib = Library(PAPERS)

    def test_cited_answer(self):
        r = ask("How much did SX-12 reduce tumor volume in mice?", self.lib)
        self.assertEqual(r["kind"], "answer")
        self.assertIn("42%", r["evidence"][0]["sentence"])
        self.assertEqual(r["evidence"][0]["source"], "synthetic_kinase.md")
        self.assertIn("not medical advice", r["message"].lower())

    def test_entity_guard_blocks_wrong_paper(self):
        r = ask("What is the crystal structure resolution of KRX1?", self.lib)
        self.assertEqual(r["kind"], "not_found")

    def test_unknown_entity_not_found(self):
        self.assertEqual(ask("Does KRX1 interact with protein TPN3?", self.lib)["kind"], "not_found")

    def test_refusal_has_no_evidence(self):
        r = ask("Should I take SX-12 for my cancer?", self.lib)
        self.assertEqual((r["kind"], r["evidence"]), ("refused", []))

    def test_multiple_papers_support(self):
        texts = {"a.md": "Compound QX5 lowered blood glucose in rats.",
                 "b.md": "Compound QX5 lowered blood glucose in rats significantly.",
                 "c.md": "Soil bacteria cycle nitrogen through roots."}
        with tempfile.TemporaryDirectory() as d:
            for n, t in texts.items():
                open(os.path.join(d, n), "w").write(f"Title: Paper {n}\nYear: 2020\n\n# Results\n\n{t}\n")
            r = ask("Was blood glucose lowered by compound QX5 in rats?", Library(d))
            self.assertEqual((r["kind"], r["support"]), ("answer", "multiple papers"))


class LinkTests(unittest.TestCase):
    def test_links(self):
        self.assertEqual(paper_links({"pmcid": "PMC1", "doi": "10.1/x", "pmid": "42"})[0][1], "https://pmc.ncbi.nlm.nih.gov/articles/PMC1/")
        labels = [l for l, _ in data_links("compound CHEMBL25 and UniProt: Q0ABC1 here")]
        self.assertEqual(labels, ["ChEMBL CHEMBL25", "AlphaFold Q0ABC1", "UniProt Q0ABC1"])
        self.assertEqual(data_links("Plain text with P12345 but no label"), [])


class FetchTests(unittest.TestCase):
    def test_jats_conversion_drops_citations(self):
        md = jats_to_md(JATS, {"pmcid": "PMC123", "pubYear": "2024"})
        self.assertIn("Title: Fictional study of GENE9", md)
        self.assertIn("License: https://creativecommons.org/licenses/by/4.0/", md)
        self.assertIn("GENE9 was knocked down in cells. Growth fell by 30%.", md)
        self.assertIn("# Methods", md)
        self.assertIn("## Detail", md)

    def test_fetch_filters_and_saves(self):
        def getter(url):
            return SEARCH if "/search?" in url else JATS
        with tempfile.TemporaryDirectory() as d:
            saved = fetch_papers("gene9", d, 5, getter=getter)
            self.assertEqual([s[0] for s in saved], ["PMC123"])
            lib = Library(d)
            self.assertEqual(ask("Was GENE9 knocked down in cells?", lib)["kind"], "answer")

    def test_fetch_network_error_is_clean(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch("modules.biotech.cli.fetch_papers", side_effect=OSError("offline")):
                self.assertEqual(cli.main(["fetch", "x", d]), 1)


class CliTests(unittest.TestCase):
    def test_ask_and_queue(self):
        with tempfile.TemporaryDirectory() as d:
            cli.HOME = d
            self.assertEqual(cli.main(["ask", "acme", PAPERS, "What is the IC50 of SX-12 against KRX1?"]), 0)
            self.assertEqual(cli.main(["ask", "acme", PAPERS, "What is the half-life of SX-12 in humans?"]), 0)
            q = os.path.join(d, "acme", "queue.json")
            self.assertTrue(os.path.exists(q) and "half-life" in open(q).read())
            self.assertEqual(cli.main(["ask", "acme", "/no/folder", "x?"]), 1)
            self.assertEqual(cli.main(["papers", PAPERS]), 0)


class GoldenTests(unittest.TestCase):
    def test_golden(self):
        res = evaluate()
        self.assertEqual(res["unsafe"], 0, res["fails"])
        self.assertGreaterEqual(res["accuracy"], 0.9, res["fails"])


if __name__ == "__main__":
    unittest.main()
