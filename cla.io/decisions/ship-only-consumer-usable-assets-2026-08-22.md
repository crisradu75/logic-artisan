# Ship only consumer-usable assets in the cla plugin

**Date:** 2026-08-22
**Topic (given):** the plugin should ship only assets a consumer can use — excluding the local
validation machinery we run while developing and validating the plugin here. A consumer repo does
not run tests over the scripts we ship, so tests should not ship.

Extended mid-session by the user: look closely at the conformance guards, which were developed
mainly around retiring the `cla-upstream` sync engine and may not be used by consumer repos.

---

## Grounding — what was checked before the questions

- **`git-subdir` has no exclusion field.** [code.claude.com/docs/en/plugin-marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
  lists exactly `url`, `path`, `ref?`, `sha?`. The whole subtree under `path` ships. The only lever
  is what lives there.
- **70 of 171 tracked plugin files are validation machinery** — `*/tests/`, `*/mutants/`, 12
  `pyproject.toml`, `run_tests.py`, `mutate.py`, the `SOURCE-REPO-ONLY.md` markers, the Node test.
  41% of the payload.
- **`conformance-checks/` is 100% tests** — 5 test files plus `pyproject.toml`, no scripts.
- **Two shipped procedures reach into "dev-only" assets:** `lite-pr/SKILL.md:132` and
  `spec-to-pr/references/revise.md:97` both mandate `python3 ${CLAUDE_PLUGIN_ROOT}/mutate.py`;
  `_shared/references/skill-authoring.md:39` says a conformance test MUST pass.
- **Only two module-name collisions exist across all 12 scopes** — `scripts/aggregate.py` and
  `tests/test_aggregate.py`, both from codify-retro / spec-to-pr-retro. `CLAUDE.md:96` justifies the
  12-scope split with "several scopes ship same-named helper modules"; measured, it is two files.
- **`release` is the only source-repo-only skill.** Swept all 21: it alone names
  `marketplace.json`, `claude plugin tag`, or the `Current release` line.

---

## Decisions

### Q1 — How do we make the published tree lean?
**Chosen: move dev-only assets out of `.claude/plugins/cla/` into a sibling dev tree.** `path` keeps
pointing at the plugin dir, which then contains only shippable assets.
*Rationale:* `git-subdir` has no exclusion field, so what lives under `path` is the only lever — and
a structural move needs no release-time build step or second tree to keep in sync.

### Q2 — Where do the two runners land?
**Chosen: both `run_tests.py` and `mutate.py` move out.** The mutation gate in `lite-pr` step 2b and
`revise.md` step 2b is downgraded to prose.
*Rationale:* asked for a fresh-eyes look at `mutate.py` first. Added 2026-08-09 (`7b6e273`, PR #42),
370 lines plus 328 lines of self-test plus a 152-line pairing guard. It is genuinely used — four runs
in eight days, two finding real weakness (a survivor exposing a vacuous test; a 36-mutant study
leaving 30 alive). But every recorded win audits *this repo's own guards*, and the repo's own
lessons-learned already says "the value was in the planning, not the run", with the causal story that
justified building it refuted by review the same day. Downstream it has a mandate in two skills, no
forcing function (the pairing guard is source-only), no example batch, and no evidence of use.

### Q3 — What happens to the five conformance guards?
**Chosen: promote the two downstream-live guards out of `tests/` into skill scripts; move the other
three to the dev tree.** `conformance-checks/` disappears from the plugin as a pytest scope.

- `test_project_facts_paths.py` → `sync-context/scripts/check_fact_paths.py`
- `test_no_project_tokens.py` → `_shared/scripts/check_no_project_tokens.py`

*Rationale:* the premise held for three of five, not all five. Commit `a9ea9cf` (2026-08-11, "Fix both
conformance guards being silently inert in every consuming repo") records that these two were
deliberately engineered to run from an installed copy against a consuming repo — and, once fixed,
"immediately found a stale path there that had been invisible". Split by **whose data a guard reads**:
two read the consuming repo's, three read the plugin's own. Once that is the criterion, the two stop
being tests and become the skill helpers they were already behaving as — a program with an exit code,
no pytest needed downstream.

### Q4 — What shape does the dev tree take?
**Chosen: collapse to one pytest scope** in `<repo>/plugin-tests/`, after renaming the two colliding
pairs. `run_tests.py` is deleted; the gate becomes bare `pytest`.
*Rationale:* the 12-scope split rests on two colliding files, and once the dev tree never ships,
everything in it is source-repo-only by construction — retiring the three `SOURCE-REPO-ONLY.md`
markers, `test_source_only_markers.py`, and `run_tests.py`'s skip logic along with the runner itself.

### Q5 — What prevents drift back?
**Chosen: a tree scan as a `release` precondition**, not a guard in the test suite.
*Rationale:* fires where the consequence actually lands, at the one deliberate gate the repo already
has. Accepted tradeoff: drift introduced in week one is not detected until the next release.

### Q5b — Where does `release` live? *(inserted by the Q5 revision)*
**Chosen: move it to a repo-local skill at `<repo>/.claude/skills/release/`.** It takes the tree scan
with it.
*Rationale:* `release` edits the repo-root catalog a consumer does not own, edits this repo's
`CLAUDE.md` release line, and cuts `cla--v<version>` tags for this plugin. Its own
`SOURCE-REPO-ONLY.md` claims the skill "remains fully usable" downstream — that claim is false.
Leaving it shipped would put the check against shipping unusable assets inside an unusable asset.

### Q6 — How is the work decomposed?
**Chosen: three changes, every content rewrite before any relocation.**

- **(a) In place, no moves.** Promote the two guards to skill scripts. Rewrite the mutation gate in
  `lite-pr` 2b and `revise.md` 2b as prose. Rename both `aggregate.py`. Update every SKILL.md line
  that names them.
- **(b) Pure relocation.** Everything dev-only moves to `<repo>/plugin-tests/` as one pytest scope.
  `release` moves to `<repo>/.claude/skills/release/`. Delete `run_tests.py`, the three
  `SOURCE-REPO-ONLY.md`, `test_source_only_markers.py` — and fix `release`'s now-dangling
  `run_tests.py` precondition in the same change.
- **(c) Precondition + docs.** Add the tree scan to the relocated `release` skill, then reconcile
  `CLAUDE.md`, the plugin `README.md`, `DEVELOPER-GUIDE.md`, root `.gitattributes`, `TODO.md`.

*Rationale:* each rewrite lands against a file that has not moved, so the diff shows what changed
rather than that it moved. Git renders a rewritten-and-moved file as delete+add, which would make the
highest-risk edits here the least reviewable if bundled with 70 renames.

---

## Decision Summary

| # | Question | Chosen | Rationale |
|---|---|---|---|
| 1 | How to make the published tree lean | Move dev-only assets to a sibling dev tree; `path` keeps pointing at the plugin dir | `git-subdir` has no exclusion field — what lives under `path` is the only lever, and a structural move needs no release-time step |
| 2 | Where the two runners land | Both `run_tests.py` and `mutate.py` move out; the mutation gate in `lite-pr` 2b and `revise.md` 2b becomes prose | Every measured `mutate.py` win was inward-facing — auditing this repo's own guards, not a consumer's product code |
| 3 | The five conformance guards | Promote the two downstream-live guards to skill scripts; move the other three out; `conformance-checks/` disappears from the plugin | Split by whose data a guard reads: two read the consuming repo's, three read the plugin's own |
| 4 | Dev-tree shape | One pytest scope in `<repo>/plugin-tests/`; rename both `aggregate.py`; delete `run_tests.py` | The 12-scope split is justified by exactly two colliding files, and a never-shipped tree makes the source-only skip machinery meaningless |
| 5 | What prevents drift back | A tree scan as a `release` precondition, not a guard in the suite | Fires where the consequence actually lands, at the one deliberate gate the repo already has |
| 5b | Where `release` lives | Move it to a repo-local skill at `<repo>/.claude/skills/release/` | It is the one skill a consumer cannot run; the check against shipping unusable assets shouldn't ride inside one |
| 6 | Decomposition | Three changes — content rewrites (a), then relocation (b), then precondition + docs (c) | Each lands in a diff its own review mode can actually read |

---

## Open, and not decided here

- **The gap between (b) and (c).** The lean tree ships with no ship-check until (c) lands. Q5's chosen
  option accepts release-time-only enforcement, so this is the shape of that choice, not a defect.
- **The version.** Not asked. This changes what consumers receive structurally, so `0.11.0`. `1.0.0`
  still waits on a real end-to-end run in a consuming repo, per `CLAUDE.md`.

## Corrections to carry into change (c)

Both are false claims about what reaches a consuming repo, and both need deleting rather than
rewording:

- Root `.gitattributes` says `hooks/tests/test_hooks_wiring.py` "ships with the plugin, so it also
  fires in a consuming repo." After (b) it definitively does not — and it does not today either,
  since nothing downstream invokes it.
- `CLAUDE.md:93` calls `conformance-checks` "portable core that reaches consuming repos". After (c),
  three of its five guards live in the dev tree and the other two are skill scripts.

## Why this matters, and what's next

The plugin currently publishes 41% of its file count as machinery a consumer cannot invoke, cannot
fix, and is not meant to read — including one skill they cannot run and two false claims about what
reaches them. The fix is structural rather than procedural, so it holds without anyone remembering it
at release time.

**Next step:** change (a) via `/cla:spec-to-pr` (content rewrites, no moves), then (b), then (c).
Each is independently shippable and green on its own.
