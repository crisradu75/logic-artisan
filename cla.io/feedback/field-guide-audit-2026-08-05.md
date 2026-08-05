# CLA conformance audit — *The Claude Code Field Guide*

Triage of the CLA harness against Ovidiu Eftimie's *The Claude Code Field Guide* (2026 edition,
verified by its author against Claude Code 2.1.220). Systematic pass over all 34 chapters and 5
appendices.

**This is triage, not decisions.** Findings are grouped by severity with a suggested direction each;
nothing here has been shaped or scheduled. Hand off to `/cla:shape-decision` for the ones worth
acting on.

**Basis:** every claim about CLA was read from the working tree (18 skills, 13 hook scripts, 2
agents, plugin manifest, launcher scripts, settings) via four parallel read-only audits — not
inferred from CLAUDE.md. Guide citations are by chapter.

**Tally:** 6 areas ahead of the guide · 3 verified defects · 8 practice gaps · 12 not applicable.

---

## A. Where CLA already exceeds the guide

Recorded first because it changes what the gaps mean: on several axes CLA has solved problems the
guide only names.

### A1. The exit-2 stderr contract is honored everywhere — Ch 10, A3

The guide calls writing a block reason to stdout its single most common hook mistake: on exit 2
Claude Code discards stdout and reads stderr, so the tool is blocked with no explanation and Claude
retries the same call. All six of CLA's blocking paths write to stderr.

`dispatch-edit-write-pretooluse.py` goes beyond what the guide describes — it re-emits an earlier
hook's stdout `additionalContext` onto stderr before blocking, so a non-blocking warning is not
silently lost to the exit-2 discard.

### A2. Sub-agent output is distrusted by construction — Ch 12

Ch 12 warns that "an agent that reports success has reported its own opinion of its work."
`spec-to-pr` answers at three levels:

- **Evidence-based terminal contract** — a `done` without a test-run summary line and a ticked-task
  count is treated as not done.
- **Deterministic post-check** — task boxes are recounted *regardless of what the agent reported*.
- **INT-CAP / INT-SYC** — a finding counts as applied only when a re-read shows the defect gone;
  "the delegate fixed it" is not accepted without the confirming read.

It also distrusts its own orchestration layer, requiring the workflow journal over the summary
because a summary was once observed misreporting a retried agent as failed.

### A3. The unattended error contract, in `multi-lite` — Ch 20

Ch 20 asks four things of an unattended run: degrade and say so, log failures with context, never
fail silently, report status in the output. `multi-lite` satisfies all four, and its
dependency-subtree quarantine is more precise than the guide's own example — a failed candidate
blocks only its transitive downstream while independents continue, with both task state and the
run-notes ledger recording which upstream blocked what. The final report enumerates shipped,
left-open, failed, blocked-by-upstream, and out-of-scope.

### A4. Agent cost routing already applied — Ch 12

Ch 12 calls model routing "a live cost lever most people leave on the table." Both CLA agents are
`model: haiku` with a `tools: [Read, Grep, Glob]` allowlist — mechanically read-only (no write path
exists in the granted set) and running mechanical grep work off the expensive model.

### A5. Hook wiring hygiene is clean on every mechanical axis — Ch 10, A3

- All six handlers reference `${CLAUDE_PLUGIN_ROOT}`; no relative or absolute paths.
- No matcher contains a character outside the literal-safe set, so none is silently reinterpreted as
  an unanchored regex.
- No hook attempts enforcement on an event that cannot block — the `SessionStart` / `SessionEnd` and
  `PostToolUse` handlers all return 0 unconditionally and deliver via `additionalContext`.
- There is a `python3` / `py` / `python` resolution preamble with a stderr-warning fallback, which
  the guide never contemplates.

### A6. Auto mode's most surprising allowance is already compensated — Ch 25

The launcher runs `--permission-mode auto`. Ch 25 lists "pushing to any branch of the repository
you're working in" among auto mode's *allowed* actions — the default branch is not treated as
special, which the guide flags as the item that surprises people. `block-direct-push-to-main.py`
closes exactly that hole, and because a `PreToolUse` hook runs before the permission mode is
consulted at all, it holds regardless of mode. The flag is also correctly set on the command line
rather than in project settings, where the guide notes auto is ignored by design.

---

## B. Verified defects

Three findings where the repo contradicts a documented Claude Code constraint. Each produces
enforcement that intermittently does not run, or output that is silently discarded.

### 01. Hook work exceeds the declared timeout budget — Ch 10, A3 — **critical**

