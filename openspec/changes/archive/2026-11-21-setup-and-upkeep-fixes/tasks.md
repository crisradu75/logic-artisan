# Tasks

## 1. Skills

- [x] 1.1 `save-permissions` saves `Read(<gitignore-style path>)`, saves no `Glob` path rule, scans only prompted-and-approved calls and saves Bash exact unless a wildcard is confirmed.
- [x] 1.2 `report-upstream` shows the draft and posts only on an explicit yes, before `gh issue comment` and `gh issue create`; a duplicate match shares a concrete detail and is shown to the user.
- [x] 1.3 `codify-learnings` shows each fix's before and after above the prompt and routes a bundled script of a shipped skill to `/cla:report-upstream`.

## 2. Tests

- [x] 2.1 requirement: permission-saving / A path rule uses the form that matches. A test reads the skill for the gitignore forms and for no `path:` or `Glob(path:` form.
- [x] 2.2 requirement: permission-saving / Only permissions approved at a prompt are collected. A test reads the step 1 text.
- [x] 2.3 requirement: upstream-reports / Nothing is posted before the user approves the text. A test checks the draft step precedes `gh issue create` and names both commands.
- [x] 2.4 requirement: upstream-reports / A known defect gets a comment, not a second issue. A test checks the concrete-detail and show-the-user clauses.
- [x] 2.5 requirement: session-learnings / One prompt before anything is written, and / A plugin fix goes upstream when the plugin is read-only. Tests check the before-and-after text sits above the prompt and the bundled-script routing.

## 3. Docs

- [x] 3.1 docs and spec map: `docs/rule-ledger.md` updated; DEVELOPER-GUIDE, README and the spec map none affected here: stale lines for the final PR are listed in its body.
