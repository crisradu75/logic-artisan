# Port the claude-plugins carry-back fixes into the canonical CLA core

**Topic (given):** The peer repo `claude-plugins` maintains `cla-upstream.md` — a carry-back
ledger of defects found while reviewing its `cla` sync, each already fixed *there* and each
portable. Port the applicable items into this repo (the canonical `cla` source) so every
destination gets them on the next `update-cla`.

**Grounding done before shaping:** every item below was re-verified against this repo's own
tree, not accepted from the ledger. Line references are ours. Two ledger items were dropped on
that evidence:

- **Item 15 (`codify-learnings/references/routing.md` hardcodes `TODO.md`)** — not applicable.
  Our `routing.md` has no "upstream plugin" section, and `TODO.md` appears nowhere under
  `skills/codify-learnings/`. The offending sentence exists only in the destination's copy.
- **Item 11 (post-adapt local-line accounting in `update-cla`)** — deliberately deferred; see
  "Explicitly deferred" below.

## Questions asked and decisions

| # | Question | Chosen option | Rationale |
|---|---|---|---|
| 1 | How to package the port | Grouped PRs by severity, chained via `/cla:multi-lite` | Cleanest history and a per-group review pass; the groups have genuine file overlap, so they serialize anyway |
| 2 | Scope of the `update-cla` hardening (ledger items 8/10/11) | Normalize + structural refusal + guard test + the Phase-2 script-premise requirement — but NOT item 11's line accounting | Items 8 and 10 are mechanically checkable at apply time; item 11 needs a diff-accounting design that is its own change |
| 3 | Whether to also fix `discover_tests.py`'s `package.json` premise | Out of scope here | The ledger calls it correct-upstream; it is not (this repo is stdlib-Python-only), but it is a separate change from the port — see "Explicitly deferred" |

---

## Candidate 1 — Close the three `git push` → main bypasses (P0)

**depends_on:** none

`.claude/plugins/cla/hooks/block-direct-push-to-main.py` currently lets real
pushes to the default branch through. Three distinct holes, one file:

1. **Only the first `git push` is inspected.** `_push_arguments` (line 107) calls
   `_GIT_PUSH.search()` — one match — then truncates at the first shell separator. The
   truncation is right; the single `.search()` is not. Every push after a separator is
   invisible: `git push origin feature/x && git push origin main` reaches the remote
   unblocked, as do the `;`, `-u`, and `| tee log &&` variants. This is a regression the
   refactor to shared `_dispatch_lib` helpers introduced — the older whole-string regex
   caught it.
   **Fix:** `_GIT_PUSH.finditer()`, one argument window per match, block if *any* window
   targets a protected ref. Rename to `_push_argument_lists`. Preserve the existing allow:
   `git push origin feature/x && echo main` (an `echo` is not a push).

2. **`git push origin HEAD` from `main` is not blocked.** `HEAD` (and `@`) is a positional
   refspec, so `_refspec_touches_main` (line 87) compares it as a literal ref name and matches
   nothing protected — while the bare-push current-branch check never runs because a refspec
   *was* present. `git push origin HEAD` is exactly what a script emits when it does not want
   to hardcode a branch name.
   **Fix:** resolve `HEAD`/`@` on either side of the refspec through the current branch. Keep
   it lazy — a literal `git push origin main` must still be decided with **no** subprocess
   call, so the guard does not become dependent on git being usable to catch its most common
   offense. Pin that with a test.

3. **HEAD is resolved in the wrong directory.** `main()` (line 163) never reads
   `payload["cwd"]`, and `GIT_GLOBAL_OPTS` consumes `-C` / `--work-tree` prefixes without ever
   using the target path. Both directions fail: a session in a worktree while the primary
   clone sits on `main` fails *open*; the inverse over-blocks a legitimate push.
   **Fix:** thread `payload["cwd"]` into `_current_branch`, preferring a `-C` / `--work-tree`
   value from the command itself when present. `guard-worktree-isolation.py` already
   establishes this pattern — match it.