`hooks.json` sets `"timeout": 10` seconds on every handler. Several hooks can demonstrably exceed
it, and a hook killed at the timeout is enforcement that did not happen.

| Hook | Slow work | Bound |
|---|---|---|
| `warn-lint-on-edit.py` | spawns oxlint | `timeout=20` — inside a 10s hook |
| `warn-stacked-pr-merge.py` | `gh pr view` + `gh pr list` | 8s + 8s — two GitHub round-trips inside 10s |

The aggregate is worse than any single hook. `dispatch-bash-pretooluse.py` runs seven hooks in one
interpreter on **every Bash call**, whose combined worst case includes both `gh` calls, a repo-wide
`git status --porcelain` (8s), `default_base_branch()`'s ~5 git calls, an `os.walk` of up to 5,000
entries, and `guard-worktree-isolation`'s unconditional pair of `git rev-parse` calls.

**Direction:** raise the per-handler timeout above the worst realistic child, or move the
network-bound and repo-wide-scan hooks off per-tool-call cadence. The guide's framing favours the
latter — a `gh` round-trip belongs on a once-per-session or once-per-condition gate, not on every
shell command. Ch 10: "Cadence is the thing to watch: the same check is fine on `SessionStart` and
unusable per tool call."

### 02. Three `git rev-parse` calls with no timeout, on every edit — Ch 10 — **critical**

`block-worktree-path-escape.py` issues `git rev-parse --absolute-git-dir`, `--git-common-dir` and
`--show-toplevel` with no `timeout` argument, on every `Edit` and `Write`. Every other subprocess
call in the hook tree carries an explicit 5s or 8s bound; these three are the exception.

A hung or slow git — a network filesystem, an index lock held by a concurrent session, exactly the
contention `guard-worktree-isolation` exists to detect — blocks the hook indefinitely rather than
failing open.

**Direction:** add the `timeout=5` the sibling hooks use, and treat expiry as the hook's existing
git-failure path (exit 0, fail open).

### 03. No output-size guard against the 10,000-character cap — A3 — **high**

Claude Code caps hook output — `additionalContext`, `systemMessage` and plain stdout alike — at
10,000 characters, writing the overflow to a file and passing Claude a path plus a preview. No CLA
hook counts characters.

Item-count truncations exist (`hits[:5]`, `hits[:3]`, `_MAX_DIAGS = 10`) but individual items are
unbounded in length:

- `warn-comment-dates` joins three whole source lines
- `warn-stray-scratch-artifact` joins **every** matching stray path
- `warn-stacked-pr-merge` joins every child PR number

Both dispatchers then concatenate all children with no cap of their own. A large enough warning
degrades to a file path Claude must choose to read — the opposite of the immediate feedback loop the
warn hooks exist to create.

**Direction:** a shared character-budget helper in `_dispatch_lib.py`, applied at the dispatcher
boundary where the concatenation actually happens, is a single point of control for all thirteen
scripts.

---

## C. Practice gaps

Documented Claude Code capabilities that map onto something CLA does by other means, or does not do
at all. Ordered by value against implementation cost.

### 04. No skill opts out of automatic invocation — Ch 11 — **high**

