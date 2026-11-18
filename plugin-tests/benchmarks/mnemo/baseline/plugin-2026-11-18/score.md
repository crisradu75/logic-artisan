# Checklist 4j: the finished plugin on the benchmark (2026-11-18)

The whole plugin, not the authoring brief alone: `/cla:multi-spec` run headless from this repo's
`main` at `1dfa6e54` (after #519), on Sonnet as `./cla` starts it, so Phase 1's spec/lite sort, the
Opus authoring agents and Phase 4's review gate with its fix round all ran. The two folders here
are its output after that review (sandbox commit `3cf9f7f`).

## Setup

- Sandbox: `git -C <mnemo> archive 898ee67`, then the files from `inputs/` at their paths, plus the
  Stakes section the step-3 rounds used (users: the owner only; a bug costs lost or corrupted notes;
  protected area: the owner's notes; `- Change budget: protected`), then `seed_openspec_rules.py`
  on a removed `openspec/config.yaml`. `origin` was a local bare repo, so every push stayed local.
- multi-spec takes one decisions file and copies decision text from it verbatim, so the three files
  were joined, unchanged, under part headings in one file whose Sequencing section names the two
  benchmark scopes (as the author prompts word them). That joined file is a setup artifact; the
  judge noticed version Y citing it.
- Command (cwd the sandbox): `claude -p "/cla:multi-spec cla.io/decisions/<joined file>"
  --plugin-dir <this repo>/.claude/plugins/cla --model sonnet --permission-mode acceptEdits
  --allowedTools Read Write Edit Glob Grep Agent TodoWrite "Bash(git:*)" "Bash(openspec:*)"
  "Bash(python3:*)" "Bash(ls:*)" "Bash(wc:*)" "Bash(mkdir:*)"`. Billed cost reported by the run:
  $9.94. It stopped only at Phase 5 (`gh pr create` was not allowed, and `origin` is not GitHub).
- Run log: both changes `spec`, no `lite` items; `openspec validate --strict` passed on both; the
  review gate found 20 and 17 blocking findings, fixed them, and sent 37 others to `TODO.md`.

## Counts

`find <change> -name '*.md' -exec cat {} + | wc -w` and `grep -c '### Requirement:'`, as in
`brief-v3/protected-list-run.md`:

| | Words | Requirements |
|---|---|---|
| `add-check-scripts` | 5,742 | 25 |
| `add-mnemo-improve` | 5,697 | 24 |
| Total | 11,439 | 49 |

## Blind judge

One Opus agent ran `judge-prompt.md` verbatim (paths filled in, plus a line telling it not to
open the blinding key) on three versions in a random order: this run (Y), brief v3 from
`brief-v3/changes` (Z) and the pre-v3 real CLA run from `changes/` (X). The judge counted words
over all files, so its counts differ slightly from the table above.

| | Rank | Invented (rough) | a | b | c | d | e | f | g | h |
|---|---|---|---|---|---|---|---|---|---|---|
| This run (Y) | 1st | ~25 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Brief v3 (Z) | 2nd | ~15 | ✓ | ½ | ✓ | ✓ | ½ | ✓ | ✗ | ✓ |
| Pre-v3 real run (X) | 3rd | ~50 | ½ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |

X predates decisions Q11-Q14, so its faithfulness score is skewed (as `score.md` notes).

The judge's reasons, in short:
- **Y:** most faithful to the current decisions; strongest protection against losing notes
  (an overlap pre-check instead of `--autostash`, a check of the staged bytes, a secret scan of
  waiting commits, separate exit codes for a secret and for "committed but not pushed"); 21
  open questions, each with a recommendation. Biggest weakness: g, scoring a new test question
  against a base without the fix. About 23 minutes to review per change.
- **Z:** shortest and faithful; weaker on a stash that conflicts on re-apply and on telling a
  secret hit apart from another failure.

## Against the pass rule

- (a) All 8 outcomes: 7 of 8. g is missing, the known gap brief v3 also has (see `README.md`):
  the same status brief v3 shipped under, by the owner's exception.
- (b) Smaller than variant A (12,235 words in `.md` files, 59 requirements): 11,439 and 49. Passes.
- (c) Fewer invented items than variant A (about 35): about 25. Passes.

Compared with brief v3 alone, this run is larger (11,439 against 8,860 words) and ranked above
it under this judge. Brief v3's rounds had no review gate; here the authored changes held 9,784
words and 47 requirements before the review gate's fix commit and 11,439 and 49 after it (the same
counts, run on `git archive` of sandbox commits `ad47ebb` and `3cf9f7f`). One judge run; a close
call would need a re-run with the same prompt.
