# Author prompts

Verbatim from the baseline run (2026-11-17), with machine-specific folder paths replaced by placeholders. Both arms ran on Opus. Variant A gets no guidance; variant B gets the lean principles brief. The real CLA output is not authored from a prompt here: it is what `/cla:multi-spec` produced from the decisions (see `README.md`). `<MNEMO_CLONE>` is a clone of mnemo, `<ARM_DIR>` the arm's scratch folder.

## Variant A: no guidance

````text
You are one arm of a controlled experiment. Work ONLY inside the scratch folder below. Never write to <MNEMO_CLONE>, never commit, never push, never touch GitHub. Never `cd` in Bash (a guard blocks it); use absolute paths, `git -C`, and run openspec with the scratch folder as working directory via PowerShell `Push-Location`/`Pop-Location`.

Setup:
1. Scratch root: <ARM_DIR>
2. Populate it with mnemo as it was before any proposals: `git -C <MNEMO_CLONE> archive 898ee67 | tar -x -C <scratch root>`. Then overwrite `cla.io/decisions/*.md` in the scratch copy with the current versions from <MNEMO_CLONE>/cla.io/decisions/ (they gained later owner decisions Q11–Q14).
3. In the scratch copy, replace `openspec/config.yaml` with just `schema: spec-driven` (no rules). Delete `.claude/rules/` from the scratch copy if present. Do not read CLA plugin files.

Task: using the openspec CLI (`openspec new change`, `openspec instructions <artifact> --change <name>`, `openspec validate <name> --strict`), author two OpenSpec changes from the decisions:
- `add-check-scripts` — scope: "conventions/ base schema, scripts/mnemo_check.py (links, schema, deletions, secrets, save; changed files only), unittest harness at repo root, version-equals-tag test". Decisions covered: architecture Q1, Q4, Q9, Q10, Q12–Q14; structure Q3, Q6, Q7, Q8, Q13, Q14 and the "Scaffold spec requirements" section.
- `add-mnemo-improve` — scope: "mnemo-improve skill: on-demand loop, provenance, [meta] PRs, targeted scorecard, gh api issue filing, deferred metadata". Decisions covered: recursive-self-improvement Q1–Q7, Q10; structure Q14.

Follow only OpenSpec's own instructions and your own judgement. No other guidance is given — that is the point of this arm.

Report (300 words max): the two change folders' paths; `openspec validate --strict` exit status for each; word counts (`wc -w`) of proposal, design, tasks, and total spec words; requirement count (`grep -c '### Requirement:'` across specs); capability count; time taken roughly. Do not summarise content — a judge will read the files.
````

## Variant B: lean principles brief

````text
You are one arm of a controlled experiment. Work ONLY inside the scratch folder below. Never write to <MNEMO_CLONE>, never commit, never push, never touch GitHub. Never `cd` in Bash (a guard blocks it); use absolute paths, `git -C`, and run openspec with the scratch folder as working directory via PowerShell `Push-Location`/`Pop-Location`.

Setup:
1. Scratch root: <ARM_DIR>
2. Populate it with mnemo as it was before any proposals: `git -C <MNEMO_CLONE> archive 898ee67 | tar -x -C <scratch root>`. Then overwrite `cla.io/decisions/*.md` in the scratch copy with the current versions from <MNEMO_CLONE>/cla.io/decisions/ (they gained later owner decisions Q11–Q14).
3. In the scratch copy, replace `openspec/config.yaml` with just `schema: spec-driven` (no rules). Delete `.claude/rules/` from the scratch copy if present. Do not read CLA plugin files.

Brief (this is the only guidance you get beyond OpenSpec's own instructions):
> You are writing OpenSpec change proposals for mnemo, a personal tool with one user (the owner), private repos, everything in git. Write for that audience. Specify what the decisions decided, in the owner's terms. Where a decision is silent on something the change truly needs, don't invent an answer: list it under "Open questions" in the proposal for the owner to settle. Specs state outcomes the owner would notice; how to build it is the implementer's call. Keep each change readable in a few minutes: a proposal under 400 words, a design only if a real choice needs recording, a handful of requirements. Prefer the simplest thing that meets the decision. Where you see a risk, name it in one line rather than designing machinery against it — except where a failure would lose or corrupt the owner's notes; specify those outcomes.

Task: using the openspec CLI (`openspec new change`, `openspec instructions <artifact> --change <name>`, `openspec validate <name> --strict`), author two OpenSpec changes from the decisions:
- `add-check-scripts` — scope: "conventions/ base schema, scripts/mnemo_check.py (links, schema, deletions, secrets, save; changed files only), unittest harness at repo root, version-equals-tag test". Decisions covered: architecture Q1, Q4, Q9, Q10, Q12–Q14; structure Q3, Q6, Q7, Q8, Q13, Q14 and the "Scaffold spec requirements" section.
- `add-mnemo-improve` — scope: "mnemo-improve skill: on-demand loop, provenance, [meta] PRs, targeted scorecard, gh api issue filing, deferred metadata". Decisions covered: recursive-self-improvement Q1–Q7, Q10; structure Q14.

Report (300 words max): the two change folders' paths; `openspec validate --strict` exit status for each; word counts (`wc -w`) of proposal, design, tasks, and total spec words; requirement count (`grep -c '### Requirement:'` across specs); capability count; the Open questions you listed. Do not summarise other content — a judge will read the files.
````
