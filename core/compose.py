"""Turn a matched evidence sentence into a customer-ready answer, safely."""
import re

YES_NO = {"do", "does", "did", "is", "are", "was", "were", "have", "has", "can", "will", "should", "must"}
NEG = re.compile(r"\b(not|no|never|none|cannot|can't|don't|doesn't|isn't|aren't|won't|haven't|hasn't|prohibited|forbidden|disallowed|banned)\b", re.I)

SCOPE_Q = re.compile(r"\b(any|anyone|anything|all|every|everyone|unrestricted)\b", re.I)
SCOPE_E = re.compile(r"\b(only|limited|restricted|solely|except)\b", re.I)


def strip_headings(text):
    lines = [l.strip() for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    return " ".join(lines) or text.strip()


def is_yes_no(question):
    words = re.findall(r"[a-z']+", question.lower())
    return bool(words) and words[0] in YES_NO


def compose(question, sentence):
    """Return (answer, needs_human). Never says 'Yes' to negated evidence."""
    s = strip_headings(sentence)
    if s and s[-1] not in ".!?":
        s += "."
    if not is_yes_no(question):
        return s, False
    if NEG.search(s.replace("\u2019", "'")):
        return s, True
    if SCOPE_Q.search(question) and SCOPE_E.search(s):
        return s, True
    return "Yes. " + s, False
