# Design

Stock triggers: **security** (what the secret scan matches) and **real ambiguity** (how `save` follows structure Q13's order without risking a note).

## Context

`mnemo_check.py` runs inside domain repos, on the owner's notes, from hooks and skills that ship in later changes. Requirements are in `specs/`. This file records only the choices a reviewer must agree on.

## Decisions

### Secret patterns (what counts as a hit)

A hit is any match below, on any line of a checked file, read as UTF-8 with undecodable bytes replaced. No checksum is applied, because "masked or not" (structure Q8) means a partly masked number still blocks. Mask characters are `*`, `x`, `X` and `•`.

- **Private key:** a line containing `-----BEGIN` … `PRIVATE KEY-----` (any key type).
- **API key:** a token starting with a known prefix: `sk-` (Anthropic `sk-ant-`, OpenAI), `ghp_`, `gho_`, `ghs_`, `github_pat_`, `AKIA`/`ASIA` followed by 16 upper-case letters or digits, `AIza`, `xoxb-`/`xoxp-`, `glpat-`, followed by at least 16 key characters.
- **Card number:** 13–19 digits or mask characters, optionally in groups split by single spaces or dashes, holding at least 4 real digits, and not part of a longer run of digits.
- **IBAN:** two capital letters, two digits, then 11–30 letters, digits or mask characters, optionally in groups of four split by single spaces.

Why: these are the four kinds Q8 names; a fixed table can be tested scenario by scenario.
- Rejected: Luhn and mod-97 checks, which would let masked numbers through, against Q8.
- Rejected: an entropy detector, which cannot be pinned by a test and fires on hashes.

The table is switched on only after the false-positive measurement (the owner-run gate in tasks.md); the change does not merge before that gate is recorded. A change to the table after that is a gate change and needs the same measurement.

### Exit statuses

0 pass, 1 note problem, 2 cannot run, 3 secret found, 4 committed but not pushed. When checks report several kinds, the highest-priority status wins: 2, then 3, then 1.
- Why: the guard and capture need "fix and retry, then `inbox/`" (1) apart from "never `inbox/`" (2, 3) without parsing text.
- Rejected: a single non-zero status with a message, which leaves callers parsing prose.

### Save order under Q13

`save` follows Q13: pull, checks, commit, push. The pull is split into a network step and a local step:
0. Without the network: if the tree is clean and the branch is not ahead of its last-fetched upstream (or of `origin/<branch>`; with neither, every local commit waits), exit 0.
1. Refuse an unfinished repo state (see spec).
2. Fetch with a time limit. On failure or timeout, skip to step 4 and remember "not pushed".
3. If the incoming commits touch any uncommitted path, stop with status 2 before changing anything. Otherwise rebase local commits with the uncommitted changes set aside. On any conflict, abort the rebase and restore the set-aside changes, which brings the repo back to its pre-run state, then exit 2.
4. Collect the changed paths once and stage exactly those paths, deletions as removals; never `git add -A`. Run every check on the staged blobs, not the working tree. On any failure, restore the index to its pre-run state.
5. Commit. Scan the lines added by every commit not yet on the remote with `secrets`; a hit pushes nothing. Push the branch to its upstream, else to the same name on `origin`, with a time limit. A failed push exits 4.

Why: the overlap check in step 3 means setting the changes aside can never put conflict markers in a note; checking staged blobs means a write during the run is never committed unchecked.
- Rejected: `pull --rebase --autostash` as is, whose restore step can leave a note in conflict.
- Rejected: commit first, which is ruled out by Q13 and raised in the proposal's Open questions.
- Rejected: every check on waiting commits, which would strand all later pushes on one schema slip made outside `save`; only a secret is permanent once pushed.

### Time limits

Each network step (fetch, push) gives up after 30 seconds, so `save` ends within 90 seconds. Git runs with `GIT_TERMINAL_PROMPT=0` and no credential helper prompt. The hook timeout in the hooks change must exceed 90 seconds and is tied to this constant by that change's test.
- Rejected: one overall timer that kills git mid-rebase, which could leave a half-applied rebase.

A fetch or push stopped at its limit is waited for, then any lock file under `.git/` that did not exist when the run started is removed. Lock files present at the start still block (exit 2) and are never removed.

### No files written by checks

The script is one file and sets `sys.dont_write_bytecode`. A domain repo then never gains a `__pycache__/` that `save` would commit. Any script that imports it must set the flag before the import. The checks run git with `GIT_OPTIONAL_LOCKS=0`, so reading status never rewrites the index.

### Base schema format

`required: [...]` and `optional: [...]` as top-level inline lists; other top-level keys (such as a version key) are not fields.

### Default commit message

`save: <n> files` when no `--message` is given. Capture passes `capture(<type>): <title>` (structure Q9).

## Risks / Trade-offs

- [Strict card pattern blocks long order numbers, PDF cross-reference lines, hash hex and adjacent dates] → the owner-run measurement covers notes, attachments and a stamp file and decides; exemptions are a gate change (proposal Open question 7).
- [Overlap stop repeats on every turn until the owner resolves it] → the notice names the file; the note stays intact.
