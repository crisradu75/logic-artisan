"""Drift guard: a path the docs tell a CONSUMER to run must actually ship.

WHAT THIS CLOSES. Issue #264. Releases up to `cla--v0.10.0` shipped the plugin's
own pytest tree, and the guidance of that era told a consuming repo to wire
`<plugin>/conformance-checks/tests` into its local gate. The dev-tree extraction
moved that tree to `plugin-tests/`, which does not ship — so from `1.0.0` the
published plugin carries no test tree at all, and every consumer that followed
the documented wiring was left pointing at a directory that is not there. The
dangerous direction is the quiet one: a gate that resolves nothing and passes.

Nothing caught it because nothing compares the docs to the published tree. The
`${CLAUDE_PLUGIN_ROOT}` reference graph inside `SKILL.md`/`references/*.md` IS
checked (`tests/conformance/test_skill_lint.py`), but the four prose documents a
human actually reads on the way in — the plugin's own `README.md`, this repo's
`README.md`, `DEVELOPER-GUIDE.md` and `CLAUDE.md` — were unguarded, and the
plugin README is the one a consuming repo receives.

WHAT IT ASSERTS. `git ls-files` over the published directory is the definition of
"shipped" — the marketplace `git-subdir` source publishes the tracked tree
verbatim, with no exclusion field, which is the same derivation
`tests/conformance/test_shipped_files_are_scanned.py` uses. Two checks over it:

  1. Every plugin-relative path named in those four docs resolves in that tree,
     as a file or as a directory.
  2. The plugin README's Layout block lists only top-level entries that ship.
     A layout diagram is the one place a reader looks to find out what the
     release contains, and at `cla--v0.9.3` it named `conformance-checks/`.

WHICH TOKENS COUNT, and why the rule is derived rather than listed. A path counts
when it is in backticks AND either carries an explicit plugin prefix
(`${CLAUDE_PLUGIN_ROOT}/`, `<plugin>/`, `.claude/plugins/cla/`) or begins with a
top-level directory that EXISTS IN THE SHIPPED TREE AND NOWHERE AT THE REPO ROOT.
That second condition is load-bearing and measured, not defensive: `.claude-plugin/`
is both a shipped directory and a repo-root directory, and CLAUDE.md's
`.claude-plugin/marketplace.json` means the repo-root one. Without the condition
that line is a false failure. `plugin-tests/...` and `cla.io/...` never enter,
because neither is a shipped top-level name.

WHY IT IS A PYTEST GUARD AND DOES NOT SHIP. Its subject is this repository's own
documentation set and it needs `git ls-files` against this repository. A
consuming repo has neither.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PLUGIN_ROOT = _REPO_ROOT / ".claude" / "plugins" / "cla"
_PUBLISHED_PREFIX = ".claude/plugins/cla/"

# The four documents a consumer or a contributor reads on the way in. The plugin
# README is the only one that ships; the other three are how this repo describes
# the release to someone about to adopt it, and all four have carried a path that
# stopped existing.
_DOCS = {
    "plugin README.md": _PLUGIN_ROOT / "README.md",
    "README.md": _REPO_ROOT / "README.md",
    "DEVELOPER-GUIDE.md": _REPO_ROOT / "DEVELOPER-GUIDE.md",
    "CLAUDE.md": _REPO_ROOT / "CLAUDE.md",
}

_BACKTICKED = re.compile(r"`([^`\n]+)`")
_PLUGIN_PREFIX = re.compile(r"^(?:\$\{CLAUDE_PLUGIN_ROOT\}/|<plugin>/|\.claude/plugins/cla/)")
# A path-shaped token and nothing else: no spaces, no shell, no placeholder.
_PATH_SHAPED = re.compile(r"[A-Za-z0-9._][A-Za-z0-9._/-]*")

# Non-vacuity floors, ONE PER CHANNEL. Every check here is "everything extracted
# resolves", which is satisfied perfectly by extracting nothing — the exact shape
# of the defect this guard is about.
#
# A single total was measured to be too coarse to do that job: breaking the
# explicit-prefix pattern outright left 20+ bare `skills/…` hits, so the total
# stayed over its floor and the mutant survived. The three channels fail
# independently, so they are floored independently. Set below the counts they
# were measured at — 9 prefixed, 28 bare, 6 layout entries — and not at them, so
# an ordinary doc edit does not fail a guard whose subject is not doc size:
#
#   python3 -c "import importlib.util as u; \
#     s=u.spec_from_file_location('g','plugin-tests/tests/consistency/test_docs_name_shipped_paths.py'); \
#     m=u.module_from_spec(s); s.loader.exec_module(m); \
#     sh=m._tracked_shipped_paths(); b=m._bare_prefixes(sh); \
#     c={k:sum(len(m._named_paths(p.read_text(encoding='utf-8'),b)[k]) \
#        for p in m._DOCS.values()) for k in ('prefixed','bare')}; \
#     print(c, len(m._layout_top_level_entries()))"
_MIN_PREFIXED_PATHS = 5
_MIN_BARE_PATHS = 15
_MIN_LAYOUT_ENTRIES = 4


def _tracked_shipped_paths() -> frozenset[str]:
    """Every path the release contains, plugin-root-relative, files and the
    directories that hold them.

    `git ls-files` rather than a filesystem walk: the marketplace publishes the
    TRACKED tree, so an untracked scratch file is not shipped and a walk would
    say it was.
    """
    out = subprocess.run(
        ["git", "-C", str(_REPO_ROOT), "ls-files", _PUBLISHED_PREFIX.rstrip("/")],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
    )
    if out.returncode != 0:
        pytest.fail(f"`git ls-files` over the published tree failed: {out.stderr.strip()}")
    files = {
        line[len(_PUBLISHED_PREFIX):]
        for line in out.stdout.splitlines()
        if line.startswith(_PUBLISHED_PREFIX)
    }
    if not files:
        pytest.fail("`git ls-files` returned no shipped file — refusing to check against nothing")
    dirs = set()
    for f in files:
        parts = f.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]))
    return frozenset(files | dirs)


def _bare_prefixes(shipped: frozenset[str]) -> frozenset[str]:
    """Top-level shipped directories a doc may name WITHOUT a plugin prefix.

    Derived, and the exclusion is the whole point — see the module docstring.
    A name that also exists at the repo root is ambiguous in prose, so a bare
    mention of it is not read as plugin-relative at all.
    """
    top = {p.split("/")[0] for p in shipped if "/" in p}
    return frozenset(name for name in top if not (_REPO_ROOT / name).exists())


def _named_paths(text: str, bare_prefixes: frozenset[str]) -> dict[str, set[str]]:
    """Plugin-relative paths a document names, by channel, prefix stripped.

    BOTH SURFACES are read. Inline backticks are the prose one; FENCED BLOCKS are
    the other, and leaving them out was a measured hole rather than a theoretical
    one — the plugin README gives the two conformance programs as a shell block,
    which is precisely what a consumer copies into their own gate, and a mutant
    that swapped one of those lines for the retired `conformance-checks/tests`
    path survived a version of this guard that read only inline backticks.

    Two channels, because they break independently and each needs its own floor:
    `prefixed` carries an explicit `${CLAUDE_PLUGIN_ROOT}/`, `<plugin>/` or
    `.claude/plugins/cla/`; `bare` starts with an unambiguous shipped top-level
    directory (see `_bare_prefixes`). A bare token inside a fenced block is NOT
    accepted — a shell block's bare words are commands and arguments as often as
    paths, and the layout diagram's own entries are checked by their own test.
    """
    found: dict[str, set[str]] = {"prefixed": set(), "bare": set()}
    for raw in _BACKTICKED.findall(text):
        token = raw.strip()
        resolved = _classify(token, bare_prefixes)
        if resolved:
            channel, path = resolved
            found[channel].add(path)
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            continue
        for token in line.split():
            resolved = _classify(token, bare_prefixes)
            if resolved and resolved[0] == "prefixed":
                found["prefixed"].add(resolved[1])
    return found


def _classify(token: str, bare_prefixes: frozenset[str]):
    """`(channel, normalised path)` for a token that names a plugin path, else None."""
    stripped = _PLUGIN_PREFIX.sub("", token)
    explicit = stripped != token
    if not explicit and token.split("/")[0] not in bare_prefixes:
        return None
    if "/" not in stripped or "..." in stripped:
        return None
    if not _PATH_SHAPED.fullmatch(stripped):
        return None
    return ("prefixed" if explicit else "bare"), stripped.rstrip("/")


def _layout_top_level_entries() -> list[str]:
    """Top-level entries listed in the plugin README's `## Layout` code block.

    The block is a tree: `.claude/plugins/cla/` at column 0, its own children at
    indent 2, and a skill's children at indent 4. Only the indent-2 lines are
    plugin-root-relative, so only those are read. A `<name>` placeholder is
    truncated at the `<` (`skills/<name>/` -> `skills`), which keeps the entry
    checkable instead of skipping the largest directory in the tree.
    """
    lines = _DOCS["plugin README.md"].read_text(encoding="utf-8").splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == "## Layout")
    except StopIteration:
        pytest.fail("the plugin README has no `## Layout` heading — the block this guard reads is gone")
    fence = next((i for i in range(start, len(lines)) if lines[i].startswith("```")), None)
    if fence is None:
        pytest.fail("the plugin README's Layout section has no code block")
    entries = []
    for line in lines[fence + 1:]:
        if line.startswith("```"):
            break
        if not re.match(r"^ {2}\S", line):
            continue
        token = line.strip().split()[0].split("<")[0].rstrip("/")
        if token:
            entries.append(token)
    return entries


def test_every_plugin_path_named_in_the_docs_actually_ships():
    """A doc naming a path the release does not contain is issue #264's defect.

    Reported per document with the offending token, because the remedy differs:
    a moved file gets re-pointed, a retired one gets the prose rewritten.
    """
    shipped = _tracked_shipped_paths()
    bare = _bare_prefixes(shipped)
    counts = {"prefixed": 0, "bare": 0}
    failures = []
    for label, path in _DOCS.items():
        named = _named_paths(path.read_text(encoding="utf-8"), bare)
        for channel, tokens in named.items():
            counts[channel] += len(tokens)
            for token in sorted(tokens):
                if token not in shipped:
                    failures.append(
                        f"{label}: `{token}` is named as a plugin path but does not ship"
                    )
    for channel, floor in (("prefixed", _MIN_PREFIXED_PATHS), ("bare", _MIN_BARE_PATHS)):
        assert counts[channel] >= floor, (
            f"extracted only {counts[channel]} {channel} plugin paths across "
            f"{len(_DOCS)} docs (floor {floor}) — that half of the extraction has "
            "stopped matching how the docs write paths, so this guard is passing "
            "vacuously over it"
        )
    assert not failures, "\n".join(failures)


def test_the_plugin_readme_layout_lists_only_entries_that_ship():
    """The Layout block is where a reader looks to learn what the release holds.

    At `cla--v0.9.3` it listed `conformance-checks/`, and that line outlived the
    directory. Checked in the naming direction only — the block deliberately
    omits `README.md` (itself) and `.gitattributes` (plumbing), and forcing it to
    enumerate those would make it worse to read for no defect it prevents.
    """
    shipped = _tracked_shipped_paths()
    entries = _layout_top_level_entries()
    assert len(entries) >= _MIN_LAYOUT_ENTRIES, (
        f"read only {len(entries)} top-level entries from the Layout block "
        f"(floor {_MIN_LAYOUT_ENTRIES}) — the block's shape changed and this "
        "guard is no longer reading it"
    )
    missing = [e for e in entries if e not in shipped]
    assert not missing, (
        "the plugin README's Layout block lists entries the release does not "
        f"contain: {', '.join(missing)}"
    )
