import os
import tempfile
import unittest
import zipfile

from modules.cybersecurity.questionnaire import _write_xlsx, finalize, read_questions, write_answers

DOCX = ('<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
        '<w:p><w:r><w:t>Security Questionnaire</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>1. Do you encrypt data at rest</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>Do you require MFA for all staff?</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>Thank you.</w:t></w:r></w:p></w:body></w:document>')
RES = [{"question": "Do you encrypt data?", "answer": "Yes.", "confidence": 0.9, "citations": [{"chunk_id": "p.md#1"}], "needs_review": False},
       {"question": "Pen test frequency?", "answer": "Not found", "confidence": 0.0, "citations": [], "needs_review": True}]


class FormatTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def p(self, n):
        return os.path.join(self.d, n)

    def test_xlsx_roundtrip_and_header(self):
        _write_xlsx(self.p("q.xlsx"), [["Question", "Notes"], ["Do you use SSO?", ""], ["Is data backed up & tested?", "x"]])
        self.assertEqual(read_questions(self.p("q.xlsx")), ["Do you use SSO?", "Is data backed up & tested?"])

    def test_docx_questions(self):
        with zipfile.ZipFile(self.p("q.docx"), "w") as z:
            z.writestr("word/document.xml", DOCX)
        self.assertEqual(read_questions(self.p("q.docx")),
                         ["1. Do you encrypt data at rest", "Do you require MFA for all staff?"])

    def test_csv_still_works(self):
        open(self.p("q.csv"), "w").write("Question\nDo you log access?\n")
        self.assertEqual(read_questions(self.p("q.csv")), ["Do you log access?"])

    def test_answers_and_finalize_xlsx(self):
        write_answers(self.p("out.xlsx"), RES)
        items = [{"question": "Pen test frequency?", "status": "edited", "final_answer": "Yearly."}]
        final = finalize(self.p("out.xlsx"), self.p("fin.xlsx"), items)
        self.assertEqual([f[3] for f in final], ["auto", "edited"])
        self.assertEqual(read_questions(self.p("fin.xlsx")), ["Do you encrypt data?", "Pen test frequency?"])

    def test_bad_inputs_are_clean_errors(self):
        open(self.p("bad.xlsx"), "w").write("not a zip")
        with self.assertRaises(ValueError):
            read_questions(self.p("bad.xlsx"))
        open(self.p("q.pdf"), "w").write("x")
        with self.assertRaises(ValueError):
            read_questions(self.p("q.pdf"))


if __name__ == "__main__":
    unittest.main()
