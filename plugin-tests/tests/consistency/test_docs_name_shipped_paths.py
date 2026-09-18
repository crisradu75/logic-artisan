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
# were measured at — 10 prefixed, 30 bare, 6 retired names — and not at them, so
# an ordinary doc edit does not fail a guard whose subject is not doc size. The
# command behind every number in this block, including the two per-document maps:
#
#   python3 -c "import importlib.util as u; \
#     s=u.spec_from_file_location('g','plugin-tests/tests/consistency/test_docs_name_shipped_paths.py'); \
#     m=u.module_from_spec(s); s.loader.exec_module(m); \
#     sh=m._tracked_shipped_paths(); b=m._bare_prefixes(sh); \
#     n={k:m._named_paths(p.read_text(encoding='utf-8'),b) for k,p in m._DOCS.items()}; \
#     print({k:len(v['prefixed'])+len(v['bare']) for k,v in n.items()}); \
#     print({k:sum(len(v[c]) for v in n.values()) for c in ('prefixed','bare')}); \
#     print(len(m._retired_top_level_names()), \
#           {k:len(v) for k,v in m._published_tree_entries().items()})"
_MIN_PREFIXED_PATHS = 5
_MIN_BARE_PATHS = 15
_MIN_RETIRED_NAMES = 4

# PER DOCUMENT, because a total across documents is the same mistake one axis
# over. The per-channel split above exists because one combined number could not
# notice half the extraction dying; a number summed over four documents cannot
# notice one DOCUMENT dropping out, and the docs are not the same size — the root
# `README.md` contributes 2 paths against the plugin README's 13, so it could go
# to zero and leave a four-document total barely moved.
#
# Measured per document at 13 / 2 / 12 / 13 (plugin README, README,
# DEVELOPER-GUIDE, CLAUDE), by the command in the block below. The root README's
# floor is deliberately 1 rather than a larger round number: it genuinely names
# almost no plugin paths in PROSE, and its real coverage is its tree diagram,
# floored separately. A floor is a tripwire for an extraction that died, not a
# target for how much a document should say.
_MIN_PATHS_PER_DOC = {
    "plugin README.md": 8,
    "README.md": 1,
    "DEVELOPER-GUIDE.md": 7,
    "CLAUDE.md": 8,
}

# The documents that MUST carry a published-tree diagram, and the floor for each.
# A map rather than a total, and the keys are the load-bearing part: a document
# whose block stops parsing simply vanished from the old aggregate — the shipped
# README's diagram could go unguarded with the suite green, because the other two
# still cleared a combined floor of 12. Measured at 6 / 8 / 8.
#
# `DEVELOPER-GUIDE.md` is absent on purpose: it carries no tree diagram today. If
# it grows one, add it here — and until then its six fenced blocks are exactly
# the input that `_fenced_blocks` exists to keep out of this parse.
_DIAGRAM_FLOORS = {
    "plugin README.md": 4,
    "README.md": 5,
    "CLAUDE.md": 5,
}


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


def _fenced_blocks(text: str):
    """Each fenced code block, as its own list of lines.

    BLOCKS, not a flat stream of fenced lines, and the distinction is a defect
    that was found rather than designed around. `_published_tree_entries` tracks
    whether it is under the `.claude/plugins/cla/` marker, and it clears that
    state on an unindented line — so with the delimiters stripped and the blocks
    concatenated, a LATER block whose first line happened to be indented two
    spaces would be read as more tree entries, having never seen an unindented
    line to reset on. `DEVELOPER-GUIDE.md` already carries six fenced blocks and
    escapes only because it has no tree diagram to start the state off; that is
    luck, not design. A block boundary is a hard reset here.
    """
    block: list[str] = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            if fenced:
                yield block
                block = []
            fenced = not fenced
            continue
        if fenced:
            block.append(line)
    if fenced and block:
        # Unterminated fence: yield what there is rather than silently dropping
        # it, so a malformed document is visible to the floors instead of empty.
        yield block


def _fenced_lines(text: str):
    for block in _fenced_blocks(text):
        yield from block


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
        for block in _fenced_blocks(path.read_text(encoding="utf-8")):
            # Reset PER BLOCK — see `_fenced_blocks` for the defect this closes.
            inside = False
            for line in block:
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


_TAGLESS_REMEDY = (
    "this checkout derived NO retired top-level names, so the bare-reference "
    "half of the extraction is inert and the migration notes stopped being "
    "seen. The exemptions are almost certainly still correct — do NOT delete "
    f"them. Fetch the release tags instead (`git fetch --tags`); "
    "`test_the_retired_name_set_is_derived_and_non_empty` is the same diagnosis"
)


def _stale_notes_message(stale, retired) -> str:
    """The message for unclaimed `_RETIREMENT_NOTES` entries.

    Split out from the assertion so the tag-less branch can be tested directly
    rather than by arranging a tag-less checkout. It exists because the obvious
    message is actively harmful in one reachable case: on a shallow clone,
    `--no-tags`, or a fresh fork, `_retired_top_level_names()` is empty, the
    migration-note paths stop being extracted, and every exemption goes
    unclaimed at once — where "drop the exemption with it" would delete correct
    work to silence a checkout problem. Same condition, opposite remedy, so the
    condition has to be named rather than inferred from the list.
    """
    listed = ", ".join(f"{d} -> {p}" for d, p in stale)
    if not retired:
        return f"{_TAGLESS_REMEDY}. Unclaimed entries: {listed}"
    return (
        "`_RETIREMENT_NOTES` entries whose document no longer names that path: "
        f"{listed} — the note was deleted or reworded, so drop the exemption "
        "with it"
    )