None of the 18 skills sets `disable-model-invocation`. Every one can fire on description match alone
— including `multi-pr` (merges pull requests), `multi-lite` (opens and merges them), and
`update-cla` (rewrites the plugin's own files). The guide's example of a skill that should never
self-trigger is a deploy; a chained PR merge is the same class of action.

There is a second payoff. A skill with `disable-model-invocation: true` keeps its description out of
Claude's context entirely, costing nothing until the command is typed. CLA's 18 descriptions total
**9,906 characters** loaded at every session start — roughly 2,500 tokens before anything is typed,
in a listing the guide notes gets truncated under budget pressure starting with the least-invoked
skills.

**Direction:** set it on the three destructive orchestrators first. The safety argument and the
context argument point the same way, and the change is one frontmatter line each.

### 05. The `ask` tier is unused, in hooks and in settings — Ch 7, Ch 10, A2 — **high**

CLA's enforcement is binary: block (exit 2) or warn (exit 0 with context). No hook returns
`permissionDecision: "ask"`, which escalates to the user's permission prompt rather than failing
outright — and which, per Ch 7, fires in *every* permission mode including the `auto` the launcher
sets. Meanwhile `.claude/settings.local.json` carries an allow-only `permissions` object of 13
entries with no `ask` and no `deny` array.

Concrete exposure: `Bash(git *)` is allowed wholesale. `block-direct-push-to-main.py` covers pushes
to main, but nothing covers `git push --force` to a feature branch or `git reset --hard` — the two
operations the guide singles out as the irreversible cases a broad `Bash(git *)` would otherwise
cover.

The guide also shows why the naive fix is wrong: a `deny` rule on `Bash(git push --force *)` misses
`git push -f` entirely, because argument-shaped deny rules are fragile. CLA already has the better
instrument.

**Direction:** extend the existing Bash dispatcher with a force-push / hard-reset hook returning
`permissionDecision: "ask"` rather than a hard block. It survives every mode, it is command-shape
aware rather than flag-string matching, and it preserves the deliberate override the current
`ALLOW_*` env vars provide.

### 06. `multi-pr`'s failure path produces no status report — Ch 20 — **medium**

Three of Ch 20's four contract points are met. The fourth — report status in the output — holds only
on the success path. `multi-pr`'s final report names which changes shipped, with no per-change
succeeded / skipped / failed enumeration, because a Tier A structural failure halts the chain before
Phase 4 ever runs. Per-change status survives in `TaskUpdate` state and the running-notes file, but
the run's own terminal output does not carry it.

The halt-the-chain semantics are correct for a dependency chain and should not change; this is about
what the run tells you on its way out. `multi-lite` already has the shape to copy.

**Direction:** a terminal status enumeration on the Tier A halt path, listing every change as
shipped / halted-here / never-attempted.

### 07. `right-model` is missing half the current effort surface — Ch 24 — **medium**

The skill's instinct not to hardcode a model list is right and the guide agrees. But its effort model
is stale, and effort is the dial it exists to set.

Absent:

- `xhigh` and `max` — the skill says "commonly low/medium/high"
- `opusplan` — plan on Opus, execute on Sonnet
- `ultrathink` — the single-turn escalation that changes no setting
- the fact that a level is not comparable across models (xhigh on Opus ≠ xhigh on Sonnet)

All four are cost levers, which is the skill's entire remit. `opusplan` in particular describes
`spec-to-pr`'s own shape — expensive reasoning in the plan phase, cheap execution after — and
`ultrathink` is the cheapest escalation available, costing one word rather than a session-wide
setting change.

**Direction:** add the four plus the per-model calibration caveat, keeping the no-hardcoded-roster
discipline. Describe the levers, not the lineup.

### 08. No git identity verification anywhere — Ch 17, Ch 18 — **medium**

Confirmed absent from all runtime paths: `git config user.email` appears only in test fixtures, and
`ssh -T` nowhere at all. The pre-push checks that exist are branch-and-state shaped (`git_state.py`,
`--expect-branch feature/<name>`) and say nothing about who is pushing.

The guide's argument for why this ranks above the SSH-key case is that the failure modes differ in
reversibility: a wrong key is rejected loudly at push time, while a wrong `user.email` is accepted
silently and surfaces later in the log, fixable only by rewriting history.

If it becomes a check, it must read the greeting line from `ssh -T` and **not** its exit code —
GitHub closes the connection without a shell, so a successful auth exits 1.

**Direction:** a `warn-git-identity` hook on the existing Bash dispatcher, gated on push-shaped
commands, reading the expected identity from the per-repo `cla.io/project-facts.md` overlay so
nothing project-specific enters the synced core.

### 09. No single-hypothesis discipline in the test-fix loops — Ch 19 — **medium**

Both loops say only "diagnose":

> `lite-pr`: "Any failure (in either tier) → diagnose, apply one fix via `Edit`, re-run from the
> failing tier once."

Neither asks for a stated root-cause hypothesis before the fix, and neither distinguishes fixing a
cause from suppressing a symptom.

The one-fix-then-one-retry cap does partly enforce the guide's discipline by accident — you cannot
fire four simultaneous fixes at a failing suite. But the cap constrains volume, not reasoning: a
single change made without a hypothesis is still a guess, and the retry budget is spent either way.

Notably `spec-to-pr` already carries excellent *domain-specific* triage for flaky local
infrastructure (the failing file changes between identical runs; the stderr names the tool's internal
error, not an assertion). The general method is what is missing.

**Direction:** one line in each loop requiring the fix to be preceded by a stated cause, and a check
that the explanation of why the fix works is specific rather than "makes it more robust."

### 10. No shared sub-agent brief template — Ch 12, A4 — **medium**

Every dispatch site invents its own scoping language, and the quality gradient is steep.
`spec-to-pr`'s Implement brief has three strong rules — full-task enumeration (an agent will not
invent an omitted task), a trimmed brief, and an evidence-based terminal contract that is stronger
than the guide's own "Done when." `lite-pr`'s review dispatch is a single sentence with no template.

