import hashlib
import hmac
import os
import re
import secrets

_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")


class TenantStore:
    """Each tenant gets its own folder and its own random signing key."""

    def __init__(self, root):
        self.root = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)

    def _check(self, tid):
        if not isinstance(tid, str) or not _ID.match(tid):
            raise ValueError("Invalid tenant id (use a-z, 0-9, hyphen; max 40 chars)")

    def dir(self, tid):
        self._check(tid)
        return os.path.join(self.root, tid)

    def create(self, tid):
        d = self.dir(tid)
        if os.path.exists(d):
            raise ValueError(f"Tenant exists: {tid}")
        os.makedirs(os.path.join(d, "docs"))
        kp = os.path.join(d, "key")
        fd = os.open(kp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_hex(32))
        return d

    def exists(self, tid):
        return os.path.isdir(self.dir(tid))

    def _key(self, tid):
        with open(os.path.join(self.dir(tid), "key")) as f:
            return bytes.fromhex(f.read().strip())

    def sign(self, tid, data):
        return hmac.new(self._key(tid), data.encode(), hashlib.sha256).hexdigest()

    def verify(self, tid, data, sig):
        return hmac.compare_digest(self.sign(tid, data), sig)
