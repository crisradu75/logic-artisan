# Plugin and skill analyzers — 2026-11-21

Triage only — no fixes applied here. Source: one `plugin-dev:plugin-validator` run over
`.claude/plugins/cla/`, and four `plugin-dev:skill-reviewer` runs covering all 19 shipped skills
(Sonnet, read-only), on `main` at `28eb40aa`. Items already decided in
`cla.io/decisions/warp-patterns-adoption-2026-11-21.md` were excluded.

Paths are under `.claude/plugins/cla/skills/` unless they say otherwise.

**Severity:**
- **blocking**: a skill misfires, misleads, contradicts itself, points at something missing, or
  breaks a repo rule.
- **improvement**: it works but is worse than it should be.
- **nit**: minor.

**Verified:**
- **✔**: the main session re-read the cited lines and they support the finding.
- **~**: re-read; the finding holds in a weaker form than reported, and the severity was lowered.
- **·**: reported by the analyzer and not re-read.

## Plugin structure (validator)

`claude plugin validate .claude/plugins/cla` printed "Validation passed": 6 hooks, 19 skills,
2 agents, 2 output styles. Every hook command uses `${CLAUDE_PLUGIN_ROOT}`, and every script it
names exists. The Copilot hooks and agents are complete. Both marketplace catalogs pin
`cla--v2.5.0`.

- **improvement ✔** `output-styles/COPILOT.md:1-5` is a doc to copy into a consuming repo's
  `.github/copilot-instructions.md`, with no frontmatter. Claude Code still counts it as a second
  output style. Fix: move it out of `output-styles/`, for example to `com.github.copilot/`.
- **nit ·** `.claude-plugin/plugin.json` has no `icon` or `network.hosts`. This matters only for
  a submission to the plugin directory.

## PR path

- **blocking ✔** `multi-lite/SKILL.md:28`: "lite is the default path, and such a change belongs
  on `spec-to-pr`". In context, "such a change" reads as the non-protected batch the sentence
  just described, which reverses the routing at `:18`. Fix: "a change that touches a protected
  area belongs on `spec-to-pr`; multi-lite flags it out of scope."
- **blocking ✔** `right-model/SKILL.md:66-67`: "`multi-pr` never dispatches an `Agent`
  itself". This contradicts `multi-pr/SKILL.md:44`, which delegates bulk work, and `:36`, which
  backgrounds `Agent` calls. Fix: "multi-pr runs whole spec-to-pr runs; its own helper dispatches
  are not routed per `model-routing.md`." The line uses `never`, so its rule-ledger entry needs
  checking.
- **improvement ·** `lite-pr/SKILL.md:134,185` list the only stops, but `:144` adds an
  `AskUserQuestion` halt on a non-zero `git_state` exit. Fix: add it to both lists.
- **improvement ·** `lite-pr/SKILL.md:3`: the description spends its length on review mechanics.
  Fix: lead with "default path; use spec-to-pr for a protected area or behaviour shipped to other
  repos", and cut the rest.
- **improvement ·** `lite-pr/SKILL.md:77-92,125-132,158`: two long essays, plus a reviewer
  paragraph of about 450 words that `model-routing.md` "Review sizing by risk" already owns. Fix:
  move them to `references/` with one-line pointers. Keep the verbatim diff-review sentence.
- **improvement ·** `multi-lite/SKILL.md:37` repeats `multi-pr/SKILL.md:36`, the no-idle-turn
  and watchdog text, almost word for word. Fix: one shared reference that both skills point to.
- **improvement ·** `multi-pr/SKILL.md:36` is one paragraph of about 500 words. Fix: move the
  closed blocker list (a–f) and the reaped-command retry to `references/change-loop.md`.
- **improvement ·** `multi-pr/SKILL.md:85-86` restates `change-loop.md` steps 2 and 4a. `:86`
  names `scripts/check_cite_drift.py`, which the References list (`:104-112`) omits.
- **improvement ·** `right-model/SKILL.md:70-72`: "an in-prompt reasoning keyword… Check the
  real keyword" names neither. Fix: point to where it is documented, or drop the paragraph.
- **nit ·** `right-model/SKILL.md:80` cites a bare `model-routing.md`. Use the
  `${CLAUDE_PLUGIN_ROOT}` path.
- **nit ·** `multi-pr/SKILL.md:77` points to "§1c step 4", but §1c is titled "Upfront chain-time
  estimate" (`discover-and-gate.md:153`).
