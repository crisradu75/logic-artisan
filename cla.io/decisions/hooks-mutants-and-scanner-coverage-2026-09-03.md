# Hooks mutant adoption and shipped-file scanner coverage — 2026-09-03

Shaped via `/cla:shape-decision`.

**Topic (given):** the two open issues that are recorded decisions rather than build
work — **#207** (does the `hooks` area get mutant batches, or is its absence recorded
as deliberate) and **#190** (should the four unscanned shipped file types be scanned).
#207 says it wants deciding together with **#176** (the seven grandfathered guards in
already-adopted areas), so #176 is in scope as a paired question.

## Grounding, measured 2026-09-03 on `111734e`

Read: `plugin-tests/tests/consistency/test_guards_have_mutant_batches.py`
(`_EXEMPT`, `_PENDING_ADOPTION`, `_PENDING_ADOPTION_CEILING`),
`plugin-tests/tests/conformance/test_shipped_files_are_scanned.py` (`EXEMPT`,
`TOKEN_EXEMPT`), `.claude/plugins/cla/skills/_shared/scripts/check_no_project_tokens.py`
(the suffix rule at line 366), and issues #207 / #190 / #176.
`cla.io/overlays/shape-decision.md` is a neutral stub in this repo.

```
ls plugin-tests/mutants/
  -> annotate  conformance  consistency  release        (no hooks)

ls plugin-tests/tests/hooks/*.py | wc -l
  -> 14                                                 (13 guards + conftest.py)

python plugin-tests/tests/conformance/test_shipped_files_are_scanned.py
  -> shipped 104  reached 99  token-candidates 99  token-reached 94
     (#190 recorded 103/98; one shipped file has been added since)

git ls-files '.claude/plugins/cla/*' | grep -v '\.\(md\|py\|json\|mjs\)$'
  -> .gitattributes  hooks/git/pre-push  hooks/probe-python.sh
```

`check_no_project_tokens.py:366` keys on suffix — `.py` anywhere under the five
`SOURCE_SCAN_ROOTS`, plus `.md` under `agents`/`output-styles`. Adding `.json` there
pulls in exactly three files: `hooks/hooks.json` and both `required-permissions*.json`.
`.claude-plugin/plugin.json` sits outside every scan root and is unaffected.

## Questions and answers

**1. #207 — does `hooks` get adopted as a mutants area?**
Chosen: **adopt it in one commit** — write batches for the high-value guards, list the
rest in `_PENDING_ADOPTION`, raise the ceiling in that same commit.
*Closes the gap the guard file names as already having cost something, and adoption is
the only direction the ceiling is allowed to move.*

**2. How many batches land in the adoption commit, and which?**
Chosen: **six** — the three blocks (`block_cd_in_bash`,
`block_unsafe_recursive_delete`, `block_worktree_path_escape`), plus
`ask_destructive_git`, `pre_push`, and `log_commit_provenance`. Ceiling 3 → 7.
*Covers every guard whose failure lets a destructive or prohibited action through,
which is the line that actually matters.*

**3. #176 pairs with this — what does the adoption commit do about the seven
grandfathered guards?**
Chosen: **keep the two lists separate, but name the next grandfathered target in #176
and write it in the same push.**
*The mechanisms are correctly distinct — `test_guards_have_mutant_batches.py` defends
the lifetime difference at length — and what was actually missing is a documented next
step, which #176 says itself.*

**4. Which grandfathered guard is next?**
Chosen: **`tests/conformance/test_no_hardcoded_plugin_paths.py`.**
*A scanner that checks the wrong thing reports green forever, and this repo has shipped
that exact defect.*

**5. #190 — how far do the token scanners widen?**
Chosen: **`.json` under the scan roots only.** `.sh`, `hooks/git/pre-push`, `.mjs` and
`.gitattributes` stay exempt-with-a-reason.
*Closes the one gap with a real leak surface — `required-permissions.json` already
carries the phrase "for the /spec-to-pr workflow in this repo" in a `_comment` key —
and leaves the rest as a defensible end state rather than a half-finished one.*

