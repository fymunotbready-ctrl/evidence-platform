# Module B: Cybersecurity (spec)
Goal: auto-answer security questionnaires with cited evidence; later, agent firewall allowlists.
Input: policy docs (.md/.txt/.csv) + questionnaire CSV. Output: cited answers, confidence, review queue.
Core parts used: ingest, retrieve, answer, review, audit, tenant.
Done when: accuracy on fixed test set tracked weekly; 0 unsafe answers; tests pass.
Out of scope now: billing, hosted UI.
