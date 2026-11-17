# CLA foundation: size the work to the stakes

**Topic:** the principles a rebuilt CLA rests on, after the mnemo multi-spec run turned 6.6k words
of decisions into about 75k words of plans (230 requirements over 41 capabilities). The principles
are agreed one at a time. Nothing in CLA changes until all are agreed and the benchmark exists.

**Evidence base (2026-11-17 analysis):**
- A blind judge compared three versions of the same two mnemo changes. No guidance: 12.2k words,
  59 requirements, ranked 1st. Lean principles brief: 3.7k words, 22 requirements, ranked 2nd. Real
  CLA run: 20.5k words, 96 requirements, ranked 3rd. Caveat: the real run predates decisions
  Q11-Q14, which skews its faithfulness score.
- Both short versions missed 3 of 7 critical outcomes the real run caught, so rigor has value in
  places.
- Across 44 review findings in 6 repos, 14% were user-visible or data-loss; 70% were low-impact
  hardening.
- Only script-checked limits held; prose size limits failed in every repo.

## Decisions

| # | Principle | Chosen | Rationale |
|---|---|---|---|
| 1 | Per-repo stakes | A few lines in each repo's `cla.io/project-facts.md` under "Stakes": who uses it, what a bug costs, protected areas (money, personal data, the user's own files, anything shipped to others). cla-setup asks the owner for it; a single change can declare higher stakes; every sizing choice reads from it. Amended 2026-11-17: a change raises its budget with a `Budget: protected` line in its proposal, which the checker reads; it can't go above the protected preset. | CLA has no notion of stakes, so every rule applies at the worst case everywhere. Free text, unlike fixed tiers, can name a protected area inside a personal repo. |
| 2 | Skill text | Audit and trim in place: run `/doctor prompt-audit`, then edit the existing files to keep only what Claude can't infer, soften absolute rules into scoped rules with a reason, delete procedure the model already follows, and merge duplicated rules. | Faster and lower risk per edit than a rewrite. Caveat noted: past trims shrank wording but kept every obligation, so the trims are judged on output (principle 7), not on word count. |
| 3 | Hard rules | A rule that must never bend (a data-loss guard, a size budget, a validity check) becomes a hook or script; everything else is guidance. The size check measures a whole change (total words and requirements, budget set by the repo's stakes), not each spec. The seeded rules "add a new capability rather than a ninth" and "never squeeze a clause out" are removed. | Only script-checked limits held, but the per-spec cap pushed mnemo to 41 capabilities. A whole-change budget can't be escaped by splitting. |
| 4 | Spec content | Think broadly, write narrowly: the writer hunts for every risk; only risks touching a protected area become requirements; the rest go in a one-line "Risks noted" list the owner can promote. The writer asks only about gaps the decisions really leave open, citing the decision text it checked. Ships only if the benchmark keeps all 8 critical outcomes. | The real run caught 3 critical outcomes the lean version missed, but buried them under about 40 invented items per change. |
| 5 | Review | One independent reviewer reports everything. A separate filter pass, on a cheaper model with the stakes section as its rubric, keeps only findings that block a merge. Non-blocking findings go to TODO.md, not into code. A second round runs only when a fix touched a protected area. The by-hand mutation check stays only for fixes in protected areas and guard hooks. | 70% of 44 findings across 6 repos were low-impact hardening; Anthropic's docs warn a reviewer always finds something and fixing every finding adds needless layers. |
| 6 | Rule lifecycle | Each rule carries one line: its origin incident and the protected area it covers. A rule with no protected area becomes guidance or is cut. Periodically (or at each benchmark run) rules with no known catch are proposed for removal; the owner approves each removal. No automatic deletion. | Every incident rule was applied everywhere and none was ever removed: the ratchet the past simplifications never broke. |
| 7 | Benchmark | mnemo only: its decision files, the 7 critical outcomes, and the blind-judge rubric (outcomes covered, invented items, review time). A change to spec writing or review ships only if, judged blind, it covers all 8 critical outcomes (a fixed list, not relative to any earlier run) and its output is smaller than the no-guidance version (about 12.2k words, 59 requirements) with fewer invented items. The eighth, an unpushed commit on a clean tree is retried, was confirmed by the owner on 2026-11-17; all three baseline versions miss it. Amended 2026-11-17: "match or beat today's CLA" was too low a bar, since today's CLA ranked last. Lives in `plugin-tests/`, never ships. | Cheapest, and the rubric already exists. Caveat noted: cuts tuned to a personal repo could drop rigor where money or privacy needs it, so protected-area outcomes in the rubric carry that weight. |
| 8 | Paths | Lite is the default (plan, build, one review). The full spec path is for changes that touch a protected area or behaviour that ships to other repos. shape-decision and multi-spec recommend the path per change from the stakes; the owner can override. | lite-pr costs about a third of spec-to-pr; claude-plugins skipped the change folder on 57 of its last 60 merged PRs. |

## Order of work

1. Build the mnemo benchmark in `plugin-tests/` and score today's CLA on it (the baseline).
2. Add the Stakes section to cla-setup and to project-facts; replace the per-spec cap with the
   whole-change budget script.
3. Iterate the spec-writing and review briefs (principles 4 and 5) against the benchmark.
4. Audit and trim the skills in place (principle 2), tagging each kept rule with origin and scope
   (principle 6); each trim must hold the benchmark.
5. Roll out to one repo (mnemo) before the others.

Each step lands as its own reviewed PR. No release without owner approval.
