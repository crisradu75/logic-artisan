# Proposal

Budget: protected

## Why

Every domain repo needs one trusted way to check notes and save them: nothing broken, unschema'd or secret lands on `main`, and nothing captured is lost before it reaches GitHub. The decisions (architecture Q1, Q4, Q9, Q10, Q12–Q14; structure Q3, Q6, Q7, Q8, Q13, Q14 and "Scaffold spec requirements") fix how; this change builds the first piece every later skill and hook calls.

## What Changes

- **BREAKING** Repackage the repo as a plain source repo: the shared files move to `mnemo-plugin/`, whose folder shape mirrors a domain repo's `.claude/`; `.claude-plugin/marketplace.json` and `plugins/mnemo/.claude-plugin/plugin.json` are removed; a root `VERSION` file and `v<semver>` tags carry the release.
- Add the base note schema in `mnemo-plugin/mnemo/conventions/`.
- Add `mnemo-plugin/mnemo/scripts/mnemo_check.py`, one entry point with the subcommands `links`, `schema`, `deletions`, `secrets` and `save`, run on changed files only.
- Add a `unittest` harness at the repo root (`tests/`, plus an empty `evals/` for the later trigger prompts), with a shipped-layout test and a version-equals-tag test.

Not in this change: the Python probe, the hook wiring and its tests (exit codes, timeout tie, settings schema, command-form matcher, `.gitattributes` for `*.sh`, the live cloud block test), the skills, the trigger-test runner, and the stamp-equals-tag test; each lands with the change that adds what it tests (`add-mnemo-setup` for the stamp).

## Capabilities

### New Capabilities

- `note-checks`: the check subcommands, the base schema and the schema-file grammar.
- `note-save`: the `save` subcommand that checks, commits and pushes in one call.
- `mnemo-release`: the shipped folder, the version and tag rules, and the test harness that guards them.

### Modified Capabilities

None.

## Impact

- New: `mnemo-plugin/`, `VERSION`, `tests/`, `evals/`.
- Removed: `.claude-plugin/`, `plugins/`.
- Docs: `CLAUDE.md` (version rule, layout), `README.md` (install and release), `cla.io/project-facts.md` (test command, test locations).
- Every later change (hooks, capture, recall, review, setup, improve) calls `mnemo_check.py` and is shaped by `mnemo-plugin/`.

## Risks noted

- Python 3 in the cloud VM is still unverified; this change only adds the script, and the hook change must confirm it first.
- The YAML subset rejects block scalars and nested maps; a hand-written schema that uses them fails until rewritten.
- Changed-files-only checking misses breakage elsewhere in the repo; whole-repo checking is `mnemo-review`'s job.
- A strict secrets scan may block harmless lines (a masked card number); this costs the owner time, not notes.
- Two locations saving at once can reject a push; the commit stays local and the next save pushes it (see Open questions).

## Open questions

1. **An unpushed commit can be stranded.** Structure Q13 has the Stop hook exit 0 at once when `git status --porcelain` is empty. A commit left unpushed by a failed or killed `save` leaves the tree clean, so no later Stop run pushes it, and a reclaimed cloud VM loses that note. The spec keeps the decision. Proposed fix: the Stop hook also continues when the branch is ahead of its upstream, and `save` with nothing to commit pushes any pending commits (specified in `note-save`).
2. **How a caller names the commit.** The decisions fix capture's message (`capture(<type>): <title>`) but not how it reaches `save`. Recommended: `save --message <text>`, defaulting to `mnemo: save` for the Stop hook. Specified that way.
