import json
import os
import uuid


class ReviewQueue:
    """Low-confidence answers wait here for a human decision."""

    def __init__(self, path):
        self.path = path
        if not os.path.exists(path):
            self._save([])

    def _load(self):
        with open(self.path) as f:
            return json.load(f)

    def _save(self, items):
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(items, f, indent=2)
        os.replace(tmp, self.path)

    def all(self):
        return self._load()

    def add(self, result):
        items = self._load()
        for i in items:  # same pending question+answer is not queued twice
            if i["status"] == "pending" and i["question"] == result["question"] and i["answer"] == result["answer"]:
                return i["id"]
        item = {"id": uuid.uuid4().hex[:8], "status": "pending", "reviewer": None, "final_answer": None, **result}
        items.append(item)
        self._save(items)
        return item["id"]

    def pending(self):
        return [i for i in self._load() if i["status"] == "pending"]

    def decide(self, item_id, status, reviewer, final_answer=None):
        if status not in ("approved", "rejected", "edited"):
            raise ValueError("status must be approved, rejected or edited")
        if status == "edited" and not final_answer:
            raise ValueError("edited needs final_answer")
        items = self._load()
        for i in items:
            if i["id"] == item_id:
                i.update(status=status, reviewer=reviewer, final_answer=final_answer or i["answer"])
                self._save(items)
                return i
        raise KeyError(item_id)
