## Context

Stock trigger: **cross-cutting**. This file records only the decisions the proposal leaves open.

## Decisions

### Already-reviewed detection reads multi-spec's recorded verdict

multi-spec's review gate writes `openspec/changes/<name>/review.json` into every change it reviews, whatever the verdict, in the commit that applies its fixes. The record holds `verdict`, `all_applied` (every Critical and Important finding applied), `deferred` (each one not applied, with its reason), `artifacts` and `date`. `artifacts` is `git ls-files -s` over the change's staged files, `review.json` excluded, piped to `git hash-object --stdin`: one digest of exactly what was reviewed.

spec-to-pr skips the checklist pass only when all of these hold:

- the change directory has no uncommitted edits;
- the record parses, says `READY` or `FIX FIRST`, has `all_applied: true`, and has no deferred finding;
- the same digest, taken now, equals `artifacts`, so no file changed after the review.

Anything else, including no record or an unreadable one, means a full review. A full review takes each deferred finding as a known issue. A miss costs a review and never skips a check.

Inherited obligations and capability re-base rows still reach a skipped change through Step 2b.

What the skip gives up, accepted because issue #291 asks for one artifact review per change, not two:

- the claim re-check against code that changed after multi-spec's review;
- an independent review of the fixes multi-spec's gate applied. The gate re-validates them and checks them against the rejected alternatives, but nobody re-reads them.

A change multi-spec rated RETHINK, or one with a deferred Critical or Important finding, is no longer skipped: its record says so, and the deferred findings reach the full review. A batch merged with a merge commit is no longer reviewed twice: the digest does not depend on how the change was merged.

Why a content digest and not commit topology: comparing the last commit on the directory with the last commit on `review.json` fails open under a squash merge, which is how this repo merges multi-spec PRs (`d6c99ee`, `573c6bd`). An edit pushed to the proposals PR after its review lands in the same squash commit as the record, and the two hashes match. The digest compares content, so it holds under squash, merge commit, rebase and cherry-pick.

Named limits:

- The check trusts that a `review.json` came from multi-spec's gate. This holds by convention only. No code enforces it.
- A record whose verdict is wrong is trusted as written. The record is only as good as the gate that wrote it.
- The record keeps Critical and Important findings only. The review's `[Open]` rows, questions it could not settle, are not recorded, so a skipped change does not see them again.
- A record stays in the change after spec-to-pr reviews it in full, and is archived with it. It is multi-spec's history, not that review's result.

Why a separate file: OpenSpec 1.14.1 warns on an unknown `.openspec.yaml` key, and `openspec validate --strict` fails on that warning. Measured in a scratch copy: a `review:` key in `.openspec.yaml` failed `--strict` with "Unrecognized key name(s)"; a `review.json` beside the artifacts passed `--strict` and `openspec archive`, and archive carried it into the archived directory.

Rejected: keying on commit subjects, multi-spec's review-fix commit or the squash form of its PR title. A subject cannot say what the review concluded, so a RETHINK change or a deferred Critical skipped the second review, and a READY batch merged with a merge commit carried no matching subject and was reviewed twice. That was this change's first design; its own review found the gap.

### The resume probe reads OpenSpec's apply-start gate

The probe's rule is OpenSpec's own apply gate: apply blocks only on the `applyRequires` artifacts. Measured in a scratch copy: with no design.md, `isComplete` and `isPlanningComplete` are false, `applyRequires` is `["tasks"]`, and tasks is `done`. This keeps the field's existing meaning, which is that the artifacts are ready. Step 2's unticked-task count still decides whether Implement actually ran.

Rejected: only documenting that resume re-counts tasks. The probe would stay wrong for every change without design.md, so a resumed run would redo every phase after Implement. Also rejected: `openspec instructions apply --json` `state: "all_done"`. It would change the field's meaning to "tasks done" and add a second CLI call, and step 2 already covers that.

### cla-init seeds config only where OpenSpec is initialised, and never merges

`openspec/` absent means nothing is created, because `openspec init` owns that directory. `config.yml` counts as existing because OpenSpec reads `config.yaml` first, so a new `config.yaml` would hide it. `openspec init` writes `config.yaml` whenever neither exists, so printing is the common path, and a consuming repo gets the rules only when someone pastes them. That is the cost of never-clobber, which cla-init's live requirement makes absolute.

The seeding is an ADDED requirement. The live cla-init requirement scopes cla-init to `cla.io/` and says a fully-scaffolded re-run writes nothing, so it is carried forward whole as MODIFIED, with those two sentences widened to name the config file. OpenSpec's validator length-checks ADDED requirements only, so the long MODIFIED block passes `--strict`. Splitting the live spec is out of scope.

Rejected: creating `openspec/config.yaml` regardless, and appending to a file that has no `rules:` key.