Measured against the guide's five-slot brief (Scope / Task / Do not / Report / Done when), the
consistently missing slot is **do-not-touch**. Ch 12 identifies it as the one that prevents two
parallel agents editing the same file — and CLA dispatches agents in parallel in both `lite-pr` and
`spec-to-pr`. The nearest analogue in the repo is narrower: a rule that delegation covers edit
application only, with re-verification never delegated.

**Direction:** one reference doc in the synced core carrying the five slots, with `spec-to-pr`'s
evidence-based terminal contract adopted as the "done when" slot — it is the better version. Each
dispatch site then cites it rather than restating it.

### 11. Worktree env carry-over is hand-rolled — Ch 13 — **low**

`new-worktree` resolves the main checkout through `git rev-parse --git-common-dir` and `cp`s each env
file listed in `project-facts.md`. The reasoning is sound and the `--git-common-dir` choice is
correct. But Claude Code has a declarative equivalent the skill never mentions: a `.worktreeinclude`
file at the project root, gitignore syntax, copying only files that are both matched **and**
gitignored.

The difference that matters is coverage. The hand-rolled copy runs only when someone invokes the
skill; `.worktreeinclude` applies to every worktree the harness creates, including the ones
`multi-lite`, `multi-pr` and `spec-to-pr` create through raw `git worktree add`.

Also unmentioned: `worktree.baseRef`, which controls whether a new worktree branches from the remote
default or from current HEAD — a setting those three skills currently express by hand as
`origin/<base-branch>`.

---

## D. Lower-priority observations

### 12. Inconsistent working-directory resolution across hooks

`block-direct-push-to-main.py` and `guard-worktree-isolation.py` read `payload["cwd"]` from the
hook's stdin JSON. `block-worktree-path-escape.py` and `block-unsafe-recursive-delete.py` use
`os.getcwd()` instead. The guide makes the equivalent point about status lines — read the directory
out of the payload rather than trusting the process — and it matters after `/cd` or `/add-dir`, where
the two can diverge. Two of the four hooks would then reason about the wrong tree.

### 13. Sync provenance cannot answer "from which commit?"

`.cla-sync-lock.json` records `last_synced_sha256` and a source-repo *name* per asset — no source
commit SHA, no timestamp, no version. The plugin manifest does carry `version: "0.0.1"`, which is
the right call (the guide notes omitting it makes every commit a new version to consumers), but the
version is not recorded in the lock. A consuming repo can verify that a file matches what was
written, but not identify what it was written *from*.

### 14. A project token has leaked into an unscanned tree

CLAUDE.md warns that the conformance guard scans only `skills/`, leaving `hooks/` and `agents/` to be
watched by hand. Confirmed instance: `hooks/tests/test_block_unsafe_recursive_delete.py` carries path
literals naming a different repo (`C:\Code\agentic-air\…`). They are synthetic parse inputs, never
touched on disk, so the tests are correct — but it is exactly the leak class the guard cannot see, in
exactly the tree it does not scan.

### 15. Two allow rules are inert

`Bash(ls *)` and `Bash(pwd)` in `settings.local.json` change nothing: both are in Claude Code's
built-in never-prompted read-only set, alongside `cat`, `echo`, `grep`, `find`, `head`, `tail`, `wc`,
`which`, `diff`, `stat`, `du`, `cd` and read-only `git`. `Edit(./**)` is correctly spelled — the
guide notes `Write(path)` and `Glob(path)` parse but never match, while `Edit` covers all
file-editing tools.

### 16. Two candidates for `context: fork`

`codify-retro` and `spec-to-pr-retro` both read JSONL ledgers, aggregate deterministically via
scripts, and return a comparatively small report — the guide's exact description of work that should
run in its own sub-agent context. Neither uses `context: fork`, and no skill uses `model:` either,
though both retros do their heavy lifting in Python rather than in the model.

### 17. No continuously-updated decision log

`spec-to-pr` explicitly forbids mid-run logging ("Per-phase mid-run logs remain forbidden") and
`lite-pr` writes nothing meta to disk; both persist only at Handoff. That is a defensible anti-bloat
position and not obviously wrong.

Worth naming only because of an interaction the guide flags: under `--permission-mode auto`, a
boundary stated conversationally is re-read from the transcript on every classifier check, so a
compaction during a long run can drop it. Rationale held in context across several phases has the
same exposure. `multi-lite`'s ledger — written the moment a PR opens, and used as the resume key —
is the counter-example already in the repo.

