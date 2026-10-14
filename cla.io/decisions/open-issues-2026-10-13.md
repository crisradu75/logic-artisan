# Open-issue decisions — 2026-10-13

**Topic:** the decisions blocking open issues #295, #319, #322 and #350, found while triaging every open issue against main at ffd1347.

## Questions and choices

1. **What should a test marker prove (S3)?** → Per-requirement by default, per-scenario as an opt-in. Two consuming repos already use per-scenario markers and caught weak tests with them; the #295 checker can serve both.
2. **Should multi-spec's review gate judge the batch as a whole?** → Yes: a batch whose total claim count (`e` in `review-change/references/checklist.md` Step 3) reaches 25 goes to the three-agent review, even when every change grades small. Reuses the single-change threshold.
3. **lite-pr: a retry that fails on a different cause?** → Route it to `/cla:diagnose` like a same-cause failure, then halt if still red. Every unexplained failure gets one bounded root-cause pass.
4. **Code/spec mismatches found while writing specs?** → Fix each in the same PR with a regression test; file an issue only when the fix is blocked outside the repo. Supersedes #319's "owner backlog" proposal.
5. **When does a second review round run?** → On the fix diff whenever round 1 fixed a Critical or Important finding on a high-risk change; low-risk keeps "only after a Critical fix". lite-pr gains this round too, and its "What this skill deliberately does not do" list changes with it. Evidence: on #353, round 2 over Important fixes found four new Important defects.
6. **Switch the `cla` launcher to Sonnet?** → Parked. Stay on Opus; the live escalate-up check is deferred in #322.
7. **Where does a repo turn on per-scenario markers?** → A "Test proof granularity" fact in `cla.io/project-facts.md`, asked by cla-setup; the checker reads it in a strict line format.

## Decision Summary

| # | Question | Choice |
|---|---|---|
| 1 | Marker granularity (S3) | Per-requirement default, per-scenario opt-in |
| 2 | multi-spec batch size | Batch total of 25+ claims → three-agent review |
| 3 | lite-pr retry on a new cause | `/cla:diagnose`, then halt if still red |
| 4 | Code/spec mismatches | Fix in the same PR; file only when blocked outside |
| 5 | Second review round | After any Critical/Important fix on high risk; low risk unchanged |
| 6 | Sonnet launcher | Parked, deferred in #322 |
| 7 | Where the opt-in lives | `cla.io/project-facts.md`, set by cla-setup |
| 8 | Review-change's three large-change reviewers (2026-10-14, #322) | Stay pasted prompts from `dispatch.md`, not fixed agents: repo content fills their placeholders each run, and they run only on Large changes |

Noted, not asked: none.

## Why it matters and what's next

These unblock code work: decisions 1 and 7 feed #295 (the shipped spec checker), 2 and 3 close #350, 4 and 5 are rule changes split out of #319. Next: `/cla:lite-pr` for #350 (decisions 2 and 3) and for decision 5; #295 is large enough for `/cla:spec-to-pr`.