def test_every_plugin_path_named_in_the_docs_actually_ships():
    """A doc naming a path the release does not contain is issue #264's defect.

    Reported per document with the offending token, because the remedy differs:
    a moved file gets re-pointed, a retired one gets the prose rewritten — or, if
    naming it retired IS the prose, an argued entry in `_RETIREMENT_NOTES`.
    """
    shipped = _tracked_shipped_paths()
    bare = _bare_prefixes(shipped)
    counts = {"prefixed": 0, "bare": 0}
    per_doc_counts: dict[str, int] = {}
    failures = []
    claimed_notes: set[tuple[str, str]] = set()
    for label, path in _DOCS.items():
        named = _named_paths(path.read_text(encoding="utf-8"), bare)
        per_doc_counts[label] = sum(len(t) for t in named.values())
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
    thin = {
        label: (per_doc_counts.get(label, 0), floor)
        for label, floor in _MIN_PATHS_PER_DOC.items()
        if per_doc_counts.get(label, 0) < floor
    }
    assert not thin, (
        "document(s) below their own extraction floor: "
        + ", ".join(f"{d} {got} < {floor}" for d, (got, floor) in sorted(thin.items()))
        + " — a per-document floor exists because a total across four documents "
        "cannot notice ONE of them dropping out"
    )
    stale = sorted(set(_RETIREMENT_NOTES) - claimed_notes)
    assert not stale, _stale_notes_message(stale, _retired_top_level_names())
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
    unparsed = {
        label: (len(per_doc.get(label, ())), floor)
        for label, floor in _DIAGRAM_FLOORS.items()
        if len(per_doc.get(label, ())) < floor
    }
    assert not unparsed, (
        "published-tree diagram(s) that stopped parsing, or shrank below their "
        "floor: "
        + ", ".join(
            f"{d} {got} < {floor}" for d, (got, floor) in sorted(unparsed.items())
        )
        + " — a document whose block stops parsing simply DISAPPEARS from a "
        "combined total, which is how the shipped README's diagram could go "
        "unguarded with the suite green. Floored per document for that reason."
    )
    failures = [
        f"{label}: the published-tree diagram lists `{entry}`, which does not ship"
        for label, entries in per_doc.items()
        for entry in entries
        if entry not in shipped
    ]
    assert not failures, "\n".join(failures)


def test_a_fenced_block_boundary_resets_the_diagram_parser():
    """A later block cannot inherit the previous one's "inside the tree" state.

    Asserted on synthetic input because the real documents do not exercise it
    TODAY — `DEVELOPER-GUIDE.md` has six fenced blocks and no tree diagram, and
    the diagrams elsewhere happen to be followed by blocks whose first line is
    unindented. That is luck: it holds until someone writes a shell block whose
    first line is indented two spaces after a diagram, at which point its lines
    would be read as published entries and checked against the shipped tree.
    A latent defect with no failing input is exactly what a unit test is for.
    """
    doc = (
        "```\n"
        f"{_PUBLISHED_PREFIX}\n"
        "  skills/\n"
        "```\n"
        "\n"
        "```bash\n"
        "  conformance-checks/tests\n"
        "```\n"
    )
    blocks = list(_fenced_blocks(doc))
    assert len(blocks) == 2, f"expected two blocks, got {len(blocks)}: {blocks}"
    assert blocks[0] == [_PUBLISHED_PREFIX, "  skills/"]
    assert blocks[1] == ["  conformance-checks/tests"]


def test_a_tagless_checkout_is_told_to_fetch_tags_not_to_delete_exemptions():
    """The one case where the obvious message destroys correct work.

    Without the release tags the retired-name set is empty, the bare channel
    stops seeing the migration notes, and EVERY exemption goes unclaimed at
    once. The ordinary reading of that — "the note was deleted, so drop the
    exemption" — is exactly wrong there: the notes are intact and the checkout
    is the problem. Asserted directly rather than by arranging a tag-less clone,
    which is why `_stale_notes_message` is a function and not an inline string.
    """
    stale = sorted(_RETIREMENT_NOTES)
    assert stale, "no exemptions to reason about — this test has lost its subject"

    tagless = _stale_notes_message(stale, frozenset())
    assert "git fetch --tags" in tagless
    assert "do NOT delete" in tagless
    assert "drop the exemption" not in tagless, (
        "the tag-less branch still tells the reader to delete exemptions that "
        "are correct"
    )

    # The ordinary branch must still give the ordinary remedy, or fixing the
    # message above would have traded one wrong instruction for another.
    ordinary = _stale_notes_message(stale, frozenset({"conformance-checks"}))
    assert "drop the exemption" in ordinary
    assert "git fetch --tags" not in ordinary
