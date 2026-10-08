## 1. Rules and skills

- [x] 1.1 Rewrite `rules.specs` in `openspec/config.yaml` and cla-init's block: the REMOVED plus ADDED path, the full-spec rule, consumer-neutral wording; drop the heading-uniqueness rule.
- [x] 1.2 Drop the repeated-heading finding from review-change's checklist and dispatch; cut dispatch check 3, the duplicate checklist sentence, and the fix-routing copies in spec-to-pr and multi-spec's review gate; point multi-spec's brief at the rules.
- [x] 1.3 lite-pr runs `openspec validate <capability> --type spec --strict` on each spec it edits; archive and multi-pr state why whole-tree validation stays non-strict; record the scope under S2.
- [x] 1.4 cla-init lists `+` and `-` lines, removes only earlier wordings of shipped rules, and asks for a yes on that diff; its description says so.
- [x] 1.5 project-review's spec agent grades spec level and plain words.

## 2. Tests

- [x] 2.1 Remove the two heading-uniqueness tests and their mutants; the retired-form scan skips only cla-init's list of earlier wordings.
- [x] 2.2 cla-init seed tests cover the `+`/`-` report and a repo's own lines left unlisted (`requirement: plugin-architecture / cla-init seeds OpenSpec authoring rules without clobbering`); the third-copy guard also catches the scenario and requirement caps.
- [x] 2.3 Both batches killed; parallel and serial suites agree; node suite and `openspec validate --specs` pass. measured: 19 of 19 and 17 of 17 killed; 1780 passed, 12 skipped both ways; 70 node tests pass; 6 of 6 specs valid.