- **nit ·** `multi-pr/SKILL.md:36,101` and `multi-lite/SKILL.md:106` carry history ("lost 4.5
  hours", a deleted ledger) or a confusing clause. Fix: keep the rule, drop the story.
- **nit ·** `lite-pr/SKILL.md:179,189` repeat scope text, and `:201-202` omit the five
  `references/` files.

## Spec path

- **blocking ✔** `multi-spec/SKILL.md:86`: "same 'wait for enough runs' posture noted above".
  No such text exists in the file; this line is the only match. Fix: delete the clause.
- **improvement ✔** `spec-to-pr/SKILL.md:121` and `review-change/SKILL.md:22` say "12
  high-yield verification checks (`0a`–`0l`)". `review-change/references/checklist.md:52`
  reserves `0f`–`0i` for overlays. Fix: say "the high-yield checks".
- **improvement ✔** `review-change/references/checklist.md:42-48`: generic checks are worded
  for one stack: "TypeScript function… React component", "an i18n JSON", the key
  `dashboard.example.label`, "wire a UI component to shared state". Fix: reword in
  language-neutral terms, and leave stack examples to an overlay.
- **improvement ·** `spec-to-pr/SKILL.md:175-183` vs `:39,46,86,189`: the Autonomy exception
  list omits the `git_state` non-zero halt and the precheck three-path ask. Fix: add both.
- **improvement ·** `spec-to-pr/SKILL.md:161` puts the post-Archive full gate in Test, against
  the phase order at `:12`. Fix: move it to Handoff's gate rules.
- **improvement ·** `spec-to-pr/SKILL.md` is about 4.5k words. Fix: move the `<pr-base>` and
  `<inherits>` detail (`:29,31`) and Implement step 4 (`:140-147`) to `references/`.
- **improvement ·** `multi-spec/SKILL.md:29` repeats spec-to-pr's no-idle-turn rule with an
  anecdote, and `:62` restates model routing, though `:94` says routing is not forked. Fix:
  point to `model-routing.md`.
- **nit ·** `spec-to-pr/SKILL.md:14` vs `:218`: `past-offenses.md` is filed under two
  different read conditions. `:218` omits `blocking-findings.md`, `test-quality.md` and
  `orchestration-economy.md`.
- **nit ·** `review-change/SKILL.md:12` overstates which files spec-to-pr reads directly, and
  `:3` doesn't say the skill only reports.
- **nit ·** `spec-to-pr-retro/SKILL.md:32-34` says "first rule that matches" for two rules, one
  of them "otherwise". `:24` vs `:27`: make clear the under-five stop applies to
  `runs_analyzed`.

## Setup and upkeep (these write the user's own files, a protected area)

- **blocking ✔** `report-upstream/SKILL.md:68-108` comments on or opens an issue in a public
  repo (`:71`, `:106`), and no step shows the user the title and body first. The body can carry
  session detail. Fix: show the draft and get a yes before `gh issue comment` or
  `gh issue create`.
- **blocking ✔** `codify-learnings/SKILL.md:71` forbids proposing edits to a skill's bundled
  scripts (`**/scripts/**/*.py`). `references/routing.md:57` routes "any plugin script" to edit
  or report-upstream, and `routing.md:13` makes a script the top rung for a re-offense. Fix: make
  `:71` route a bundled script to report-upstream, not ban it.
- **blocking ✔** `save-permissions/SKILL.md:20,26` writes `Read(path:/prefix/**)` and
  `Glob(path:/prefix/**)`. The Claude Code permissions page
  (https://code.claude.com/docs/en/permissions.md, "Read and Edit" and "How path patterns
  match") says a file tool's path field can't be matched by name. The valid forms use gitignore
  syntax: `Read(//abs/**)`, `Read(~/…)`, `Read(/project-rel/**)`, `Read(./rel)`. A `Glob(...)` or
  `Grep(...)` path rule is accepted but never matches; `Read(...)` rules cover them. So every rule
  the skill saves in these forms is dead. Fix: save `Read(<gitignore-style path>)`, and drop the
  `Glob(path:…)` line.
- **improvement ~** `save-permissions/SKILL.md:19` suggests `Bash(*)` as a save form, while
  `:41` requires confirmation for any wildcard. Step 4 does gate it, so nothing unsafe is
  written. Fix: state in step 1 that Bash entries are saved exact unless the user confirms a
  wildcard.
- **improvement ·** `save-permissions/SKILL.md:18` scans calls "approved by the user", which
  includes auto-allowed calls that were never prompted. Fix: say which it means.
- **improvement ~** `report-upstream/SKILL.md:54-56`: the code block holds only a comment. The
  prose at `:52` does say to read the manifest. Fix: replace the block with "read `repository`
  from `.claude-plugin/plugin.json` under the plugin root".
- **improvement ·** `report-upstream` never resolves the plugin root, which step 1
  (`:42-44`) needs. Fix: add the `plugin-root.md` pointer the other skills carry.
- **improvement ·** `codify-learnings/SKILL.md:101` says to prepend "above its first `## `
  entry", but the seeded lessons file (`cla-setup/SKILL.md:140-144`) has none. Fix: add "or
  after the title when none exists".
- **improvement ·** `cla-setup/SKILL.md:263` runs `check_fact_paths.py` without the
  `--root`/guard idiom used at `:68` and `:279`.
- **improvement ·** `cla-setup/SKILL.md:23` says to install the `pre-push` hook but never says
  how or from where.
- **improvement ·** `new-worktree/SKILL.md:93-99` hardcodes the destination `"<app-dir>/.env"`
  while the source is `<env-file-path>`. Fix: use `<env-file-path>` on both sides.
- **improvement ·** `new-worktree/SKILL.md:102-125`: speculation about `.worktreeinclude` and
  hedging about install flags, with no step attached. Fix: cut it, or move it to `references/`.
- **nit ·** `cla-setup/SKILL.md:25,100,255` restate the never-clobber exceptions listed at
  `:89-91`. `codify-learnings/SKILL.md:18` uses "before the move" as jargon.
  `report-upstream/SKILL.md:3` uses "synced skill", which is unexplained.
  `new-worktree/SKILL.md:10-16,28`: history, and a paragraph that belongs in `path-casing.md`.

## Utility skills

- **blocking ✔** `feedback/SKILL.md:38,46` uses words specific to another project: "the
  Recharts-crash entry", "Assistant rail", "Clients screen", "Charts (Planning/Buying)".
  `check_no_project_tokens.py` didn't catch them. This breaks "keep facts out of the shipped
  plugin". Fix: generic examples. Also find out why the checker missed these words.
- **blocking ✔** `diagnose/SKILL.md:150-152` (Phase 5) accepts a dated "no seam" finding as
  done, but Phase 6's "Done when" (`:185-186`) needs a passing regression test. A valid Phase 5
  outcome can then never finish. Fix: Phase 6 accepts the finding in place of the test. The
  round-2 decision (Q13) already routes the "no seam" case to the `Checks:` line inside lite-pr,
  so keep the two consistent.
- **improvement ✔** `annotate/SKILL.md:3`: the description says "Never edits the source", but
  `Edit` is allowed (`:5`) and §4 does edit, after the reading pass (`:27-31`). Fix: "never edits
  the source while comments are being collected".
- **improvement ·** `annotate/SKILL.md:3,81`: the trigger 'let me review change X as a block'
  is close to review-change's triggers. The description does say "Not a pre-implementation
  review". Fix: drop "review" from the trigger.
- **improvement ·** `annotate/SKILL.md:60-78,172-203`: the HTML conditions and the coverage view
  are about 40% of the file. Fix: move them to `references/`. `:188-190` quote sweep figures
  (51%, 22%, 355 changes). Under CLAUDE.md check 3, cite the command or drop the figures.
- **improvement ·** `feedback/SKILL.md:61` calls the read-only promise "mechanically backed",
  but `Write` is allowed (`:5`). Fix: soften the claim.
- **improvement ·** `checkpoint/SKILL.md:3` has no "resume from checkpoint" trigger, though
  `:79-84` covers resuming. `:35-48` never lists worktrees. Fix: add the trigger and
  `git worktree list`.
- **improvement ·** `diagnose/SKILL.md:3` lacks the triggers 'bug', 'regression', 'flaky' and
  'test keeps failing'.
- **improvement ·** `project-review/SKILL.md:3` doesn't say it reviews the whole repo, not one
  change.
- **improvement ·** `shape-decision/SKILL.md:47`: "These enter at Partial" is ambiguous. `:3`
  omits the output (`cla.io/decisions`).
- **nit ·** `diagnose/references/strategies.md:108-118` (ask the user) vs unattended mode
  (`SKILL.md:40-43`). `diagnose/SKILL.md:134-144` gives no filename for the finding.
  `shape-decision/SKILL.md:18` waits for a reply in an unattended run, and `:8` has no H1.
  `checkpoint/SKILL.md:47` has no `gh` fallback. `project-review/references/aggregate-and-log.md:26`
  is titled "and log" but persists nothing. `project-review/SKILL.md:20` carries a legacy
  migration sentence. `annotate/SKILL.md:106` vs `:212-219` differ in plugin-root notation.

## Counts

- Blocking: 8, all confirmed: seven by re-reading the files, and save-permissions against the
  Claude Code docs. Four more the analyzers called blocking were lowered to improvements after
  re-reading: save-permissions' `Bash(*)`, the report-upstream code block, and both annotate
  findings.
- Improvements: about 30.
- Nits: about 20.

Every blocking item touches a shipped skill, which is a protected area, so it goes through
`/cla:spec-to-pr`, or `/cla:lite-pr` where you say so.
