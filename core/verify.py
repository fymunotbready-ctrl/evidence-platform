"""Optional AI check: does this evidence sentence really answer the question?
Off unless EP_LLM_URL is set. Sends only the question and one sentence."""
import json, os, urllib.request

PROMPT = ("You check security questionnaire answers.\n"
          "Question: {q}\nEvidence sentence: {e}\n"
          "Does the evidence sentence directly and fully answer the question, "
          "with no contradiction and no narrower scope? Reply with only YES or NO.")


def configured():
    return bool(os.environ.get("EP_LLM_URL"))


def _http_call(prompt):
    body = json.dumps({"model": os.environ.get("EP_LLM_MODEL", ""),
                       "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": 5, "temperature": 0}).encode()
    req = urllib.request.Request(os.environ["EP_LLM_URL"], data=body, headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + os.environ.get("EP_LLM_KEY", "")})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)["choices"][0]["message"]["content"]


def verify(question, evidence, call=None):
    """True only on a clear YES. Any error counts as NO, so a human reviews it."""
    if call is None:
        if not configured():
            return True
        call = _http_call
    try:
        out = call(PROMPT.format(q=question, e=evidence))
    except Exception:
        return False
    return str(out).strip().upper().startswith("YES")
