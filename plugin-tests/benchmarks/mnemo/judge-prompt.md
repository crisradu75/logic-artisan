# Judge prompt

Verbatim from the baseline run (2026-11-17). Only machine-specific folder paths are replaced by placeholders: `<MNEMO_CLONE>` is a clone of mnemo with the files in `inputs/` at their `cla.io/` paths, `<EXP_DIR>` is the folder holding the blinded versions as `blind/{X,Y,Z}/<change>/`, and `<NOTES_DIR>` is a scratch folder for the judge's notes. Run it on an Opus agent with no other context. Blind the versions first: copy each version's two change folders to X, Y and Z in a random order, and keep the key aside.

````text
Read-only judging task. Write nothing anywhere except optional notes under <NOTES_DIR>/. Do not read anything else under <EXP_DIR>/ except the blind folder named below. Do not run git on mnemo-plugin.

You are judging three independently written versions (X, Y, Z) of the same two OpenSpec change proposals for "mnemo", a personal note-taking ("AI recall second brain") tool with ONE user, the owner, storing Markdown notes in private git repos and used from Claude Code sessions (phone, web, laptop). You are not told how each version was produced; judge only what is on the page.

Inputs:
- The owner's decisions (the source of truth): <MNEMO_CLONE>/cla.io/decisions/plugin-architecture-2026-11-16.md, plugin-structure-2026-11-16.md, recursive-self-improvement-2026-11-16.md. Read all three fully first.
- Scope of the two changes:
  - add-check-scripts — "conventions/ base schema, scripts/mnemo_check.py (links, schema, deletions, secrets, save; changed files only), unittest harness at repo root, version-equals-tag test". Covers architecture Q1, Q4, Q9, Q10, Q12–Q14; structure Q3, Q6, Q7, Q8, Q13, Q14 and the "Scaffold spec requirements" section.
  - add-mnemo-improve — "on-demand loop, provenance, [meta] PRs, targeted scorecard, gh api issue filing, deferred metadata". Covers recursive-self-improvement Q1–Q7, Q10; structure Q14.
- The versions: <EXP_DIR>/blind/{X,Y,Z}\{add-check-scripts,add-mnemo-improve}\ (proposal.md, design.md if any, tasks.md, specs/*/spec.md). Read every file of all three.

Score each version on each change, 1–5 with evidence (file:line quotes):
1. **Faithfulness** — every decision in scope is represented correctly. List each decision missed or contradicted.
2. **Invention** — content no decision asked for. Count roughly; give 3 examples each; classify each example as valuable (protects the owner's notes or a stated goal), neutral, or harmful (cost/complexity with no benefit for one user, or overrides an owner choice).
3. **Gap handling** — where the decisions are silent on something the change truly needs, does the version (a) invent an answer silently, (b) invent and flag it, or (c) ask the owner? Is that the right call for each?
4. **Critical outcomes** — for each, say covered / raised as an open question / missing:
   a. a commit that could not be pushed (cloud VM reclaimed) is not silently lost;
   b. a pull/rebase conflict during save never loses or discards the owner's uncommitted note changes (incl. stashed changes);
   c. a hung save/hook is time-bounded;
   d. a failed check commits nothing;
   e. a secret-scan hit blocks the commit and does not fall back to inbox/;
   f. the improve loop's scoring does not change or consume the query log it learns from;
   g. a test question added for a fix is not scored against a base where the fix doesn't exist yet;
   h. a commit left unpushed on a clean tree is retried by a later save.
   For any outcome whose full coverage would contradict a decision, "kept the decision and raised the conflict as an open question with a proposed fix" counts as covered.
5. **Reviewability** — could the owner read and approve each change in ~15 minutes? Word counts (`wc -w`) per file.
6. **Implementability** — could a competent implementer build it without guessing on anything that matters for one user?

Then: overall ranking with a 5-line justification, and the single biggest weakness of each version. Be adversarial toward all three equally; do not reward length or brevity for its own sake. Report 700 words max plus one score table.
````
