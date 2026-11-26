"""Optional AI check: does this evidence sentence really answer the question?
Off unless EP_LLM_URL is set. Sends only the question and one sentence."""
import json, os, re, sys, time, urllib.error, urllib.request

PROMPT = ("You check security questionnaire answers.\n"
          "Question: {q}\nEvidence sentence: {e}\n"
          "Does the evidence sentence directly and fully answer the question, "
          "with no contradiction and no narrower scope? Reply with only YES or NO.")


def configured():
    return bool(os.environ.get("EP_LLM_URL"))


def _http_call(prompt):
    payload = {"model": os.environ.get("EP_LLM_MODEL", ""),
               "messages": [{"role": "user", "content": prompt}],
               "max_tokens": int(os.environ.get("EP_LLM_MAX_TOKENS", "400")),
               "temperature": 0}
    if os.environ.get("EP_LLM_REASONING"):
        payload["reasoning_effort"] = os.environ["EP_LLM_REASONING"]
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", "User-Agent": "evidence-platform/0.1",
               "Authorization": "Bearer " + os.environ.get("EP_LLM_KEY", "")}
    for wait in (2, 5, 10, None):
        req = urllib.request.Request(os.environ["EP_LLM_URL"], data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)["choices"][0]["message"].get("content") or ""
        except urllib.error.HTTPError as e:
            if e.code == 429 and wait:
                time.sleep(wait)
                continue
            raise
    return ""


def parse(out):
    """True only if the model's final word is YES."""
    text = re.sub(r"<think>.*?</think>", "", str(out), flags=re.S | re.I).upper()
    found = re.findall(r"\b(YES|NO)\b", text)
    return bool(found) and found[-1] == "YES"


def verify(question, evidence, call=None):
    """True only on a clear YES. Any error counts as NO, so a human reviews it."""
    if call is None:
        if not configured():
            return True
        call = _http_call
    try:
        return parse(call(PROMPT.format(q=question, e=evidence)))
    except Exception as e:
        print('verify failed:', type(e).__name__, getattr(e, 'code', ''), file=sys.stderr, flush=True)
        return False
