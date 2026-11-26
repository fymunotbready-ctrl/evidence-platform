# STATE (no secrets). Updated 2026-11-26

## Product
AI agent that fills enterprise security questionnaires from the customer's own policy docs. Every auto-answer has a cited source. Never guesses; unsure goes to human review.

## Invariants
UNSAFE=0; cited source on every auto-answer; synthetic data only until a customer signs (not on Railway Free); tenant isolation and deletion; no secrets in logs, git or screenshots; standard library only; no medical advice.

## Code
~/evidence-platform, branch master, private GitHub repo; every push redeploys Railway.
core/ (ingest, retrieve, answer, compose, verify, review, audit, tenant, pipeline, cli), modules/cybersecurity/, bench/ (6 synthetic policies, 55 cases, run_bench.py, live_bench.py), server/app.py.

## Live
https://evidence-platform-production.up.railway.app (Railway Free, volume /data). Synthetic data only.
Variables: EP_ADMIN_TOKEN, EP_LLM_URL, EP_LLM_KEY, EP_LLM_MODEL, EP_LLM_REASONING, EP_LLM_MAX_TOKENS, EP_TRUST_PROXY=1.
Rate limits per minute: IP 300, tenant 120, fail 20.

## Last verified results
- Tests ~131 pass; golden eval 28/28 (earlier today).
- Local bench, AI on: AUTO-CORRECT 41, GOOD DRAFTS 12, MISSES 2, UNSAFE 0.
- Live bench (2026-11-26 21:21): 55 questions, 26 answered, 29 needs_review. AUTO-CORRECT 26, flagged though answer expected 14, REVIEW-OK 15, PROBLEMS 0. UNSAFE=0.
- Proxy IP fix verified live: 305 requests gave 300x200 and 5x429. Separate buckets for two different IPs NOT verified.

## Open issues
1. Live auto-answers 26 vs 41 locally. Cause not verified.
2. Duplicate empty Railway project; delete only after a screenshot confirms which is real.
3. Paid host needed before any real customer file.
4. Admin token copy lost; recover from Railway Variables.

## Decisions
- Railway Free is OK for synthetic data only.
- Billing and Stripe deferred to v2.
- 80% product / 20% AgentWeir.

## Next
Roadmap v1 step 1 (accuracy), then cleanup, hosting, web UI, trust pages, real-format tests, customer discovery.
