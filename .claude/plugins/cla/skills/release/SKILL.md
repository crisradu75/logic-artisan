---
name: release
description: "Cut a new release of the cla plugin: verify the preconditions (on the default branch, clean tree, green test suite, work already reviewed and merged), bump the version in the plugin manifest AND the marketplace catalog ref in the same commit, then cut the tag with `claude plugin tag`. Refuses rather than guesses when a precondition fails, and never moves a tag that has already been published. Triggers on /cla:release or natural language like 'cut a release', 'publish a new version', 'tag 0.10.0', 'ship the plugin', 'bump the plugin version'."
argument-hint: "[major|minor|patch|<explicit version>] (default: ask)"
allowed-tools: Bash, Read, Edit, Grep, Glob, AskUserQuestion
---

# /cla:release — publish a new version of the plugin

Cutting a release is a **two-file edit plus a tag**, and getting either half wrong is
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
python3 ${CLAUDE_PLUGIN_ROOT}/run_tests.py
```

| Precondition | Why it is not negotiable |
|---|---|
| On the repo's default branch | A tag cut from a feature branch pins commits that may never merge. |
| Working tree clean | An uncommitted edit is either in the release or it isn't; a dirty tree means nobody knows which. |
| Up to date with `origin` | Tagging a stale local branch publishes a tree that is not what `main` holds. |
| `run_tests.py` fully green | There is no CI. This run is the only gate that exists. |
| The work is reviewed and merged | See the invariant above. |

Resolve the default branch, never assume it: `git symbolic-ref --quiet refs/remotes/origin/HEAD`
(take the segment after the last `/`); if unset, use whichever of `main` / `master`
exists.

## Step 2 — Choose the version

Read the current version from `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`.

If `$ARGUMENTS` names a bump (`major` / `minor` / `patch`) or an explicit version, use
it. Otherwise ask with `AskUserQuestion`, showing what changed since the last tag
(`git log --oneline <last-tag>..HEAD`) so the choice is informed:

- **patch** — fixes and doc corrections only.
- **minor** — a skill added or removed, a new guard, a restructure consumers will notice.
- **major** — a change that breaks a consuming repo's existing usage.

While the line is `0.9.x`, it is the pre-1.0 validation line. It becomes `1.0.0` once a
real task has been run end-to-end through the plugin in a consuming repo — installing
and resolving paths is verified; running a task through it is the remaining gate.

## Step 3 — The two-part edit, in one commit

Both files must move together. A test fails when they disagree
(`consistency-checks/tests/test_marketplace_manifest.py`), and a third copy of the
version lives in `CLAUDE.md`'s "Current release" line, pinned by
`consistency-checks/tests/test_doc_facts.py`.

1. `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json` → `"version": "<new>"`
2. `.claude-plugin/marketplace.json` (repo root) → the plugin entry's
   `source.ref` → `"cla--v<new>"`
3. `CLAUDE.md` → `**Current release: `cla--v<new>`.**`

Then re-run the suite — the two manifest tests and the doc-fact test are what confirm
the three copies agree — and commit all three together:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/run_tests.py
git add -- "${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json" .claude-plugin/marketplace.json CLAUDE.md
git commit -m "release: <new>"
git push
```

Path-scoped `git add`, never `-A`.

## Step 4 — Cut the tag

```bash
claude plugin tag
```

It uses the shape `<name>--v<version>` and **refuses unless `plugin.json` and the
marketplace entry already agree** — so a refusal here means step 3 is incomplete, not
that the tool is wrong. Push the tag, then confirm it resolves:

```bash
git push origin cla--v<new>
git ls-remote --tags origin cla--v<new>
```

An empty result from that last command means the tag did not reach the remote, and
consumers will get an install failure with nothing visibly wrong in the catalog. Treat
it as a failed release, not a cosmetic problem.

## Step 5 — Report

State: the version cut, the three files bumped, the tag pushed and confirmed, and the
one command a consumer runs to pick it up (`/plugin marketplace update`). If any
precondition was waived — it should not have been — say so prominently.

## When NOT to use

- To fix a release that is already published. Cut the next version instead.
- To tag work sitting on a feature branch or an open PR.
- To bump a version without releasing it: the two-file edit exists to be atomic with
  the tag, and splitting them is what leaves the catalog advertising a tag that does
  not exist.
