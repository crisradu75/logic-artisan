"""The release skill's preconditions, asserted rather than described.

`/cla:release` is prose, and prose is the right shape for most of it — reading
`git status`, choosing a bump, deciding whether the work is reviewed. But its last
step is irreversible: once a tag is pushed and a consumer installs it, that tag is
what they fetched and it can never be corrected in place. `0.9.0` proved that; the
next fix had to become `0.9.1`.

So the two facts the tag depends on are checked here rather than trusted to a
careful reading:

  1. The five copies of the version — the Claude `plugin.json`, the Copilot
     root `plugin.json`, both marketplace `ref`s, and `CLAUDE.md`'s release
     line — agree. `claude plugin tag` refuses when the Claude pair disagrees,
     but it never sees the rest, and a stale `CLAUDE.md` line is exactly what
     shipped before.
  2. The tag NAME the skill will cut matches the shape the tooling expects
     (`cla--v<version>`), derived from the manifests rather than hand-typed.

Deliberately NOT tested here: that the tree is clean, that the branch is the
default one, that the suite is green. Those are properties of a moment, not of the
repo, and a test asserting them would either be vacuous or fail every time someone
worked on a branch — which is most of the time.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# Three subjects in three different trees, so the repo root is resolved once and
# all three are derived from it. A single `parents[N]` cannot express this:
# `extract-dev-tree-from-plugin` left this test in the dev tree, its `SKILL.md`
# subject in the repo-local skills tree, and `plugin.json` in the published
# plugin. A "corrected depth" would have had to be three different depths.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PLUGIN_ROOT = _REPO_ROOT / ".claude" / "plugins" / "cla"

_PLUGIN_JSON = _PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
_MARKETPLACE_JSON = _REPO_ROOT / ".claude-plugin" / "marketplace.json"
# The GitHub Copilot CLI pair: an Agent Plugins 1.0 manifest at the plugin root
# and a catalog under .github/plugin/. Both carry the release version too.
_COPILOT_PLUGIN_JSON = _PLUGIN_ROOT / "plugin.json"
_COPILOT_MARKETPLACE_JSON = _REPO_ROOT / ".github" / "plugin" / "marketplace.json"
_SKILL_MD = _REPO_ROOT / ".claude" / "skills" / "release" / "SKILL.md"

TAG_SHAPE = re.compile(r"^cla--v(\d+\.\d+\.\d+)$")


def _plugin_version() -> str:
    return json.loads(_PLUGIN_JSON.read_text(encoding="utf-8"))["version"]


def _marketplace_ref() -> str:
    catalog = json.loads(_MARKETPLACE_JSON.read_text(encoding="utf-8"))
    entries = [p for p in catalog["plugins"] if p["name"] == "cla"]
    assert len(entries) == 1, f"expected exactly one `cla` entry, found {len(entries)}"
    return entries[0]["source"]["ref"]


def test_the_tag_the_release_would_cut_has_the_expected_shape():
    """`claude plugin tag` builds `<name>--v<version>`. If the ref ever stops
    matching that shape, the skill's `git push origin cla--v<new>` line pushes a
    tag nobody created."""
    ref = _marketplace_ref()
    match = TAG_SHAPE.match(ref)
    assert match, f"marketplace ref {ref!r} is not of the form `cla--v<x.y.z>`"
    assert match.group(1) == _plugin_version(), (
        f"marketplace ref {ref!r} pins version {match.group(1)}, "
        f"but plugin.json declares {_plugin_version()}"
    )


def _copilot_marketplace_ref() -> str:
    catalog = json.loads(_COPILOT_MARKETPLACE_JSON.read_text(encoding="utf-8"))
    entries = [p for p in catalog["plugins"] if p["name"] == "cla"]
    assert len(entries) == 1, f"expected exactly one `cla` entry, found {len(entries)}"
    return entries[0]["source"]["ref"]


def _release_versions() -> dict[str, str]:
    """The five places a release writes its version, keyed by file, each reduced
    to the bare `x.y.z` so a single comparison covers manifests and tag refs."""
    claude_md = (_REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    line = re.search(r"\*\*Current release: `cla--v([0-9.]+)`", claude_md)
    assert line, "CLAUDE.md no longer states a `**Current release: `cla--v<x>`**` line"

    def from_ref(ref: str) -> str:
        match = TAG_SHAPE.match(ref)
        # A ref that is not a release tag is reported as itself, so the
        # disagreement message shows the bad value rather than a parse error.
        return match.group(1) if match else ref

    return {
        ".claude-plugin/plugin.json": _plugin_version(),
        "plugin.json (Copilot)": json.loads(
            _COPILOT_PLUGIN_JSON.read_text(encoding="utf-8")
        )["version"],
        ".claude-plugin/marketplace.json": from_ref(_marketplace_ref()),
        ".github/plugin/marketplace.json": from_ref(_copilot_marketplace_ref()),
        "CLAUDE.md": line.group(1),
    }


# requirement: plugin-distribution / Publishing a release
def test_every_copy_of_the_version_agrees():
    """The precondition `claude plugin tag` cannot check: it compares two of the
    five copies and never reads the Copilot pair or CLAUDE.md. Every copy is
    named in the failure, so a half-finished bump shows which file it missed."""
    versions = _release_versions()
    assert len(set(versions.values())) == 1, (
        f"the release version disagrees across its files: {versions} — the release "
        "skill's step 3 bumps all five together for exactly this reason"
    )


def test_the_skill_names_every_file_its_own_procedure_bumps():
    """A release that edits four of the five files leaves a catalog advertising
    a version the prose contradicts. The skill's step 3 must keep naming all
    five, so this fails if one is ever dropped from the procedure."""
    body = _SKILL_MD.read_text(encoding="utf-8")
    # Only the numbered list: the `git add` line further down names the same
    # paths, so a whole-file search passes with a numbered step deleted.
    body = body.split("## Step 3", 1)[1].split("Then re-run the suite", 1)[0]
    for required in (
        ".claude-plugin/plugin.json",
        ".claude/plugins/cla/plugin.json",
        ".claude-plugin/marketplace.json",
        ".github/plugin/marketplace.json",
        "CLAUDE.md",
    ):
        assert required in body, (
            f"release/SKILL.md no longer names {required} — the five-file bump has "
            "silently become a partial bump"
        )


def _step_1_status_commands(body: str) -> list[str]:
    """Every `git status --porcelain` line in Step 1's command block."""
    step_1 = body.split("## Step 1", 1)[1].split("## Step 2", 1)[0]
    block = re.search(r"```bash\n(.*?)```", step_1, re.S)
    assert block, "release/SKILL.md Step 1 no longer opens with a bash command block"
    return [
        line.strip() for line in block.group(1).splitlines()
        if line.strip().startswith("git status --porcelain")
    ]