---

## E. Coverage map

| Ch | Subject | Verdict | Finding |
|---|---|---|---|
| 1–4 | Posture, install, mental model, commands | n/a | User-level; no harness surface |
| 5 | CLAUDE.md | ahead | Fact/procedure split with per-repo overlays exceeds the guide's model |
| 6 | Context management | gap | #17 — no continuous decision log |
| 7 | Permissions & Plan Mode | gap | #05 — `ask` tier unused |
| 8 | Memory | conformant | Auto-memory in use; repo-durable state in `cla.io/` |
| 9 | MCP servers | n/a | CLA ships none |
| 10 | Hooks | **defects** | #01, #02, #03 |
| 11 | Skills | gap | #04, #16 — invocation control, fork context, description budget |
| 12 | Sub-agents | partial | #10 — verification exemplary; brief template absent |
| 13 | Multi-Clauding & worktrees | gap | #11 — `.worktreeinclude`, `worktree.baseRef` |
| 14 | Headless mode | n/a | CLA is interactive-only by design |
| 15 | Daily rhythm | partial | Session open/close ritual has no CLA equivalent; see #17 |
| 16 | TDD | **not assessed** | Open edge of this pass — worth a follow-up against the test loops |
| 17–18 | Git workflow & identity | gap | #08 — no identity verification |
| 19 | Debugging | gap | #09 — no hypothesis discipline |
| 20 | Automation pipelines | partial | #06 — `multi-lite` exceeds; `multi-pr` failure path incomplete |
| 21 | Common failure modes | ahead | codify/retro loops formalize what the guide handles informally |
| 22 | Plugins & marketplaces | minor | #13 — lock file provenance |
| 23 | Agent SDK | n/a | Not an SDK application |
| 24 | Shaping the session | gap | #07 — `right-model`'s effort surface |
| 25 | Letting it run | conformant | A6 — auto mode's push allowance compensated |
| 26 | Code review | ahead | Multi-agent adversarial review predates the guide's cloud tier |
| 27–29 | Web, CI, browser & chat | n/a | Outside a terminal-loaded plugin's surface |
| A1 | CLAUDE.md template | reference | Compared; no gap |
| A2 | Permissions reference | gap | #05, #15 — rule tiers and inert entries |
| A3 | Hooks reference | **defects** | #03, #12 — output cap, `cwd` resolution |
| A4 | Patterns cheatsheet | gap | #10 — sub-agent scope brief |
| A5 | Command reference | reference | No gap |

---

## Suggested order

1. **Findings 01–03.** Verified defects in the hook layer. All three produce enforcement that
   intermittently does not run, which is worse than no enforcement because it looks like coverage.
   Each is a contained fix in code that already has a test scope.
2. **Findings 04 and 05.** Safety-relevant and cheap. `disable-model-invocation` on the three
   destructive orchestrators is one line each and cuts the always-loaded description budget. The
   `ask`-tier hook closes the force-push and hard-reset exposure `Bash(git *)` currently leaves open.
3. **Findings 06–11.** Genuine practice gaps, none urgent. 07 and 08 are the most self-contained;
   10 is the most valuable if CLA keeps adding parallel dispatch sites.
4. **Findings 12–17.** Fold into whatever touches those files next rather than scheduling on their
   own.

## Caveats

- Guide citations reference the edition its author verified against Claude Code 2.1.220. The guide's
  own note that flags and settings keys age faster than patterns applies to the mechanical findings
  here — particularly the 10,000-character hook output cap and the built-in read-only command set.
  Re-confirm both against current docs before implementing 03 or 15.
- Chapter 16 (TDD) was not assessed.
- Findings A1–A6 are recorded so that later readers do not "fix" something the guide already endorses.

---

## F. Resolution log

Appended after working the findings. The triage above is left as originally
filed; this section records what actually happened, **including two places where
the audit itself was wrong**. Fixes landed on branch `fix/hook-handler-budget`.

### Status

| # | Finding | Outcome |
|---|---|---|
| 01 | Hook timeout budget | Fixed |
| 02 | Unbounded `git rev-parse` | Fixed |
| 03 | No output-size guard | Fixed |
| 04 | No `disable-model-invocation` | Fixed |
| 05 | `ask` tier unused | Fixed |
| 06 | `multi-pr` halt-path report | Fixed |
| 07 | `right-model` effort surface | Fixed |
| 08 | No git identity check | Fixed (partially — see below) |
| 09 | No hypothesis discipline | Fixed |
| 10 | No sub-agent brief template | Fixed |
| 11 | Worktree env carry-over | Fixed — **audit corrected** |
| 12 | `cwd` resolution inconsistency | Fixed |
| 13 | Sync-lock provenance | Fixed |
| 14 | Foreign project token | Fixed — **audit corrected, scope was 6x larger** |
| 15 | Two inert allow rules | **No action** |
| 16 | `context: fork` on the retros | **Rejected — audit error** |
| 17 | No continuous decision log | **No action** |

