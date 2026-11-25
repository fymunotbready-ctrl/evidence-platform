import os
import tempfile
import unittest

from core.answer import NOT_FOUND, answer
from core.audit import AuditLog
from core.ingest import chunk_text, load_file
from core.pipeline import Engine
from core.retrieve import BM25
from core.review import ReviewQueue
from core.tenant import TenantStore

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICY = os.path.join(HERE, "samples", "security_policy.md")


class IngestTests(unittest.TestCase):
    def test_chunks_have_ids_and_source(self):
        ch = chunk_text("One.\n\nTwo.", "f.txt")
        self.assertEqual([c["id"] for c in ch], ["f.txt#1", "f.txt#2"])

    def test_long_paragraph_split(self):
        ch = chunk_text(" ".join(["Sentence number one is here."] * 40), "f.txt", max_chars=200)
        self.assertGreater(len(ch), 1)
        self.assertTrue(all(len(c["text"]) <= 200 for c in ch))

    def test_unsupported_type(self):
        with self.assertRaises(ValueError):
            load_file("x.exe")


class RetrieveAnswerTests(unittest.TestCase):
    def setUp(self):
        self.idx = BM25(load_file(POLICY))

    def test_ranks_relevant_first(self):
        top = self.idx.search("database backups retention", k=1)[0][1]
        self.assertIn("backups", top["text"])

    def test_answer_has_citation(self):
        r = answer("Is customer data encrypted at rest?", self.idx)
        self.assertIn("AES-256", r["answer"])
        self.assertEqual(len(r["citations"]), 1)
        self.assertFalse(r["needs_review"])

    def test_not_found_never_invents(self):
        r = answer("Do you have a bug bounty program?", self.idx)
        self.assertEqual(r["answer"], NOT_FOUND)
        self.assertEqual(r["citations"], [])

    def test_empty_question(self):
        self.assertEqual(answer("the a of", self.idx)["answer"], NOT_FOUND)

    def test_low_confidence_flagged(self):
        r = answer("Do you encrypt backups with rotation schedule?", self.idx, review_below=0.99)
        self.assertTrue(r["needs_review"])

    def test_llm_hook_capped_and_cited(self):
        r = answer("Is customer data encrypted at rest?", self.idx, llm=lambda q, p: "Yes, AES-256.")
        self.assertEqual(r["answer"], "Yes, AES-256.")
        self.assertLessEqual(r["confidence"], 0.9)
        self.assertTrue(r["citations"])


class AuditTests(unittest.TestCase):
    def test_chain_verifies_and_detects_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            log = AuditLog(os.path.join(d, "a.jsonl"))
            for i in range(3):
                log.append("u", "act", {"i": i})
            self.assertEqual(log.verify(), (True, 0))
            p = os.path.join(d, "a.jsonl")
            data = open(p).read().replace('"i": 1', '"i": 9')
            open(p, "w").write(data)
            self.assertEqual(log.verify(), (False, 2))


class TenantTests(unittest.TestCase):
    def test_isolation_and_keys(self):
        with tempfile.TemporaryDirectory() as d:
            s = TenantStore(d)
            s.create("acme")
            s.create("beta")
            sig = s.sign("acme", "hello")
            self.assertTrue(s.verify("acme", "hello", sig))
            self.assertFalse(s.verify("beta", "hello", sig))

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            s = TenantStore(d)
            for bad in ["../x", "a/b", "", "A", "x" * 41]:
                with self.assertRaises(ValueError):
                    s.dir(bad)

    def test_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            s = TenantStore(d)
            s.create("acme")
            with self.assertRaises(ValueError):
                s.create("acme")


class ReviewTests(unittest.TestCase):
    def test_queue_flow(self):
        with tempfile.TemporaryDirectory() as d:
            q = ReviewQueue(os.path.join(d, "q.json"))
            i = q.add({"question": "q", "answer": "a"})
            self.assertEqual(len(q.pending()), 1)
            q.decide(i, "edited", "bob", "better")
            self.assertEqual(q.pending(), [])
            with self.assertRaises(ValueError):
                q.decide(i, "edited", "bob")
            with self.assertRaises(KeyError):
                q.decide("nope", "approved", "bob")


class EngineTests(unittest.TestCase):
    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            e = Engine(d, "acme")
            self.assertGreater(e.ingest(POLICY), 0)
            good = e.ask("How often are backups run?")
            self.assertIn("daily", good["answer"])
            bad = e.ask("Do you have a bug bounty program?")
            self.assertIn("review_id", bad)
            self.assertEqual(len(e.queue.pending()), 1)
            self.assertEqual(e.audit.verify(), (True, 0))

    def test_tenants_do_not_share_data(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Engine(d, "acme"), Engine(d, "beta")
            a.ingest(POLICY)
            self.assertEqual(b.ask("Is customer data encrypted at rest?")["answer"], NOT_FOUND)


if __name__ == "__main__":
    unittest.main()
