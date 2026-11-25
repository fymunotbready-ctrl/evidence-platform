# Module A: Healthcare Denial Appeal Engine (spec)
Goal: read a denial, find the reason, cite the payer's public policy, draft an appeal, flag weak cases.
Data rule: SYNTHETIC denials and PUBLIC payer policies only until legal agreements (BAA + guardian) exist.
Safety: no medical advice; every claim cites a policy passage or says "not found".
Done when: tests pass on synthetic denials; weak cases land in the review queue.