**Tests:** extend `hooks/tests/test_block_direct_push_to_main.py` — the four verified bypass
shapes, the `echo main` allow, `HEAD`/`@` from main and from a feature branch, the no-subprocess
pin for a literal refspec, and cwd/`-C` resolution.

---

## Candidate 2 — Hook crash + base-branch correctness (P1)

**depends_on:** Candidate 1 (same `hooks/` tree and test scope)

Four defects that either crash a hook or produce a silently wrong value:

1. **`warn-stacked-pr-merge.py:102` crashes on a non-dict `tool_input`.**
   `(payload.get("tool_input") or {}).get("command", "")` — `payload` is `isinstance`-checked,
   `tool_input` is not. The four sibling hooks all carry the guard; this one was missed.
   Consequence is out of proportion to the hook: `_dispatch_lib.run_hook` catches the
   `AttributeError`, the dispatcher exits 1, and **every Bash call in the session** emits a
   hook-error notice with a traceback — from a hook whose only job is to warn.
   **Fix:** the two-line sibling `isinstance` pattern.

2. **`_dispatch_lib.default_base_branch` trusts a stale `origin/HEAD`.** Step 1 (line 170)
   accepts `git symbolic-ref refs/remotes/origin/HEAD` unconditionally while steps 2–3 right
   below it do `rev-parse --verify`. `refs/remotes/origin/HEAD` is a clone-time cache that is
   never auto-refreshed, so after an upstream `master`→`main` rename it names a ref that no
   longer exists — and `symbolic-ref` still exits 0 on a dangling symref. Reproduced
   end-to-end downstream: in a `main` repo it returned `master`, after which
   `git rev-list master..HEAD` failed with `unknown revision` — precisely the failure this
   function's own docstring claims to have fixed.
   **Fix:** `rev-parse --verify --quiet` the symref target before trusting it; reject a literal
   `HEAD`; otherwise fall through to the existing chain.

3. **The base-branch fallback is silent, and two callers swallow its failure.**
   `default_base_branch` returns the literal `"master"` (line 182) with no stderr — it cannot
   distinguish "this repo genuinely uses master" from "git is broken and I guessed", which is
   inconsistent with every sibling hook's degrade-loudly convention. Worse, in
   `skills/spec-to-pr/scripts/probe_state.py`, `_branch_state` (line 138) and
   `_fix_rounds_applied` (line 184) both return on any non-zero rc with no stderr, so
   `False` / `0` read as *legitimate negatives* ("no feature branch", "no fixes applied yet").
   The orchestrator uses these for implicit phase resume, so the visible symptom is re-running
   completed work or re-looping an applied fix round, with the true cause (`unknown revision`)
   printed nowhere. The same file already does this correctly in `_implement_done` and
   `_pr_state`.
   **Fix:** stderr note before the fallback; diagnostics on the non-zero rc in both callers;
   expose the resolved base branch in `probe()`'s JSON so a wrong value is visible rather than
   inferred. Mirror the symref verification into `probe_state._base_branch` (line 105), which
   carries its own copy of the resolver.

4. **`probe_state._run` catches too narrow an exception set and has no timeout** (line 45).
   `cwd=REPO_ROOT` lets `subprocess.run` raise `NotADirectoryError` / `PermissionError` — both
   `OSError`, neither `FileNotFoundError` — so the script dies with an uncaught traceback and
   emits **no JSON at all**, leaving the orchestrator parsing stdout with nothing. A bad cwd
   that *does* raise `FileNotFoundError` is recorded as `"tools_missing": ["git"]`, a false
   diagnostic pointing at PATH. And there is no `timeout`, while sibling `_repo_root` uses 10s
   and `_dispatch_lib._git` uses 5s — every `gh` network call can hang on a credential prompt.
   **Fix:** catch `OSError`, distinguish missing-executable from bad-cwd, add a timeout
   consistent with the siblings.

