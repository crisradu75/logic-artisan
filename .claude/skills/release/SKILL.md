---
name: release
description: "Cut a new release of the cla plugin: verify the preconditions (on the default branch, clean tree, green test suite, work already reviewed and merged), bump the version in the two plugin manifests, the two marketplace catalog refs, and the CLAUDE.md release line in one commit on a release PR, cut the tag on that PR's head commit with `claude plugin tag`, then merge the PR with a merge commit. Refuses rather than guesses when a precondition fails, and never moves a tag that has already been published. Triggers on /release or natural language like 'cut a release', 'publish a new version', 'tag a version', 'ship the plugin', 'bump the plugin version'."
argument-hint: "[major|minor|patch|<explicit version>] (default: ask)"
allowed-tools: Bash, Read, Edit, Grep, Glob, AskUserQuestion
---

# /release — publish a new version of the plugin

Cutting a release is a **five-file edit plus a tag**, and getting either half wrong is
expensive in a way ordinary mistakes are not: a published tag is what consumers have
already fetched, so it can never be corrected in place.

## The invariant that governs everything here

**A published tag is never moved.** A consumer that installed a tag has fetched that tree,
and moving the tag would change it under them. If a release turns out to be wrong, the
answer is always the next version, never the same one again.

Two consequences this skill enforces rather than advises:

- Start only from the default branch, and only from work that has been reviewed and
  merged. A tag on unreviewed work cannot be withdrawn. The tag goes on the release
  commit, whose only change over that reviewed branch is the version bump, and the
  release PR is merged with a merge commit so the tagged commit itself lands on it.
- Tag before merging. The merge is what makes the catalogs name the new tag, so the tag
  is on `origin` first and the catalogs never name a tag that is missing.
- Never publish from a local-directory marketplace. The catalog is then read from a
  working tree, so a locally-bumped `ref` advertises a tag that may never have been
  pushed — the install fails with nothing visibly wrong in the manifest.

## Step 1 — Preconditions (all must hold; refuse otherwise)

Run these and read every result before proposing anything. If any fails, **stop and
say which one** — do not offer to proceed anyway, and do not "fix" a precondition as
part of the release.

```bash
git rev-parse --abbrev-ref HEAD
git status --porcelain
git fetch origin
git status -sb
pytest plugin-tests -q -n 4 --dist loadfile
openspec validate --specs --strict
python3 .claude/skills/release/scripts/check_shipped_tree.py
python3 .claude/skills/release/scripts/check_copilot_models.py
python3 .claude/skills/release/scripts/check_catalog_tags.py
```

| Precondition | Why it is not negotiable |
|---|---|
| On the repo's default branch | The release branch starts here. A tag on any other branch pins commits that may never merge; the release commit's only parent is this reviewed branch. |
| Working tree clean (`git status --porcelain` prints nothing) | An uncommitted edit is either in the release or it isn't; a dirty tree means nobody knows which. **Nothing is excluded, and nothing should be:** no pathspec, so the check covers the whole repo from any directory, and a half-resolved merge conflict shows up here too. The run ledgers under `cla.io/retro/` are written at a controlled moment and should be committed, not hidden. |
| Up to date with `origin` | Tagging a stale local branch publishes a tree that is not what `main` holds. |
| `pytest plugin-tests -q -n 4 --dist loadfile` fully green | There is no CI. This run, plus the spec validation below, is the whole gate that exists. |
| `openspec validate --specs --strict` passes with no warning | It is the second command in CLAUDE.md's "Before opening a PR" gate, so the OpenSpec CLI is now a release precondition: without it on `PATH` this step fails and no tag is cut. |
| The work is reviewed and merged | See the invariant above. |
| The docs match the code since the last tag | Re-check every count and present-tense claim in `README.md`, `DEVELOPER-GUIDE.md` and `.claude/plugins/cla/README.md` against `git log <last-tag>..HEAD`, and fix them in a PR first. A release that ships stale counts needs a docs PR after it. |
| `check_shipped_tree.py` exits 0 | `git-subdir` has no exclusion field, so a stray dev asset in the plugin tree ships to every consumer — and a published tag is never moved. |
| `check_copilot_models.py` exits 0 | It verifies generated Copilot agent copies stay in step with their Claude sources and inherit the session model instead of pinning account-specific IDs. A source model alias without a defined inheritance policy, a stale profile, or an explicit Copilot model refuses the release. It is local-only; exit 2 means the sources could not be checked. Fix the source alias policy and regenerate the copies in a PR first, never as part of the release. |
| `check_catalog_tags.py` exits 0 | Every `ref` in both catalogs names a tag `origin` has. Exit 1 means an earlier release was merged but its tag never reached `origin`, so every consuming repo's `marketplace update` is failing now: stop, and have the owner push that tag from its merged release commit before any new version. Exit 2 means `origin` could not be asked, which is not a pass. |

Resolve the default branch, never assume it: `git symbolic-ref --quiet refs/remotes/origin/HEAD`
(take the segment after the last `/`); if unset, use whichever of `main` / `master`
exists.

