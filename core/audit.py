import hashlib
import json
import os
import time


def _h(rec):
    return hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()


class AuditLog:
    """Append-only JSONL log; each entry hashes the previous one (tamper-evident)."""

    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if not os.path.exists(path):
            open(path, "w").close()

    def _last_hash(self):
        last = "GENESIS"
        with open(self.path) as f:
            for line in f:
                if line.strip():
                    last = json.loads(line)["hash"]
        return last

    def append(self, actor, action, detail=None):
        rec = {"ts": time.time(), "actor": actor, "action": action, "detail": detail or {}, "prev": self._last_hash()}
        rec["hash"] = _h(rec)
        with open(self.path, "a") as f:
            f.write(json.dumps(rec) + "\n")
        return rec

    def verify(self):
        prev = "GENESIS"
        with open(self.path) as f:
            for n, line in enumerate(f, 1):
                if not line.strip():
                    continue
                rec = json.loads(line)
                h = rec.pop("hash")
                if rec["prev"] != prev or _h(rec) != h:
                    return False, n
                prev = h
        return True, 0