**6. Does the #4 pick stand without the shared-work argument?**
Chosen: **yes, unchanged.**
*During shaping I claimed #190 would widen `test_no_hardcoded_plugin_paths.py` — that
was wrong. #190 widens `check_no_project_tokens.py`; the hardcoded-path guard is
separate and already covers `.json`. The two pieces of work share nothing. The pick
stands on its silent-failure argument, which was always the real one.*

**7. How does it land?**
Chosen: **three PRs, in order C → A → B.**
*Each closes or advances exactly one issue, and the ceiling raise gets the isolated
review the guard file asks for.*

## Decision Summary

| # | Question | Chosen | Rationale |
|---|---|---|---|
| 1 | #207 — adopt `hooks` as a mutants area? | Adopt in one commit: batches for the high-value guards, rest in `_PENDING_ADOPTION`, ceiling raised there | Closes the gap the guard file names as already having cost something; adoption is the only direction the ceiling may move |
| 2 | Which batches land in that commit? | Six: 3 blocks + `ask_destructive_git` + `pre_push` + `log_commit_provenance`; ceiling 3 → 7 | Covers every guard whose failure lets a destructive or prohibited action through |
| 3 | What happens to #176's seven grandfathered guards? | Keep the two lists separate; name the next target in #176 and write it in the same push | The mechanisms are correctly distinct; what was missing is a documented next step |
| 4 | Which grandfathered guard is next? | `tests/conformance/test_no_hardcoded_plugin_paths.py` | Highest silent-failure risk of the seven — a vacuous scanner reports green forever |
| 5 | #190 — how far do the token scanners widen? | `.json` under the scan roots; `.sh`, `pre-push`, `.mjs`, `.gitattributes` stay exempt-with-a-reason | Closes the one gap with a real leak surface; the rest is a defensible end state, not a half-finished one |
| 6 | Does #4 stand without the shared-work argument? | Yes — pick unchanged | The silent-failure argument was always the real one; the claimed overlap was wrong |
| 7 | How does it land? | Three PRs, in order C (#190 widening) → A (hooks adoption) → B (grandfathered batch) | Each closes or advances one issue; the ceiling raise gets the isolated review the guard file asks for |

## The three pieces

**C — widen the token scanners to `.json`** (closes #190)
One suffix change at `check_no_project_tokens.py:366`. Delete the three `.json` entries
from `TOKEN_EXEMPT` in `test_shipped_files_are_scanned.py`; that guard fails on a stale
exemption, so it reports whether the widening actually took. Re-run
`python plugin-tests/tests/conformance/test_shipped_files_are_scanned.py` and expect
`token-reached` to rise by 3.

**A — adopt `hooks` as a mutants area** (closes #207)
Create `plugin-tests/mutants/hooks/` with six batches. List the remaining seven guards
in `_PENDING_ADOPTION` with a reason each, and raise `_PENDING_ADOPTION_CEILING` from 3
to 7 **in the same commit** — the only place that number is allowed to move up.

**B — batch for `test_no_hardcoded_plugin_paths.py`** (advances #176)
Write the batch, delete its `_EXEMPT` line, and lower the bound in
`test_the_grandfather_list_only_shrinks` in the same commit. #176 records that leaving
the bound above its real population silently permitted four new exemptions.

Net: adoption debt 0 → 7, grandfathered 7 → 6, `TOKEN_EXEMPT` loses 3 entries.

## Why this matters, and the next step

Both issues were open because the cost of closing them was never priced, not because
the answer was hard. #207 in particular was a mechanism discouraging the behaviour it
exists to encourage — writing one hook batch demanded thirteen, so the affordable move
was to write none, and the batch proving `ask-destructive-git` catches `git branch -D`
ended up existing nowhere. `_PENDING_ADOPTION` was built to unblock exactly this, and
has been unused since.

**Next:** C is small and self-contained — `/cla:lite-pr`. A is the substantial one and
wants `/cla:spec-to-pr`. B follows A.

**One operational constraint, from CLAUDE.md:** `mutate.py` rewrites real files in place
and restores them, so no batch may run while a review agent reads the same tree. A and B
each need their own window; this is a reason not to merge them into one PR.