## Step 2 — Choose the version and ask once

Read the current version from `.claude/plugins/cla/.claude-plugin/plugin.json`.

Propose a version. If `$ARGUMENTS` names a bump (`major` / `minor` / `patch`) or an explicit
version, propose that. Otherwise propose the bump the changes call for:

- **patch** — fixes and doc corrections only.
- **minor** — a skill added or removed, a new guard, a restructure consumers will notice.
- **major** — a change that breaks a consuming repo's existing usage.

**This is the release's only question.** Call `AskUserQuestion` one time, before any file is
edited, any branch is made or anything is pushed. It shows:

- the proposed version, with the patch, minor and major alternatives as the other options, and a
  last option "Don't release";
- the output of `git log --oneline <last-tag>..HEAD`;
- the `CHANGELOG.md` section that will move under the new version heading (the `[Unreleased]`
  entries, or the entry Step 3 will write from that log when `[Unreleased]` is empty).

Choosing a version approves the release at that version. "Don't release", or any other answer,
stops: nothing is edited,
branched, pushed, merged or tagged. Once a version is chosen, Step 3 and Step 4 run with no second
question, including the merge and the tag push.

## Step 3 — The five-file edit, in one commit

All five files must move together. One test fails when they disagree
(`test_every_copy_of_the_version_agrees` in
`plugin-tests/tests/skills/release/test_release_preconditions.py`, which names every file and
the version it holds). The Claude pair is also pinned by
`plugin-tests/tests/consistency/test_marketplace_manifest.py`, and `CLAUDE.md`'s "Current
release" line by `plugin-tests/tests/consistency/test_doc_facts.py`. `claude plugin tag` in
Step 4 compares only the Claude pair, so the two GitHub Copilot CLI files are held by the test alone.

1. `.claude/plugins/cla/.claude-plugin/plugin.json` → `"version": "<new>"`
2. `.claude/plugins/cla/plugin.json` (the Copilot CLI manifest, at the plugin root) →
   `"version": "<new>"`
3. `.claude-plugin/marketplace.json` (repo root) → the plugin entry's
   `source.ref` → `"cla--v<new>"`
4. `.github/plugin/marketplace.json` (the Copilot CLI catalog) → the plugin entry's
   `source.ref` → `"cla--v<new>"`
5. `CLAUDE.md` → `**Current release: `cla--v<new>`.**`

**The changelog goes in the same commit, though it is not one of the five.** In `CHANGELOG.md`,
turn `## [Unreleased]` into `## [<new>] — <date>` and leave an empty `## [Unreleased]` above it. If
`[Unreleased]` is empty, write the entry from `git log --oneline <last-tag>..HEAD`: one line per
change a consumer notices, with its PR number, under Added, Changed or Fixed. No test pins the
changelog, so this step is the only thing that keeps it current.

Then re-run the suite — the version-agreement test, the two manifest tests and the doc-fact
test are what confirm the five copies agree — and commit the five files plus `CHANGELOG.md` together:

**Branch BEFORE committing.** Step 1 put you on the default branch; committing there and
branching afterwards leaves the local default branch carrying a commit `origin` does not
have, and the `git pull` when Step 4 returns to it then refuses. Branch first and the
default branch never moves:

```bash
git checkout -b release/<new>
pytest plugin-tests -q -n 4 --dist loadfile
openspec validate --specs --strict
python3 .claude/skills/release/scripts/check_shipped_tree.py
git add -- .claude/plugins/cla/.claude-plugin/plugin.json .claude/plugins/cla/plugin.json .claude-plugin/marketplace.json .github/plugin/marketplace.json CLAUDE.md CHANGELOG.md
git commit -m "release: <new>"
```

Path-scoped `git add`, never `-A`.

**The release commit reaches the default branch through a PR, not a push.** Push the
branch and open the PR. Do not merge it yet: Step 4 tags its head commit first.

```bash
git push -u origin release/<new>
gh pr create --base <default-branch> --head release/<new> --title "release: <new>" \
  --body "Version bump: <old> → <new>."
```

Pass `--body`: without it `gh pr create` opens an interactive editor, which in a
non-interactive session is a hang two steps before an irreversible action.

**Why a PR and not `git push`.** `hooks/git/pre-push` refuses a direct push to the default
branch. The hook's message names an `ALLOW_PUSH_TO_MAIN=1` override, and it is not the
answer here: that hatch is for a genuine emergency, and a release is a planned act, so
reaching for it is routing around a guard rather than complying with one.

## Step 4 — Tag the PR's head, then merge it with a merge commit

**The order is the point: tag first, merge second.** The merge is what makes the
default branch's catalogs name `cla--v<new>`. With the tag already on `origin`, there is
no moment when a consumer's `marketplace update` fetches a missing tag. The old order
(merge, then tag the merged commit) left that window open whenever the tag push failed,
and 2.0.0 and 2.4.0 both sat merged and untagged until the owner pushed the tag by hand.

