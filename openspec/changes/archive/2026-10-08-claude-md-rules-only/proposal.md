## Why

`CLAUDE.md` loads into every session in this repo, and about three quarters of its 4,494 words were
rationale, reference tables (the script table, the layout trees) or copies of the plugin README and
DEVELOPER-GUIDE. This is P6 of the 2026-10-08 plugin-surface simplification.

## What Changes

- `CLAUDE.md` holds only the rules a session here acts on, in plain words: what the repo is, the
  launcher, the push-guard install, the release rules and the "Current release" line, the gate
  commands and the parallel-gate rules, where things go, the five checks with the mutation caveats
  and the "match the checking" table, and the no-CI rules.
- The script table and the layout trees move to DEVELOPER-GUIDE §11, updated on the way: a row for
  `plugin-tests/scripts/migrate_run_records.py`, the tree lists it, and the stale "6 skills with
  tests" and "configured by 1 of 4" facts are corrected.
- Rationale and the full wording of each compressed rule move to DEVELOPER-GUIDE §12, under headings
  naming the rule. The distribution details and the 0.x versioning history move to "Release and
  distribution history".
- Copies of the plugin README are deleted: skills by phase, typical flows, the guard-hook summary,
  portability, the `cla.io/` inventory, the recap pointer.
- `test_docs_name_shipped_paths.py` still checks every plugin path `CLAUDE.md` names, but no longer
  floors its path count or requires a tree diagram there; DEVELOPER-GUIDE's new diagram is floored
  instead. The release line and the "Before opening a PR" row stay, so the release tests keep their
  subject.

No behaviour changes, so there is no spec delta (`skip_specs`).

**Rules dropped (CLAUDE.md check 2).** None the model acts on. Moved, not dropped: every compressed
rule's full wording and its evidence (§12); the guard-placement detail, scanner reach, Playwright
install, platform-divergence detail and `TODO.md` history (§11); distribution and version history.
Deleted as copies or trivia: the README copies above; the `pytest -k` filter example; the
`pip install pytest-xdist` line (root README has it); the arc of life-cycle phases.
