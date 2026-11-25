import json
import os

STATUSES = ("new", "quoted", "sent", "won", "lost")


class Projects:
    """Saved projects + simple lead tracking (one JSON file per client)."""

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

    def add(self, name, results, meta, today):
        items = self._load()
        pid = f"P-{len(items) + 1:04d}"
        item = {"id": pid, "name": name, "created": today, "status": "quoted",
                "history": [[today, "quoted"]], "results": results, "meta": meta}
        items.append(item)
        self._save(items)
        return item

    def all(self):
        return self._load()

    def get(self, pid):
        for i in self._load():
            if i["id"] == pid:
                return i
        raise KeyError(f"No project {pid}")

    def set_status(self, pid, status, today):
        if status not in STATUSES:
            raise ValueError("status must be one of: " + ", ".join(STATUSES))
        items = self._load()
        for i in items:
            if i["id"] == pid:
                i["status"] = status
                i["history"].append([today, status])
                self._save(items)
                return i
        raise KeyError(f"No project {pid}")