### Corrections to this document

**Finding 11 overstated its scope.** It claimed `.worktreeinclude` would cover
the worktrees `multi-lite` / `multi-pr` / `spec-to-pr` create. It would not:
that file is harness machinery, and those three use raw `git worktree add`,
which is git. The real (narrower) justification is that `new-worktree` spends
its entire design budget minimizing round-trips, and this removes a command
from that path.

**Finding 16 was aimed at the wrong skill, and rests on a premise that does not
hold here.** Two independent reasons it was rejected:

1. Both retros state "Do NOT apply edits without explicit confirmation — retros
   are advisory." A `context: fork` sub-agent cannot reach the user to ask, so
   forking breaks the confirmation gate.
2. It would save little regardless. The read-heavy aggregation in both retros is
   already offloaded to deterministic Python, so what enters context is a compact
   metrics summary, not raw file reads. The finding assumed model-driven reading
   without checking.

Re-aimed at `project-review` — the skill that genuinely reads broadly — and it
came back negative too: that skill is *itself* an orchestrator that dispatches
five agents and aggregates "only their conclusions, never their raw reads", and
it sets per-agent `model:` routing that nesting inside a fork would disturb.

**The generalization worth keeping: the guide's "read-heavy → `context: fork`"
pattern does not apply anywhere in CLA.** This plugin already offloads heavy
reading two other ways — deterministic scripts, and agent delegation with
conclusions-only return. A future audit should check for those two before
proposing `fork` again.

**Finding 14 sampled the leak rather than measuring it.** It named one file. The
token was in **19 places across six files in three test scopes**. More useful than
the miscount is *why* nobody caught it: the conformance guard could not have, on
three independent counts that all applied at once.

- It globs `*.md`. Every occurrence was in `.py`.
- `tests/` and `scripts/` are in `EXCLUDED_SUBTREES` — on the reasoning that they
  carry no portable *prose*. They carry portable *strings*, and `update-cla` syncs
  them into every destination repo just the same.
- `hooks/` and `agents/` are not under `skills/`, so both are outside its scan root.

And it is dormant here regardless: with no curated `project-tokens.local.md` it
`pytest.skip`s, which is the "1 skipped" the `update-cla` scope reports on every run.
CLAUDE.md warns that `hooks/*.py` and `agents/*.md` are unscanned; it does not
mention `skills/**/tests/`, nor that the guard does nothing without an overlay.

Two guards were added so the class cannot recur — a source scanner covering the
three blind spots, and an absolute-path check that needs no token list at all. The
second is the durable one, and the reasoning generalizes:

**A token list fits a consuming repo and not a source repo.** In a consuming repo
the list is closed and self-known — your own project's vocabulary. In the source
repo there are no local product tokens to protect, and what leaks in are names from
*other* repos, arriving via pasted examples. Listing those means enumerating every
repo the author works in: open-ended, externally determined, and stale the moment a
new project starts. It catches the names you already know, which are the ones you
already fixed. A closed-form pattern — no synced-core file may carry a hardcoded
absolute developer path, whatever repo it names — catches a name nobody has seen,
and is what would actually have caught this one.

Worth recording about the tuning, because a synthetic-only rule would have shipped
broken twice: a naive drive-letter pattern matches `https://…` (`s:` followed by
`//` satisfies the drive shape), and after that was fixed every remaining hit was a
legitimate path-parsing fixture. The resolution was placeholder notation
auto-exempting and an explicit marker on real-looking fixtures — not a `tests/`
exemption, since `tests/` is where the leak lived.

### Deliberate non-changes

**15 — two inert allow rules.** Verified inert: `ls` and `pwd` are both in the
built-in never-prompted read-only set, so removing them changes no behavior. The
file is also gitignored and machine-local, so the edit would be uncommittable.
Recorded rather than done, so it is not re-raised.

**17 — continuous decision log.** `spec-to-pr` forbids mid-run logging as a
deliberate anti-bloat decision with a stated rationale, and this document already
conceded that position was defensible. The narrower real exposure — a boundary
stated *conversationally* being dropped by compaction under `--permission-mode
auto` — is closed by finding 05, whose rules live in a hook and therefore never
depended on the transcript. Adding a log would treat a symptom of a problem that
no longer exists.