**1. Tag the release commit, the PR's head.** Stay on `release/<new>`. The two shas
below must be equal; if they differ, the branch you are on is not what the PR will
merge, so stop. Then dry-run, which prints the exact git commands it will run, the last
cheap moment before an irreversible step:

```bash
git rev-parse HEAD
gh pr view release/<new> --json headRefOid --jq .headRefOid
claude plugin tag .claude/plugins/cla --dry-run
claude plugin tag .claude/plugins/cla --push
python3 .claude/skills/release/scripts/check_catalog_tags.py --expect cla--v<new>
```

**Pass the plugin directory.** Bare `claude plugin tag` looks for a manifest at the repo
root (`.claude-plugin/plugin.json`) and fails here with `No plugin manifest found`: this
repo's root `.claude-plugin/` holds `marketplace.json`, and the plugin's own manifest is
one level down. It tags `HEAD` with the shape `<name>--v<version>` on any branch, and
**refuses unless `plugin.json` and the marketplace entry already agree**, which they do
on the release commit; so a refusal here means Step 3 is incomplete, not that the tool
is wrong. `--push` sends the tag to `origin`.

On the release branch the working tree's catalogs already name `cla--v<new>`, so
`check_catalog_tags.py --expect cla--v<new>` passes as soon as the tag is on `origin`,
and fails before. Do not merge until it exits 0.

**If the tag push fails, stop and do not merge.** A cloud session's credentials push
only its own branch, so a tag push there returns HTTP 403. Nothing is published: the
default branch's catalogs still name the previous tag. Leave the PR open, hand the owner
this step's commands and the merge below, and report the release as not done.

**2. Merge the PR with a merge commit, pinned to the tagged commit.** Step 2's answer
already approved it:

```bash
gh pr merge release/<new> --merge --match-head-commit "$(git rev-parse 'cla--v<new>^{commit}')"
```

**`--merge`, never `--squash` or `--rebase`, for a release PR.** Both write a new commit
on the default branch, so the tagged commit would never be on it, and the
`merge-base --is-ancestor` check below fails on a tag that points off the branch.
`--match-head-commit` makes GitHub refuse the merge if the PR's head is no longer the
tagged commit.

**If the PR needs another commit after the tag is pushed** (a conflict, a review
change, a refused merge, a head that moved), the release restarts as a new version.
Do not add the commit to this PR and do not move the tag: **a published tag is never
moved**, even one the catalogs never named. Close the PR without merging
(`gh pr close release/<new>`), leave `cla--v<new>` where it is, and start again at
Step 1 with the next patch version; that release's changelog entry says `<new>` was
tagged but never released. `hooks/git/pre-push` refuses a tag delete or move, and its
`ALLOW_TAG_REWRITE=1` override is not part of a release.

**3. Return to the default branch and confirm.**

```bash
git checkout <default-branch> && git pull --ff-only
python3 .claude/skills/release/scripts/check_catalog_tags.py --expect cla--v<new>
git fetch origin && git merge-base --is-ancestor cla--v<new>^{} origin/<default-branch>
```

**This is the release's postcondition: the release is not done until
`check_catalog_tags.py` exits 0.** It asks `origin` for its tags and fails on every
catalog `ref` that names one `origin` lacks. A tag that exists only in the local clone
counts as missing, because a consumer cannot fetch it. `--expect` also fails a
catalog still naming the old tag, so a checkout that was not pulled cannot pass on the
previous release. Exit 1 means the tag did not reach
the remote, and consumers get an install failure with nothing visibly wrong in the
catalog: push the tag (never a different commit under the same name) and re-run it.
Exit 2 means `origin` could not be asked, which proves nothing. Treat either as a failed
release, not a cosmetic problem, and do not go on to Step 5's success report.

The last command asserts the tag is *on* the default branch — the property that actually
matters, and the one a squash merge breaks. Do not compare the tag's sha with the default
branch's head instead: the merge commit always sits above the tagged commit, and any
unrelated PR merged since moves the head further, turning a correct release into an
apparent failure. The `git fetch` is not optional, because Step 1's fetch predates the
merge being checked.

## Step 5 — Report

Report success only after Step 4's `check_catalog_tags.py` exited 0. If it did not, report
the release as not done, with its output and the commands still to run.

State: the version cut, the five files bumped plus `CHANGELOG.md`, the tag pushed and confirmed, and the
commands a consumer runs to pick it up (`claude plugin marketplace update cris-logic-artisan`, then
`claude plugin update cla@cris-logic-artisan` and a restart, for Claude Code; for
GitHub Copilot CLI, which is untested, `copilot plugin marketplace update` then
`copilot plugin update cla`). If any
precondition was waived — it should not have been — say so prominently.

## When NOT to use

- To fix a release that is already published. Cut the next version instead.
- To tag work sitting on a feature branch or an open PR. The one PR this skill tags is
  its own release PR, whose only change is the version bump.
- To bump a version without releasing it: the five-file edit exists to be atomic with
  the tag, and splitting them is what leaves the catalog advertising a tag that does
  not exist.