def test_the_clean_tree_check_excludes_nothing():
    """Any exclusion lets an uncommitted edit ride into a tag, and any pathspec
    at all narrows the check — `.` to the current directory, an exclusion to
    everything but one file, and an excluded file also hides a half-resolved
    merge conflict in it. Step 1's check is the bare command, whole repo."""
    commands = _step_1_status_commands(_SKILL_MD.read_text(encoding="utf-8"))
    assert len(commands) == 1, f"expected one porcelain check in Step 1, found {commands}"
    assert commands[0] == "git status --porcelain", (
        f"Step 1's clean-tree check {commands[0]!r} carries a pathspec or an "
        "exclusion, either of which can only narrow it"
    )


def test_the_status_command_parser_is_not_vacuous():
    body = "## Step 1\n```bash\ngit status --porcelain -- .\ngit fetch\n```\n## Step 2\n"
    assert _step_1_status_commands(body) == ["git status --porcelain -- ."]


# requirement: plugin-distribution / Publishing a release
def test_the_skill_states_the_never_move_invariant():
    """The one rule whose violation cannot be undone. If it is ever edited out of
    the skill, the skill has stopped being safe to run."""
    body = _SKILL_MD.read_text(encoding="utf-8")

    # A substring search anywhere in the file is NOT this assertion. Measured:
    # `never move` occurs three times — the frontmatter `description:`, the
    # normative statement, and a precondition-table cell — so rewriting the
    # normative one to "may be moved when convenient" left the other two alive
    # and the old `"never move" in body` check green. A mutant caught it; no
    # amount of reading would have. Pin the emphasized statement itself.
    assert "**A published tag is never moved.**" in body, (
        "release/SKILL.md no longer carries the emphasized invariant "
        '"**A published tag is never moved.**" as its own statement. Other '
        "mentions of the phrase elsewhere in the file do not substitute for it: "
        "this is the rule whose breach cannot be undone."
    )


