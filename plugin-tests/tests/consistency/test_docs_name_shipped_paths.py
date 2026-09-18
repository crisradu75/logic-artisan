"""Drift guard: a path the docs tell a CONSUMER to run must actually ship.

WHAT THIS CLOSES. Issue #264. Releases up to `cla--v0.10.0` shipped the plugin's
own pytest tree, and the guidance of that era told a consuming repo to wire its
`conformance-checks/tests` directory into that repo's local gate. The dev-tree
extraction moved that tree to `plugin-tests/`, which does not ship — so from
`1.0.0` the published plugin carries no test tree at all, and every consumer that
followed the documented wiring was left pointing at a directory that is not
there. The dangerous direction is the quiet one: a gate that resolves nothing and
passes.

Nothing caught it because nothing compares the docs to the published tree. The
`${CLAUDE_PLUGIN_ROOT}` reference graph inside `SKILL.md`/`references/*.md` IS
checked (`tests/conformance/test_skill_lint.py`), but the four prose documents a
human actually reads on the way in — the plugin's own `README.md`, this repo's
`README.md`, `DEVELOPER-GUIDE.md` and `CLAUDE.md` — were unguarded, and the
plugin README is the one a consuming repo receives.

WHAT "SHIPPED" MEANS. `git ls-files` over the published directory — the
marketplace `git-subdir` source publishes the tracked tree verbatim, with no
exclusion field, the same derivation
`tests/conformance/test_shipped_files_are_scanned.py` uses.

THE HARD PART, AND THE FIRST VERSION OF THIS GUARD GOT IT WRONG. A bare
reference — `conformance-checks/tests`, with no `<plugin>/` in front of it — is
the spelling the defect ACTUALLY shipped in. At `cla--v0.10.0` three of the four
documents guarded here wrote it bare (`CLAUDE.md:74`, `DEVELOPER-GUIDE.md:315`,
plugin `README.md:135`); only files this guard does not cover used the
`${CLAUDE_PLUGIN_ROOT}/` form. A rule that recognises a bare token by asking
whether its first segment is a CURRENTLY shipped top-level directory can never
see one, because removal is precisely what takes a name out of that set. The
guard would have been green through the whole defect.

Two candidate fixes were measured rather than reasoned about:

  * *"A bare path must resolve somewhere — plugin tree or repo."* Measured over
    the four docs: **63 false positives**. This repo's own conventions write
    paths relative to several implicit roots — skill-relative
    (`annotate/scripts/render_doc.py`, a convention CLAUDE.md states outright),
    dev-tree-relative (`tests/conformance`), `cla.io`-relative (`decisions`,
    `retro`). Unusable, and rejected on the measurement.
  * *Derive the RETIRED names from the published tags.* `git tag --list
    'cla--v*'` over 10 tags yields 6 top-level entries that shipped once and ship
    no longer: `conformance-checks`, `consistency-checks`, `launcher-checks`,
    `mutate.py`, `run_tests.py`, `.cla-sync-lock.json`. Nothing is hand-written,
    it self-maintains (the next release that drops a directory adds it to the set
    at its own tag), and it is exactly right about what a consumer may still be
    carrying — a tag is what they installed.

So a bare token is read as a plugin path when its first segment is a shipped
top-level entry OR a retired one, and a retired one then fails by construction.

WHICH TOKENS COUNT. A path counts when it appears in backticks or in a fenced
block, AND either carries an explicit plugin prefix (`${CLAUDE_PLUGIN_ROOT}/`,
`<plugin>/`, `.claude/plugins/cla/`) or begins with one of those top-level names.
A bare token inside a fenced block is NOT accepted — a shell block's bare words
are commands as often as paths — but the tree diagrams get their own check below.

The bare set excludes a name that ALSO exists at the repo root, which is
load-bearing and measured rather than defensive: `.claude-plugin/` is both a
shipped directory and a repo-root directory, and `CLAUDE.md`'s
`.claude-plugin/marketplace.json` means the repo-root catalog. Without the
exclusion that line is a false failure.

WHY IT IS A PYTEST GUARD AND DOES NOT SHIP. Its subject is this repository's own
documentation set and it needs `git ls-files` and `git tag` against this
repository. A consuming repo has neither.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PLUGIN_ROOT = _REPO_ROOT / ".claude" / "plugins" / "cla"
_PUBLISHED_PREFIX = ".claude/plugins/cla/"
_RELEASE_TAG_GLOB = "cla--v*"

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

# Naming a retired path is sometimes the POINT — a migration note that does not
# name what it is migrating from is useless to the repo carrying that wiring. So
# this is the pressure valve, in the shape `test_shipped_files_are_scanned.py`'s
# `EXEMPT` uses: keyed on (document, exact path), each with its reason, and
# STALENESS CUTS BOTH WAYS — an entry whose document no longer names the path
# fails too, so a note that gets deleted takes its exemption with it.
#
# Keep it short and argued. An entry here is a claim that the surrounding prose
# tells the reader the path is GONE; it is not a way to keep a live instruction
# pointing at a directory that does not exist.
_RETIREMENT_NOTES: dict[tuple[str, str], str] = {
    ("plugin README.md", "conformance-checks/tests"): (
        "the migration blockquote in the Testing section, naming what a 0.x-era "
        "gate must stop pointing at"
    ),
    ("DEVELOPER-GUIDE.md", "conformance-checks/tests"): (
        "the same migration note in the §10 adoption steps"
    ),
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
# stayed over its floor and the mutant survived. The channels fail
# independently, so they are floored independently. Set below the counts they
# were measured at — 10 prefixed, 30 bare, 6 retired names, 22 tree entries
# across 3 diagrams — and not at them, so an ordinary doc edit does not fail a
# guard whose subject is not doc size. The command behind those four numbers:
#
#   python3 -c "import importlib.util as u; \
#     s=u.spec_from_file_location('g','plugin-tests/tests/consistency/test_docs_name_shipped_paths.py'); \
#     m=u.module_from_spec(s); s.loader.exec_module(m); \
#     sh=m._tracked_shipped_paths(); b=m._bare_prefixes(sh); \
#     c={k:sum(len(m._named_paths(p.read_text(encoding='utf-8'),b)[k]) \
#        for p in m._DOCS.values()) for k in ('prefixed','bare')}; \
#     print(c, len(m._retired_top_level_names()), \
#           sum(len(v) for v in m._published_tree_entries().values()))"
_MIN_PREFIXED_PATHS = 5
_MIN_BARE_PATHS = 15
_MIN_RETIRED_NAMES = 4
_MIN_TREE_ENTRIES = 12


def _git(*args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(_REPO_ROOT), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
    )
    if out.returncode != 0:
        pytest.fail(f"`git {' '.join(args)}` failed: {out.stderr.strip()}")
    return out.stdout


def _with_parent_dirs(files: set[str]) -> set[str]:
    out = set(files)
    for f in files:
        parts = f.split("/")
        for i in range(1, len(parts)):
            out.add("/".join(parts[:i]))
    return out


def _tracked_shipped_paths() -> frozenset[str]:
    """Every path the release contains, plugin-root-relative, files and dirs.

    `git ls-files` rather than a filesystem walk: the marketplace publishes the
    TRACKED tree, so an untracked scratch file is not shipped and a walk would
    say it was.
    """
    files = {
        line[len(_PUBLISHED_PREFIX):]
        for line in _git("ls-files", _PUBLISHED_PREFIX.rstrip("/")).splitlines()
        if line.startswith(_PUBLISHED_PREFIX)
    }
    if not files:
        pytest.fail("`git ls-files` returned no shipped file — refusing to check against nothing")
    return frozenset(_with_parent_dirs(files))


def _retired_top_level_names() -> frozenset[str]:
    """Top-level entries that a PUBLISHED release carried and the tree no longer
    does.

    This is the set a bare reference in old guidance can still name, and the only
    reason such a reference is recognisable at all — see the module docstring.
    Derived from the release tags because a tag is what a consuming repo actually
    installed; nothing here is maintained by hand.
    """
    current = {
        line[len(_PUBLISHED_PREFIX):].split("/")[0]
        for line in _git("ls-files", _PUBLISHED_PREFIX.rstrip("/")).splitlines()
        if line.startswith(_PUBLISHED_PREFIX)
    }
    retired: set[str] = set()
    for tag in _git("tag", "--list", _RELEASE_TAG_GLOB).split():
        names = {
            line[len(_PUBLISHED_PREFIX):].split("/")[0]
            for line in _git(
                "ls-tree", "-r", "--name-only", tag, "--", _PUBLISHED_PREFIX.rstrip("/")
            ).splitlines()
            if line.startswith(_PUBLISHED_PREFIX)
        }
        retired |= names - current
    return frozenset(retired)


def _bare_prefixes(shipped: frozenset[str]) -> frozenset[str]:
    """Top-level names a doc may write WITHOUT a plugin prefix and still mean the
    plugin: the shipped ones plus the retired ones.

    The repo-root exclusion applies to both halves and is the whole reason
    `.claude-plugin/marketplace.json` is not a false failure — see the docstring.
    """
    top = {p.split("/")[0] for p in shipped if "/" in p}
    return frozenset(
        name
        for name in top | _retired_top_level_names()
        if not (_REPO_ROOT / name).exists()
    )


def _classify(token: str, bare_prefixes: frozenset[str]):
    """`(channel, normalised path)` for a token naming a plugin path, else None.

    The "must contain a separator" test runs against the token AS WRITTEN when a
    plugin prefix is present, and against the stripped remainder otherwise. That
    asymmetry is deliberate: `${CLAUDE_PLUGIN_ROOT}/conformance-checks` and
    `<plugin>/mutate.py` are unambiguous plugin references whose remainder has no
    separator left, and testing the stripped form dropped exactly the
    single-segment retired entries — the two runners and the three `*-checks/`
    scopes — that old guidance names.
    """
    stripped = _PLUGIN_PREFIX.sub("", token)
    explicit = stripped != token
    if not explicit and token.split("/")[0] not in bare_prefixes:
        return None
    if "/" not in (token if explicit else stripped):
        return None
    if "..." in stripped or "*" in stripped:
        return None
    if not _PATH_SHAPED.fullmatch(stripped):
        return None
    return ("prefixed" if explicit else "bare"), stripped.rstrip("/")


def _named_paths(text: str, bare_prefixes: frozenset[str]) -> dict[str, set[str]]:
    """Plugin-relative paths a document names, by channel, prefix stripped.

    BOTH SURFACES are read. Inline backticks are the prose one; FENCED BLOCKS are
    the other, and leaving them out was a measured hole rather than a theoretical
    one — the plugin README gives the two conformance programs as a shell block,
    which is precisely what a consumer copies into their gate, and a mutant that
    swapped one of those lines for the retired `conformance-checks/tests` path
    survived a version of this guard that read only inline backticks.

    Two channels, because they break independently and each needs its own floor:
    `prefixed` carries an explicit plugin prefix; `bare` starts with a top-level
    name from `_bare_prefixes`. A bare token inside a fenced block is NOT
    accepted — a shell block's bare words are commands and arguments as often as
    paths, and the tree diagrams have their own check.
    """
    found: dict[str, set[str]] = {"prefixed": set(), "bare": set()}
    for raw in _BACKTICKED.findall(text):
        resolved = _classify(raw.strip(), bare_prefixes)
        if resolved:
            found[resolved[0]].add(resolved[1])
    for line in _fenced_lines(text):
        for token in line.split():
            resolved = _classify(token, bare_prefixes)
            if resolved and resolved[0] == "prefixed":
                found["prefixed"].add(resolved[1])
    return found


def _fenced_lines(text: str):
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            yield line


def _published_tree_entries() -> dict[str, list[str]]:
    """Per document, the plugin-root-relative entries its published-tree diagram
    lists.

    A tree diagram is where a reader looks to learn what a release contains, and
    it is the literal location of the historic defect in TWO documents — the root
    `README.md:57` and the plugin `README.md:165` both listed
    `conformance-checks/` at `cla--v0.10.0`. The bare tokens inside a fenced
    block are deliberately not read by `_named_paths`, so without this the
    diagrams are unchecked.

    Recognised structurally rather than by heading, because the three documents
    that carry such a block title their sections differently: inside a fenced
    block, find the line whose first token is `.claude/plugins/cla/` at column 0,
    then take the entries indented exactly two spaces under it. That is the
    published half of a diagram that may also list repo-root trees above it —
    `plugin-tests/`, `cla.io/` and friends are outside the block by construction
    rather than by exclusion.

    A `<name>` placeholder is truncated at the `<` (`skills/<name>/` -> `skills`),
    which keeps the entry checkable instead of skipping the largest directory in
    the tree.
    """
    marker = _PUBLISHED_PREFIX
    per_doc: dict[str, list[str]] = {}
    for label, path in _DOCS.items():
        entries: list[str] = []
        inside = False
        for line in _fenced_lines(path.read_text(encoding="utf-8")):
            if not line.startswith(" "):
                fields = line.split()
                inside = bool(fields) and fields[0] == marker
                continue
            if not inside:
                continue
            if not re.match(r"^ {2}\S", line):
                continue
            token = line.strip().split()[0].split("<")[0].rstrip("/")
            if token:
                entries.append(token)
        if entries:
            per_doc[label] = entries
    return per_doc


def test_every_plugin_path_named_in_the_docs_actually_ships():
    """A doc naming a path the release does not contain is issue #264's defect.

    Reported per document with the offending token, because the remedy differs:
    a moved file gets re-pointed, a retired one gets the prose rewritten — or, if
    naming it retired IS the prose, an argued entry in `_RETIREMENT_NOTES`.
    """
    shipped = _tracked_shipped_paths()
    bare = _bare_prefixes(shipped)
    counts = {"prefixed": 0, "bare": 0}
    failures = []
    claimed_notes: set[tuple[str, str]] = set()
    for label, path in _DOCS.items():
        named = _named_paths(path.read_text(encoding="utf-8"), bare)
        for channel, tokens in named.items():
            counts[channel] += len(tokens)
            for token in sorted(tokens):
                if token in shipped:
                    continue
                if (label, token) in _RETIREMENT_NOTES:
                    claimed_notes.add((label, token))
                    continue
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
    stale = sorted(set(_RETIREMENT_NOTES) - claimed_notes)
    assert not stale, (
        "`_RETIREMENT_NOTES` entries whose document no longer names that path: "
        + ", ".join(f"{d} -> {p}" for d, p in stale)
        + " — the note was deleted or reworded, so drop the exemption with it"
    )
    assert not failures, "\n".join(failures)


def test_the_retired_name_set_is_derived_and_non_empty():
    """The bare channel can only see a removed directory through this set.

    An empty one is not a clean tree, it is a guard that has lost the half of its
    reach that matters — and a checkout without the release tags produces exactly
    that, silently. Failing loudly is the point: silent reduced coverage is the
    defect class this whole file exists for.
    """
    retired = _retired_top_level_names()
    assert len(retired) >= _MIN_RETIRED_NAMES, (
        f"derived only {len(retired)} retired top-level names from "
        f"`git tag --list {_RELEASE_TAG_GLOB}` (floor {_MIN_RETIRED_NAMES}) — if "
        "this checkout has no release tags, fetch them (`git fetch --tags`); the "
        "bare-reference half of this guard is inert without them"
    )
    assert not (retired & {p.split("/")[0] for p in _tracked_shipped_paths()}), (
        "a name is both retired and currently shipped — the derivation is wrong"
    )


def test_no_published_tree_diagram_lists_an_entry_that_does_not_ship():
    """The diagrams are where the historic defect literally lived, in two docs.

    Checked in the naming direction only — a diagram deliberately omits entries
    (the plugin README's own block leaves out `README.md` and `.gitattributes`),
    and forcing it to enumerate everything would make it worse to read for no
    defect it prevents.
    """
    shipped = _tracked_shipped_paths()
    per_doc = _published_tree_entries()
    total = sum(len(v) for v in per_doc.values())
    assert total >= _MIN_TREE_ENTRIES, (
        f"read only {total} entries from {len(per_doc)} published-tree diagram(s) "
        f"(floor {_MIN_TREE_ENTRIES}) — the blocks' shape changed and this guard "
        "is no longer reading them"
    )
    failures = [
        f"{label}: the published-tree diagram lists `{entry}`, which does not ship"
        for label, entries in per_doc.items()
        for entry in entries
        if entry not in shipped
    ]
    assert not failures, "\n".join(failures)
