import os

from .answer import answer
from .audit import AuditLog
from .ingest import load_file
from .retrieve import BM25
from .review import ReviewQueue
from .tenant import TenantStore


class Engine:
    """One tenant's engine: ingest documents, answer with citations, queue doubtful cases, log everything."""

    def __init__(self, root, tenant_id, llm=None):
        self.store = TenantStore(root)
        if not self.store.exists(tenant_id):
            self.store.create(tenant_id)
        self.tid = tenant_id
        d = self.store.dir(tenant_id)
        self.docs_dir = os.path.join(d, "docs")
        self.audit = AuditLog(os.path.join(d, "audit.jsonl"))
        self.queue = ReviewQueue(os.path.join(d, "queue.json"))
        self.llm = llm
        self.chunks = []
        self.index = BM25([])

    def ingest(self, path):
        new = load_file(path)
        self.chunks = [c for c in self.chunks if c["source"] != os.path.basename(path)] + new
        self.index = BM25(self.chunks)
        self.audit.append("system", "ingest", {"file": os.path.basename(path), "chunks": len(new)})
        return len(new)

    def ask(self, question, actor="user"):
        res = answer(question, self.index, llm=self.llm)
        if res["needs_review"]:
            res["review_id"] = self.queue.add(res)
        self.audit.append(actor, "ask", {"q": question, "confidence": res["confidence"],
                                         "sources": [c["chunk_id"] for c in res["citations"]],
                                         "needs_review": res["needs_review"]})
        return res
