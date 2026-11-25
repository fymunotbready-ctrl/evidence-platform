import math
import re
from collections import Counter

STOP = set("""a an the and or of to in on at by for with from is are was were be been do does did
you your we our it its this that these those how what when where which who whom why often any
can could should would will shall may might have has had as if than then there their they them i""".split())

PHRASES = [
    (r"multi[- ]?factor( authentication)?", "mfa"),
    (r"two[- ]?factor( authentication)?", "mfa"),
    (r"\b2fa\b", "mfa"),
    (r"pen[- ]?test(s|ing)?", "pentest"),
    (r"penetration test(s|ing)?", "pentest"),
    (r"how long", "retention"),
]
WORDS = {
    "encryption": "encrypt", "encrypted": "encrypt", "encrypts": "encrypt", "encrypting": "encrypt",
    "removed": "revoke", "revoked": "revoke", "remove": "revoke", "revoke": "revoke", "removal": "revoke",
    "leaves": "terminate", "leave": "terminate", "left": "terminate", "termination": "terminate",
    "terminated": "terminate", "departs": "terminate", "offboarding": "terminate",
    "retained": "retention", "retain": "retention", "kept": "retention",
    "patched": "patch", "patching": "patch", "scans": "scan", "scanning": "scan",
    "deleted": "delete", "deletion": "delete", "logs": "log", "logging": "log",
    "required": "require", "requires": "require", "requirement": "require", "requirements": "require",
    "admin": "administrative", "administrator": "administrative", "administrators": "administrative",
    "long": "length", "minimum": "least", "performed": "perform", "performs": "perform",
    "mice": "mouse", "murine": "mouse", "tumour": "tumor", "tumours": "tumor",
    "inhibitors": "inhibit", "inhibitor": "inhibit", "inhibition": "inhibit", "inhibited": "inhibit",
    "inhibiting": "inhibit", "inhibits": "inhibit", "expressed": "express", "expression": "express",
    "overexpressed": "express", "binding": "bind", "binds": "bind", "bound": "bind",
    "mutation": "mutat", "mutations": "mutat", "mutant": "mutat", "mutated": "mutat", "mutate": "mutat",
    "reduced": "reduce", "reduction": "reduce", "reduces": "reduce", "stored": "store", "storage": "store",
    "measured": "measure", "measurement": "measure", "administered": "administer",
    "administration": "administer", "evaluated": "evaluate", "evaluation": "evaluate",
    "validated": "validate", "validation": "validate", "dosage": "dose", "dosing": "administer", "dosed": "administer",
}


def _stem(w):
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


def tokenize(text):
    t = text.lower()
    for pat, rep in PHRASES:
        t = re.sub(pat, rep, t)
    out = []
    for w in re.findall(r"[a-z0-9]+", t):
        if w in STOP:
            continue
        out.append(_stem(WORDS.get(w, w)))
    return out


class BM25:
    def __init__(self, chunks, k1=1.5, b=0.75):
        self.chunks, self.k1, self.b = chunks, k1, b
        self.docs = [tokenize(c["text"]) for c in chunks]
        self.n = len(chunks)
        self.avg = (sum(len(d) for d in self.docs) / self.n) if self.n else 0
        self.df = Counter()
        for d in self.docs:
            self.df.update(set(d))
        self.tf = [Counter(d) for d in self.docs]

    def idf(self, t):
        """Rare or unseen words weigh more than generic ones like 'customer' or 'data'."""
        return math.log(1 + (self.n - self.df.get(t, 0) + 0.5) / (self.df.get(t, 0) + 0.5))

    def search(self, query, k=3):
        q = set(tokenize(query))
        scored = []
        for i, tf in enumerate(self.tf):
            dl, s = len(self.docs[i]), 0.0
            for t in q:
                f = tf.get(t, 0)
                if not f:
                    continue
                s += self.idf(t) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / (self.avg or 1)))
            if s > 0:
                scored.append((s, i))
        scored.sort(reverse=True)
        return [(s, self.chunks[i]) for s, i in scored[:k]]
