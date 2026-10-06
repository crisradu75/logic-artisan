## Context

Stock trigger: **cross-cutting**. This file records only the decisions the proposal leaves open.

## Decisions

### Already-reviewed detection reads the change directory's last commit

spec-to-pr skips the checklist pass when the change directory has no uncommitted edits and the last commit touching it (`git log -1 --format=%s -- openspec/changes/<name>/`) is one of:

- `docs(openspec): apply review fixes to <slug> proposals`, which multi-spec writes after its review gate; or
- `docs(openspec): <N> <slug> change proposals (#<pr>)`, the squash-merge form of multi-spec's PR title, **and** the last commit on that PR (`gh pr view <pr> --json commits`) is multi-spec's review-fix commit or its `docs(openspec): propose ` commit. Without the second check, an edit pushed to the proposals PR after its review would be squashed in unseen.

Anything else, including `gh` failing, means a full review. A miss costs a review and never skips a check.

Inherited obligations and capability re-base rows still reach a skipped change through Step 2b.

What the skip gives up, accepted because issue #291 asks for one artifact review per change, not two:

- the claim re-check against code that changed after multi-spec's review;
- an independent review of the fixes in multi-spec's review-fix commit, which its gate applies without re-reviewing;
- a finding multi-spec's gate noted out of scope, or a change it graded RETHINK. Nothing carries these to spec-to-pr, so they are not re-raised.

Named limits:

- The check trusts that a commit with one of multi-spec's subjects came from multi-spec. This holds by convention only. No code enforces it.
- The squash-form check reads only the PR's last commit.
- Two cases always miss the skip and get a full review: a single-commit PR squash-merged under that commit's own subject, and a batch reviewed READY and merged with a merge commit, where the last commit touching the change is multi-spec's `docs(openspec): propose <name>`. Each costs a review and never skips one.

Rejected: keying on the review-fix commit alone. This repo squash-merges multi-spec PRs (`d6c99ee`, `573c6bd`), so that commit does not survive, and a batch reviewed READY never writes one. Also rejected: a marker file in the change directory, which would add an artifact to every package.

### The resume probe reads OpenSpec's apply-start gate

The probe's rule is OpenSpec's own apply gate: apply blocks only on the `applyRequires` artifacts. Measured in a scratch copy: with no design.md, `isComplete` and `isPlanningComplete` are false, `applyRequires` is `["tasks"]`, and tasks is `done`. This keeps the field's existing meaning, which is that the artifacts are ready. Step 2's unticked-task count still decides whether Implement actually ran.

Rejected: only documenting that resume re-counts tasks. The probe would stay wrong for every change without design.md, so a resumed run would redo every phase after Implement. Also rejected: `openspec instructions apply --json` `state: "all_done"`. It would change the field's meaning to "tasks done" and add a second CLI call, and step 2 already covers that.

### cla-init seeds config only where OpenSpec is initialised, and never merges

`openspec/` absent means nothing is created, because `openspec init` owns that directory. `config.yml` counts as existing because OpenSpec reads `config.yaml` first, so a new `config.yaml` would hide it. `openspec init` writes `config.yaml` whenever neither exists, so printing is the common path, and a consuming repo gets the rules only when someone pastes them. That is the cost of never-clobber, which cla-init's live requirement makes absolute.

The seeding is an ADDED requirement. The live cla-init requirement scopes cla-init to `cla.io/` and says a fully-scaffolded re-run writes nothing, so it is carried forward whole as MODIFIED, with those two sentences widened to name the config file. OpenSpec's validator length-checks ADDED requirements only, so the long MODIFIED block passes `--strict`. Splitting the live spec is out of scope.

Rejected: creating `openspec/config.yaml` regardless, and appending to a file that has no `rules:` key.
