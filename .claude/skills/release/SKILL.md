---
name: release
description: "Cut a new release of the cla plugin: verify the preconditions (on the default branch, clean tree, green test suite, work already reviewed and merged), bump the version in the plugin manifest, the marketplace catalog ref, and the CLAUDE.md release line in one commit, then cut the tag with `claude plugin tag`. Refuses rather than guesses when a precondition fails, and never moves a tag that has already been published. Triggers on /release or natural language like 'cut a release', 'publish a new version', 'tag 0.10.0', 'ship the plugin', 'bump the plugin version'."
argument-hint: "[major|minor|patch|<explicit version>] (default: ask)"
allowed-tools: Bash, Read, Edit, Grep, Glob, AskUserQuestion
---

# /release — publish a new version of the plugin

Cutting a release is a **three-file edit plus a tag**, and getting either half wrong is
expensive in a way ordinary mistakes are not: a published tag is what consumers have
already fetched, so it can never be corrected in place. This skill exists because that
procedure has been performed by hand on every release so far, and a hand-run procedure
with an irreversible last step is exactly the kind that earns automation.

## The invariant that governs everything here

**A published tag is never moved.** `0.9.0` was cut, a consumer installed it, and the
very next fix therefore became `0.9.1` rather than a re-tag — moving it would have
changed what that consumer had already fetched. If a release turns out to be wrong,
the answer is always the next version, never the same one again.

Two consequences this skill enforces rather than advises:

- Cut only from the default branch, and only from work that has been reviewed and
  merged. A tag on unreviewed work cannot be withdrawn.
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
pytest plugin-tests -q -n auto --dist loadfile
node --test plugin-tests/node/mechanical-checks.test.mjs
python3 .claude/skills/release/scripts/check_shipped_tree.py
```

| Precondition | Why it is not negotiable |
|---|---|
| On the repo's default branch | A tag cut from a feature branch pins commits that may never merge. |
| Working tree clean (`git status --porcelain` prints nothing) | An uncommitted edit is either in the release or it isn't; a dirty tree means nobody knows which. **Nothing is excluded, and nothing should be:** no pathspec, so the check covers the whole repo from any directory, and a half-resolved merge conflict shows up here too. The run ledgers under `cla.io/retro/` are written at a controlled moment and should be committed, not hidden. |
| Up to date with `origin` | Tagging a stale local branch publishes a tree that is not what `main` holds. |
| `pytest plugin-tests -q -n auto --dist loadfile` fully green | There is no CI. This run, plus the Node run below, is the whole gate that exists. |
| `node --test plugin-tests/node/mechanical-checks.test.mjs` fully green | the pytest gate does not reach it — `norecursedirs` excludes `node` — so a broken `mechanical-checks.mjs`, a SHIPPED file, ships behind an all-green pytest run without this line. Not hypothetical: commit `ee3e359` on `extract-dev-tree-from-plugin` fixed this suite failing with `ERR_MODULE_NOT_FOUND` while pytest stayed green throughout. |
| The work is reviewed and merged | See the invariant above. |
| `check_shipped_tree.py` exits 0 | `git-subdir` has no exclusion field, so a stray dev asset in the plugin tree ships to every consumer — and a published tag is never moved. |

Resolve the default branch, never assume it: `git symbolic-ref --quiet refs/remotes/origin/HEAD`
(take the segment after the last `/`); if unset, use whichever of `main` / `master`
exists.

## Step 2 — Choose the version

Read the current version from `.claude/plugins/cla/.claude-plugin/plugin.json`.

If `$ARGUMENTS` names a bump (`major` / `minor` / `patch`) or an explicit version, use
it. Otherwise ask with `AskUserQuestion`, showing what changed since the last tag
(`git log --oneline <last-tag>..HEAD`) so the choice is informed:

- **patch** — fixes and doc corrections only.
- **minor** — a skill added or removed, a new guard, a restructure consumers will notice.
- **major** — a change that breaks a consuming repo's existing usage.

While the line is `0.9.x`, it is the pre-1.0 validation line. It becomes `1.0.0` once a
real task has been run end-to-end through the plugin in a consuming repo — installing
and resolving paths is verified; running a task through it is the remaining gate.

## Step 3 — The three-file edit, in one commit

All three files must move together. A test fails when they disagree
(`plugin-tests/tests/consistency/test_marketplace_manifest.py`), and a third copy of the
version lives in `CLAUDE.md`'s "Current release" line, pinned by
`plugin-tests/tests/consistency/test_doc_facts.py`.

1. `.claude/plugins/cla/.claude-plugin/plugin.json` → `"version": "<new>"`
2. `.claude-plugin/marketplace.json` (repo root) → the plugin entry's
   `source.ref` → `"cla--v<new>"`
3. `CLAUDE.md` → `**Current release: `cla--v<new>`.**`

Then re-run the suite — the two manifest tests and the doc-fact test are what confirm
the three copies agree — and commit all three together:

**If `test_every_batch_is_loadable_and_declares_real_targets` goes red here, it is a
mutant batch anchored on the version literal, not a broken bump.** The anchor named in
the failure no longer appears, `mutate.py` aborts that whole batch in preflight, and the
guard reports it. Fix the batch, not the bump: anchor on the version-independent prefix
and inject a digit, as `mutants/consistency/test_doc_facts.py` and
`mutants/consistency/test_marketplace_manifest.py` both do. This step is the earliest
point it can be caught — at step 1 the version has not moved, so the anchors still
resolve — which is why it surfaces after the bump and before the tag.

**Branch BEFORE committing.** Step 1 put you on the default branch; committing there and
branching afterwards leaves the local default branch carrying a commit `origin` does not
have, and the `git pull` at the end of this step then refuses. Branch first and the
default branch never moves:

```bash
git checkout -b release/<new>
pytest plugin-tests -q -n auto --dist loadfile
node --test plugin-tests/node/mechanical-checks.test.mjs
python3 .claude/skills/release/scripts/check_shipped_tree.py
git add -- .claude/plugins/cla/.claude-plugin/plugin.json .claude-plugin/marketplace.json CLAUDE.md
git commit -m "release: <new>"
```

Path-scoped `git add`, never `-A`.

**The release commit reaches the default branch through a PR, not a push.** Push the
branch, open the PR, merge it, then return:

```bash
git push -u origin release/<new>
gh pr create --base <default-branch> --title "release: <new>" \
  --body "Version bump: <old> → <new>."