**Tests:** `hooks/tests/test_warn_stacked_pr_merge.py` (non-dict `tool_input`),
`hooks/tests/test_dispatch_lib.py` (dangling symref → falls through; fallback emits stderr),
`skills/spec-to-pr/tests/test_probe_state.py` (bad-cwd `OSError` still emits JSON, rc
diagnostics reach stderr, resolved base branch present in `probe()` output).

---

## Candidate 3 — Harden `update-cla`'s apply phase against silently-wrong syncs (P2)

**depends_on:** Candidate 2 (sequential to keep the chain's merges linear)

The downstream sync wrote 19 of 37 files with every `\r\n` turned into `\n\n` — a blank line
between every line. **Byte counts were identical**, which is why nothing caught it: not the
hook suite, not the guards, not the apply summary. Five markdown tables stopped parsing (a
blank line before `|---|` is not a table in CommonMark) and every diff became unreviewable —
`probe_state.py` read as 252 insertions for a 35-line change. Left unfixed it also poisons the
*next* sync, which sees all 19 files as fully divergent and loses the ability to review the
merge at all. `spec-to-pr/references/design-tradeoffs.md` was already doubled before that sync,
so this is a second occurrence, not a one-off.

Our `_write_file` (line 84) already pins `newline="\n"`, so the corruption happened upstream of
the write, between the adapting agent's output and the file. Root cause was never isolated to a
single line, so the fix is **defensive in `apply.py`** rather than a point fix:

1. **Normalize `adapted_content` line endings before writing.**
2. **Refuse structurally implausible content** — reject/flag content whose newline count is
   ~2× its non-empty line count, alongside the existing `_looks_like_binary_placeholder`
   refusal (line 93), and compare the adapted content's line count against the source's. A
   file whose newline count is ~2× its non-empty line count is never a legitimate adaptation.
   Surface it as a distinct `ApplyOutcome` status, not a silent skip.
3. **`_write_lock` writes CRLF on Windows** (line 134): `os.fdopen(fd, "w", encoding="utf-8")`
   with no `newline=""`, so Python translates `\n` → `\r\n`. The lockfile becomes the only CRLF
   file in the plugin and churns on every cross-platform diff. One-word fix: `newline="\n"`.
4. **Add a Phase-2 premise requirement to `references/adaptation_prompt.md`:** any adapted
   **script** must have its environmental premise checked against the destination repo — a
   script whose discovery/gate output is empty in the destination must be *reported*, not
   adopted silently. This is the second failure of the same shape: `discover_tests.py` arrived
   downstream assuming a root `package.json`; in a repo with none, both discovery tiers return
   empty forever and the Test phase reports `skip` with a wrong reason — a silent gate. It is a
   re-offense (the same script's premise had already failed there once, then `pyproject.toml`),
   and the local memory entry naming that exact script did not fire because the failure arrived
   through a sync rather than through someone authoring a skill.

**Tests:** `skills/update-cla/tests/` — a guard test for the doubled-newline refusal, one for
CRLF-input normalization, and one asserting the lockfile is written LF-only.

---

## Candidate 4 — Documentation accuracy + guard determinism (P3)

**depends_on:** Candidate 3 (touches `hooks/` docstrings and `update-cla/tests/`, both edited
by earlier candidates)

1. **`guard-worktree-isolation.py` docstring defects.** Names `.claude/settings.json` as its
   wiring point (line 15) — it is wired by the plugin's own `hooks/hooks.json`, so a maintainer
   following the docstring to inspect or disable the hook finds nothing. Self-contradicts on
   lines 26–29, listing `git merge`/`rebase`/`reset` as both handled and intentionally not
   guarded in consecutive clauses (verified: not guarded). Says "exotic/quoted shapes are
   intentionally NOT guarded" while `strip_quoted_spans` + offset re-slicing was added
   precisely to handle them, contradicting the same file's own newer docstrings. And
   `_is_checkout_switch`'s docstring (line 129) references `_is_local_branch`, a function that
   exists nowhere in the repo.

2. **`spec-to-pr/references/bash-discipline.md:18` prescribes exactly what `SKILL.md` forbids.**
   Its path-scoped-staging line ends with `git add openspec/` for the Archive phase, while
   `spec-to-pr/SKILL.md:339` says **"Path-scoped staging, NEVER a broad `git add openspec/`"** —
   because in a `multi-pr` chain it sweeps sibling changes' still-untracked directories into the
   archive commit. Same failure mode as `git add -A`, one level down, prescribed by the very
   reference file whose job is to prevent it. `references/archive.md:26` already shows the
   correct explicit form; make `bash-discipline.md` agree.

3. **`block-direct-push-to-main.py:59` misattributes how it is launched.** Says running
   standalone is "the shape `hooks.json` uses". `hooks.json` never invokes this file — it
   invokes the dispatcher, which loads the hook in-process. The `sys.path` insert is still
   correct and worth keeping, but the stated reason is wrong, and a maintainer checking
   `hooks.json` may conclude the guard is dead. `_dispatch_lib.py` gets this exactly right;
   the two should agree.

4. **The project-facts path guard's verdict depends on stray untracked directories.**
   `update-cla/tests/test_project_facts_paths.py` checks a candidate path only when its first
   segment matches a real top-level entry — and `_top_level_names` (line 189) derives that set
   from a live `repo_root.iterdir()`. That keeps it portable but makes the result
   **environment-dependent**: an *empty, untracked* directory in one checkout flips a path from
   skipped to checked. Observed concretely downstream — the same overlays passed inside a clean
   worktree and failed on the primary clone, which happens to contain an empty untracked
   `docs/`. The consequence that matters is a silent false negative in exactly the check meant
   to catch staleness: a green guard is not evidence the overlays are clean, only that this
   checkout's top-level listing happened to skip the bad tokens.
   **Fix:** derive the top-level set from tracked content (`git ls-files` top-level segments, or
   the committed tree) so an untracked scratch dir can neither mask nor manufacture a violation.
   Failing that, at minimum report the derived top-level set in the failure message so the
   discrepancy is diagnosable rather than looking like a flaky test. Keep the existing
   self-tests' `tmp_path` repos working (they are untracked by construction — the fix must not
   make the checker unusable outside a git repo).

---

## Explicitly deferred / out of scope

- **Ledger item 11 — the adapt phase claims an additive merge but performs wholesale
  replacement.** Mechanically verified downstream: 35 of 37 files came out byte-identical to
  upstream modulo blank lines, while per-file `change_summary` lines said things like "kept
  local's X" — and would have read identically whether or not local content was preserved,
  because nothing checks. The one genuinely local thing that survived did so because its file
  was excluded from the sync, not because merge logic protected it. The proposed fix (diff
  local-only lines against the adapted output, require the summary to account for any that
  disappeared) converts the skill's central promise from a self-report into a verified
  property — worth doing, but it is a design change to the adapt contract, not a defensive
  patch, and belongs in its own change.
- **`discover_tests.py`'s `package.json` premise.** The ledger files this under
  "correct upstream, inert downstream". It is not correct upstream: this repo is stdlib-Python
  only (plus one `node --test` script), so `discover()` returns empty here too and our own
  `spec-to-pr` Test phase reports a wrong skip reason. Real, but a separate change from porting
  the ledger.
- **`python3` vs `python` across the plugin** (129 occurrences in 53 files). A blind token swap
  breaks the other platform; the runtime path already resolves correctly
  (`dispatch-bash-pretooluse.py` tries `python3 || py || python`) and only the prose is wrong.
  The right fix is a stated convention — document the interpreter as platform-conditional, or
  standardize the docs on `uv run python` — which is its own decision.
- **Ledger item 15** — not applicable to this repo; see the grounding note at the top.

## Why this matters / next step

Every item here is a defect in the *process layer itself*, which means it is silently inherited
by every repo that syncs CLA. The P0 group is the sharp end: the repo's headline convention is
"no direct push to main", and today a two-command chain walks straight past the guard that
enforces it. The P1 group is the insidious end: values that are wrong rather than absent, read
by the orchestrator as legitimate negatives.

Feeds into a `/cla:multi-lite` run over the four candidates above, dependency-first.