### Partial

**08 — git identity.** Implemented the `user.email` half only. The guide pairs it
with an `ssh -T` key check; that is a network round-trip on a hook firing at every
commit and push, which is precisely the per-tool-call cadence that caused finding
01. The greeting-not-exit-code trap (`ssh -T` exits 1 on success) is recorded in
the hook's docstring for whoever adds that check at a slower cadence.

### Still open

Chapter 16 (TDD) remains unassessed — the one edge this pass never reached.

---

## Section G: Multi-agent review round

A five-agent review (code, tests, silent-failure, comments, type-design) over the
finished branch found the audit had **shipped three defects of the same class it
was written to close** — a guard that looks like coverage while producing nothing.
All are fixed; findings below are the ones that survived independent verification
against the branch.

### Critical, all verified by hand before fixing

**G1 — an `ask` was discarded whenever any unrelated hook errored.** A permission
decision on stdout is honoured only on exit 0, and the dispatcher returned
`1 if errored else 0` while printing the ask JSON. One sibling with a typo and
every force-push in the session ran unprompted. Fixed: an ask forces exit 0 and
the failure notice rides in the prompt text. The same bug applied to the
Edit/Write dispatcher's `additionalContext`, fixed the same way.

**G2 — the `Deadline` gated starting, not fitting.** Enforcing hooks summed to
**17s (Bash) and 21s (Edit/Write) against a 10s handler**, so the handler was
killed before the last hook — always a blocking one — ever ran. Per-hook timeouts
had been tuned but never summed. Fixed by collapsing the redundant twin
`rev-parse` calls in both worktree hooks into one (`rev-parse` takes multiple
options and prints one line each), retuning local-git timeouts to 2s, and adding
`HOOK_WORST_CASE_SECONDS` plus a test that fails when the enforcing sum stops
fitting. Now 8.0s against an 8.5s budget.

**G3 — PowerShell, the primary shell on Windows, ran one hook of nine.** Only
`block-unsafe-recursive-delete` was wired to it, so a force-push, a push straight
to main, or a wrong-identity commit issued through PowerShell bypassed every git
guard. This was **pre-existing and the audit missed it entirely** — the pass
checked what the hooks do, never which matchers they are wired to. Fixed by
routing PowerShell through the shared dispatcher; every hook there matches on
command shape, not shell syntax.

### Also fixed

- The developer's real Windows username was still in a synced-core fixture. The
  new path guard could not see it (separators stripped), so a `mangled-windows-path`
  shape was added. **The rename in finding 14 fixed the repo name and left the
  username** — the same line, the same sweep.
- `ask-destructive-git` silently allowed `git push -uf` (bundled short flags) and
  `git push origin +feat` (refspec force), and falsely prompted on any multi-line
  command containing `-f` on a later line. All three verified empirically, before
  and after.
- Its module docstring emitted a `SyntaxWarning` (regex in a non-raw string).
- `find_absolute_path_leaks` had **zero** unit tests; the only test asserted the
  real tree was clean, which passes identically if the function returns nothing.
- An `elif` meant a placeholder Windows path on a line suppressed the home-path
  check for that whole line.
- `ask-git-identity` failed open *silently* even with `CLA_EXPECTED_GIT_EMAIL`
  set — an explicit request to verify, answered with silence. Now warns.
- `source_commit` recorded a bare sha from a dirty source tree, which is the
  normal state for a `--plugin-dir` repo. Now suffixed `-dirty`.

### The lesson worth keeping

Every G-finding is a **wiring** or **budget** fact, not a logic fact. The audit
read each hook's code carefully and never asked what the hook was connected to or
what it cost when summed with its siblings. A guard's correctness is not a
property of its own file.

Second: I dispatched five review agents with "make no edits" and one checked out
a different branch mid-review, because I scoped the prohibition to file edits and
never forbade repository state changes. That is exactly the omission
`subagent-brief.md`'s **do-not-touch** slot exists to prevent, in the same PR that
introduced the slot. Agents sharing one working tree need the constraint stated as
*repository state*, not *files*.

### G4 — the whole Bash warn tier reached nobody (found on the merge check)

Asking "ready to merge?" surfaced a fourth instance of the same class, and the
worst one. The branch asserted in three docstrings that *"exit 0 drops stderr
entirely per the documented hook contract"* — and then left every advisory
warning on stderr at exit 0. Both could not be true.