# merge it, then:
git checkout <default-branch> && git pull --ff-only
```

Pass `--body`: without it `gh pr create` opens an interactive editor, which in a
non-interactive session is a hang two steps before an irreversible action.

**Why a PR and not `git push`.** `hooks/git/pre-push` refuses a direct push to the default
branch. The hook's message names an `ALLOW_PUSH_TO_MAIN=1` override, and it is not the
answer here: that hatch is for a genuine emergency, and a release is a planned act, so
reaching for it is routing around a guard rather than complying with one. Earlier versions
of this skill said `git push` and were hand-run past the refusal every time.

Confirm the default branch carries the bump before tagging — the tag must point at the
merged commit, not at the branch.

## Step 4 — Cut the tag

**Pass the plugin directory.** Bare `claude plugin tag` looks for a manifest at the repo
root (`.claude-plugin/plugin.json`) and fails here with `No plugin manifest found` — this
repo's root `.claude-plugin/` holds `marketplace.json`, and the plugin's own manifest is
one level down. Dry-run first; it prints the exact git commands it will run, which is the
last cheap moment before an irreversible step:

```bash
claude plugin tag .claude/plugins/cla --dry-run
claude plugin tag .claude/plugins/cla --push
```

It uses the shape `<name>--v<version>` and **refuses unless `plugin.json` and the
marketplace entry already agree** — so a refusal here means step 3 is incomplete, not
that the tool is wrong. `--push` sends the tag to `origin`; without it, tag and push by
hand. Then confirm it resolves, and that it points where you think:

```bash
git ls-remote --tags origin cla--v<new>
git fetch origin && git merge-base --is-ancestor cla--v<new>^{} origin/<default-branch>
```

**An empty result from `git ls-remote` means the tag did not reach the remote**, and
consumers will get an install failure with nothing visibly wrong in the catalog. Treat
it as a failed release, not a cosmetic problem.

The second command asserts the tag is *on* the default branch — the property that actually
matters. Do not compare the two shas for equality instead: that breaks the moment any
unrelated PR merges between the release merge and the tag, turning a correct release into
an apparent failure. The `git fetch` is not optional, because step 1's fetch predates the
merge being checked.

## Step 5 — Report

State: the version cut, the three files bumped, the tag pushed and confirmed, and the
one command a consumer runs to pick it up (`/plugin marketplace update`). If any
precondition was waived — it should not have been — say so prominently.

## When NOT to use

- To fix a release that is already published. Cut the next version instead.
- To tag work sitting on a feature branch or an open PR.
- To bump a version without releasing it: the three-file edit exists to be atomic with
  the tag, and splitting them is what leaves the catalog advertising a tag that does
  not exist.