def test_the_precondition_block_names_every_command_the_documented_gate_runs():
    """CLAUDE.md's "Before opening a PR" row is this repo's own statement of what
    the shipping gate consists of — currently two commands, `pytest plugin-tests`
    and `openspec validate --specs --strict` over the live specs. The guard was
    written when a third, a `node --test` run `pytest` could not reach, had
    silently dropped out of the tag gate (commit `ee3e359` on
    `extract-dev-tree-from-plugin`); that suite was deleted with the one Node
    script it tested, and the failure shape — the doc's gate and the release
    preconditions drifting apart — is unchanged.

    Derived from CLAUDE.md rather than hardcoded, so a future change to what
    "before opening a PR" runs is what this test forces release/SKILL.md to
    follow, instead of letting the two drift apart silently again."""
    claude_md = (_REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    match = re.search(r"\|\s*Before opening a PR\s*\|(.+)\|\s*\n", claude_md)
    assert match, "CLAUDE.md no longer states a 'Before opening a PR' gate row"
    gate_commands = re.findall(r"`([^`]+)`", match.group(1))
    assert gate_commands, (
        "no `command` spans found in CLAUDE.md's 'Before opening a PR' row — "
        "the gate can no longer be read out of the doc"
    )

    body = _SKILL_MD.read_text(encoding="utf-8")
    assert "## Step 1" in body, "release/SKILL.md no longer has a Step 1 section"
    assert "## Step 2" in body, (
        "release/SKILL.md no longer has a Step 2 heading — without it the Step 1 "
        "slice below runs to end of file and swallows Step 3's re-run block, "
        "which repeats these same commands, so Step 1 could lose one entirely "
        "and this test would still pass"
    )
    step1 = body.split("## Step 1", 1)[1].split("## Step 2", 1)[0]

    # Match against the RUNNABLE block, not the whole section. Step 1 also holds
    # a precondition TABLE that names both commands in backticks, so searching
    # the section made this test satisfiable by the prose describing the gate
    # rather than by the gate. Measured: deleting both commands from the fenced
    # bash block left this test passing.
    blocks = re.findall(r"```(?:bash|sh)?\n(.*?)```", step1, re.S)
    assert blocks, "release/SKILL.md's Step 1 has no fenced command block to run"
    runnable = "\n".join(blocks)
    missing = [cmd for cmd in gate_commands if cmd not in runnable]
    assert not missing, (
        f"release/SKILL.md's Step 1 preconditions do not run: {missing} — "
        "CLAUDE.md's documented shipping gate and the release skill's "
        "preconditions have drifted apart, exactly the drop this test exists "
        "to catch"
    )


def _bash_lines(section: str) -> list[str]:
    """The command lines of a section's fenced bash blocks, in document order."""
    blocks = re.findall(r"```bash\n(.*?)```", section, re.S)
    return [line.strip() for block in blocks for line in block.splitlines() if line.strip()]


def _section(body: str, start: str, end: str) -> str:
    assert start in body and end in body, f"release/SKILL.md lost {start!r} or {end!r}"
    return body.split(start, 1)[1].split(end, 1)[0]


# requirement: plugin-distribution / A release is tagged before its catalogs name it
def test_the_skill_tags_the_release_pr_before_merging_it_with_a_merge_commit():
    """The order closes the window 2.0.0 and 2.4.0 fell into: merged first, the
    catalogs named a tag `origin` did not have until someone pushed it by hand.
    Tag the PR's head, prove the tag is on `origin`, then merge with a merge commit
    so the tagged commit itself is on the default branch. A squash or rebase merge
    writes a new commit, and the tag would point off the branch."""
    body = _SKILL_MD.read_text(encoding="utf-8")
    step_3 = _bash_lines(_section(body, "## Step 3", "## Step 4"))
    assert not [l for l in step_3 if l.startswith("gh pr merge")], (
        "Step 3 merges the release PR before Step 4 tags it")
    step_4 = _bash_lines(_section(body, "## Step 4", "## Step 5"))

    def first(prefix: str) -> int:
        hits = [i for i, line in enumerate(step_4) if line.startswith(prefix)]
        assert hits, f"Step 4 no longer runs `{prefix}`"
        return hits[0]

    mergeable = first("gh pr view release/<new> --json mergeable,mergeStateStatus")
    tag = first("claude plugin tag .claude/plugins/cla --push")
    assert mergeable < tag, (
        "Step 4 must check the PR can merge before the tag push uses up the version")
    proof = first("python3 .claude/skills/release/scripts/check_catalog_tags.py --expect cla--v<new>")
    merge = first("gh pr merge")
    assert tag < proof < merge, (
        "Step 4 must push the tag, prove it is on origin, and only then merge the PR")
    merges = [line for line in step_4 if line.startswith("gh pr merge")]
    assert len(merges) == 1, f"expected one merge command in Step 4, found {merges}"
    assert " --merge " in f"{merges[0]} ", f"the release PR is not merged with --merge: {merges[0]}"
    assert "--match-head-commit" in merges[0], (
        "the merge is not pinned to the tagged commit, so a head that moved after the "
        "tag would merge an untagged commit")
    for flag in ("--squash", "--rebase", "-s ", "-r "):
        assert flag not in f"{merges[0]} ", f"the release PR merge carries {flag.strip()}"
    # The tagged commit has to reach the default branch: the ancestry check runs
    # after the merge, not before.
    assert first("git fetch origin && git merge-base --is-ancestor cla--v<new>^{}") > merge


# requirement: plugin-distribution / A release is tagged before its catalogs name it
def test_the_skill_restarts_as_a_new_version_when_the_tagged_pr_needs_a_commit():
    body = _SKILL_MD.read_text(encoding="utf-8")
    step_4 = " ".join(_section(body, "## Step 4", "## Step 5").split())
    assert "**`--merge`, never `--squash` or `--rebase`, for a release PR.**" in step_4
    assert "**If the PR needs another commit after the tag is pushed**" in step_4
    assert "the release restarts as a new version" in step_4
    assert "**If the tag push fails, stop and do not merge.**" in step_4
    assert "and `mergeStateStatus` is `CLEAN`" in step_4 and "stop before tagging" in step_4


# requirement: plugin-distribution / A release is tagged before its catalogs name it
def test_the_skill_expects_the_merge_prompt_and_restarts_on_a_no():
    """`ask-destructive-git` asks before `gh pr merge` unless `ALLOW_PR_MERGE=1`
    prefixes it, so the skill cannot promise the merge runs unasked. A no comes
    after the tag is published, so it costs the version."""
    body = _SKILL_MD.read_text(encoding="utf-8")
    flat = " ".join(body.split())
    assert "no second question" not in flat, (
        "the skill promises no further prompt, but the merge guard asks")
    step_2 = " ".join(_section(body, "## Step 2", "## Step 3").split())
    assert "`ask-destructive-git` asks the user before Step 4's `gh pr merge`" in step_2
    step_4 = " ".join(_section(body, "## Step 4", "## Step 5").split())
    assert "`ask-destructive-git` asks the user before this command unless `ALLOW_PR_MERGE=1`" in step_4
    assert "**If the user says no, do not merge.**" in step_4
    assert "restart at the next patch version" in step_4