Confirmed against the published hook reference rather than reasoned about:

> "Stderr from a hook that exits 0 goes to the debug log only, never the
> transcript, and Claude never sees it."
>
> "Any other exit code ... the transcript shows a hook error notice followed by
> the **first line** of stderr."

So `warn-branch-base`, `warn-stacked-pr-merge`, `warn-stray-scratch-artifact` and
`guard-worktree-isolation`'s degraded warnings had been spawning subprocesses on
every Bash call and delivering nothing — including, for one round, **the
strict-mode warning added earlier the same day to fix a silent fail-open.** The
fix replaced an invisible failure with an invisible warning.

It also showed the exit-1-on-skip fix from the previous round was the wrong
instrument: a non-zero exit discards stdout entirely and surfaces only the first
line of merged multi-hook stderr, so it reports *less*, not more.

Both dispatchers now send everything non-blocking through one stdout JSON object
at exit 0 — `permissionDecision` for an ask and `additionalContext` for advisory
text, which coexist in one `hookSpecificOutput`. Neither dispatcher exits
non-zero unless a hook actually blocked. Verified end-to-end: a warn-only call,
a force-push, and an identity mismatch all now deliver on a channel Claude reads.

**The lesson.** Three rounds of this audit reasoned from the repo's own
docstrings about an external contract, and the docstrings were *right* — the code
just contradicted them. Nobody checked the primary source until the last round.
A stated contract in a comment is a claim to verify, not a premise to build on;
when a fix and a comment disagree about the same contract, that disagreement is
the finding.

---

## Section H: Chapter 16 (TDD) — the last unassessed chapter

Closed. Assessed against the skills as written, not from memory.

**What the chapter argues.** Write the failing test first and watch it fail;
"a test that can fail is a test that means something." Its named failure mode is
*implementation drift* — Claude writes test and implementation in one response,
so the test passes whether the implementation is correct or not. It offers two
enforcement hooks (16.3) and a refactoring discipline (16.4).

### Where CLA is already ahead

The chapter's remedy is **temporal**: watch it go red once. CLA's `not_vacuous`
pattern is the **structural** form of the same guarantee — a test asserting the
check can still fire at all (`test_the_outcome_detector_is_not_vacuous`,
`test_the_scanner_is_not_vacuous`, `test_source_scan_of_the_real_plugin_is_non_vacuous`).
Watching a test fail is evidence at one moment; a non-vacuity test keeps holding
after a refactor quietly turns the check into a no-op. For a repo whose features
are mostly guards, that is the better instrument.

`lite-pr`'s symptom-fix rule also covers the chapter-33 companion rule ("never
modify tests to make them pass") more precisely than the guide states it:
*"Loosening an assertion, widening a type, adding a try/except around the failing
call, or bumping a timeout all turn the suite green without touching the defect."*

### Where the guide was ahead — and it stings

1. **Sequence.** `lite-pr` Implement is: change the code (1), then add the tests
   (4). Nothing said to show the test failing first. That is precisely the
   ordering the chapter warns produces a meaningless test — and this audit
   *shipped one*: `find_absolute_path_leaks` had a single test asserting the real
   tree was clean, which passes identically if the function returns `[]`. Caught
   by review, not by the suite. Fixed, and a red-before-green rule added to
   `lite-pr`.

2. **"Not all red is the right red."** An import error, a broken fixture, or an
   unrelated failure is a failure of the test, not evidence about the code. CLA
   had nothing on this. Now stated.

3. **The part that stings.** Section 16.3, explaining its TDD hook, says:

   > "A bare `echo` would not do this: on exit 0 plain stdout goes to the debug
   > log, not to you." … "The reason goes to stderr because on exit 2 Claude
   > ignores stdout entirely."

   That is **finding G4**, stated plainly, in the one chapter this audit never
   read. Four rounds and a merge check were spent rediscovering it from the hook
   layer's own contradictory docstrings. The cost of declaring a chapter
   out of scope was the most expensive defect in the branch.

### Where it does not apply

The 16.3 enforcement hooks are inapplicable here, and now for a measured reason
rather than a hunch: a PostToolUse hook running the suite on every test-file
write would fire a ~2-minute hooks scope inside a 10s handler — the exact budget
class as finding G2. The guide flags the cost itself ("a noticeable pause on
every edit"); at this suite's size it is not a pause, it is a guaranteed kill.
The flag-file blocking hook is self-described as heavyweight and is not warranted.

**Coverage is now complete: 34 of 34 chapters, 5 of 5 appendices.**
