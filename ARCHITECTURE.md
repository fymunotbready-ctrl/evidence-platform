# Architecture
One core, four modules. Core flow: ingest -> BM25 retrieve -> cited answer -> confidence -> review queue -> audit log.
- core/: shared engine (pure Python stdlib, runs anywhere incl. Termux)
- modules/: one folder per field, each with a one-page SPEC.md before code
- tenants/<id>/: per-client docs, signing key, review queue, audit log
Planned upgrades (same interfaces): embeddings + pgvector, FastAPI, Postgres, local models, Stripe, web UI.
## Coding rules
1. No feature is done without tests. 2. Every answer cites a source or says "not found".
3. No secrets in code (environment variables). 4. Fixed accuracy test set, tracked weekly.
5. One-page spec before module code.
