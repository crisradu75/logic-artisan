#!/usr/bin/env python3
"""Report requirements (or scenarios) that no test or manual note proves.

A repo's OpenSpec rules ask that each requirement a change adds or modifies is
proven by a test carrying a comment line ``requirement: <spec> / <heading>``, or
by a tasks.md line ``manual: <spec> / <heading>: <reason>``. Nothing but a reviewer reads
that rule, and a consuming repo has no test gate over the plugin, so this is a
program a repo runs, not a test::

    python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/check_spec_proof.py

It only reports. It never edits, files or opens anything.

PROOF GRANULARITY. The default is per requirement. A repo opts in to per-scenario
proof (``scenario: <spec> / <heading>`` markers, scenario headings in ``manual:``
lines) with exactly one line in ``cla.io/project-facts.md``::

    - Test proof granularity: requirement
    - Test proof granularity: scenario

A scenario marker takes two forms. ``scenario: <spec> / <scenario>`` is the canonical one.
``scenario: <spec> / <requirement> / <scenario>`` is accepted too, and also names the requirement
the scenario sits under: it proves the scenario only when that requirement exists in the spec and
holds the scenario, read from the live specs and the active deltas together, as the two-part
form is. A scenario that sits under a different requirement is reported as ``wrong
requirement``, and a requirement the spec does not have as ``unknown requirement``. A scenario heading
that itself holds `` / `` can also read as a three-part marker; when both readings hold, the marker is
reported as ambiguous and proves neither. The ``requirement:`` marker, and the ``manual:`` and ``waiting:`` lines, have no
three-part form: everything after the spec is the heading. See ``resolve_scenario_marker``.

No such line means ``requirement``. A line that starts with the phrase but is
not one of the two forms above, or a second such line, exits 2 and names the
line: a value read loosely would turn the opt-in off without a word. See
``read_granularity``.

WHAT IT REPORTS (each is a ``PROBLEM`` line; any problem exits 1):
  - ``uncovered``: a unit the branch adds or changes (against the merge-base with
    the default branch) with neither a marker nor a ``manual:`` line. A pure
    heading rename (same block text) is not a change. Specs covered: live specs,
    active change deltas and deltas the branch archives. Without a default branch
    this rule is off and the output says so.
  - ``dangling``: a marker, ``manual:`` or ``waiting:`` line naming a spec or
    heading that no live spec or active delta holds (a three-part scenario marker whose
    requirement is unknown, or does not hold the scenario, is named as such). A marker of the
    other granularity is also reported, since nothing reads it.
  - ``repeated``: a heading repeated within one spec or delta. In scenario mode, also a
    scenario heading under two requirements of one spec across its files, since one marker
    would prove both (a requirement a delta removes or renames away from does not count).
  - ``prompt-half``: a ``manual: ... (prompt half)`` line with no marker beside it.
  - ``waiting``: a ``waiting:`` line in an archived change, or beside a unit a
    marker or ``manual:`` line already proves.
  - ``format``: a live spec or active delta over the limits in the repo's
    ``openspec/config.yaml`` ``rules.specs`` (``read_format_limits`` reads the
    numbers from that text, so nothing is copied here): a requirement statement
    over N characters, a requirement with more than N scenarios, and (only while the
    config still states it) a spec with more than N requirements. A limit the config does
    not state is not enforced, and the ``format limits`` output line names it. Archives are
    not edited and are skipped.
  - ``budget``: an active change (``openspec/changes/<name>/``, not the archive) over the
    whole-change budget in ``rules:`` ("at most N requirements across all its specs and at most
    N words in total", read by ``read_change_budget``): the total words over every ``.md`` file
    in its folder (what ``wc -w`` counts) and the total ``### Requirement:`` headings. A budget the
    config does not state is not enforced, and the ``change budget`` output line says so. A
    ``Budget: protected`` line in the change's ``proposal.md`` holds that change to the protected
    override sentence (the one naming `Budget: protected`) instead (a ``Budget:`` line inside a code
    fence is an example and is not read); any other ``Budget:`` value, or that line with no override
    sentence in the config, is a ``budget`` problem. Every active change is checked, whatever ``--base``
    or ``--tests`` says (see ``check_change_budget``). A budget number in wording the
    reader does not know ("twenty-five", "6 000") exits 2.
  - ``empty``: a live spec with no unit, or an active delta whose requirements sit
    under no ADDED, MODIFIED, REMOVED or RENAMED heading; in scenario mode, also a
    requirement in a live spec or active delta with no ``#### Scenario:`` heading (a live spec
    with no scenario at all gets the generic line and one line per requirement).
  - ``purpose`` (a ``NOTE`` line, never a problem and never changes the exit code, since the
    ``**Serves:**`` Purpose is advisory in the repo's spec rules): a live spec whose Purpose
    is missing, ``TBD``, does not open with a ``**Serves:**`` line, or does not follow it
    with exactly one sentence. Only a live spec the branch touches is noted (a changed or
    untracked live spec file, or a delta of any change naming the spec); with no default branch
    to compare with, every live spec is noted and the ``purpose notes`` output line says so.
    See ``purpose_notes`` for what counts as the Serves line and ``count_sentences`` for what
    ends a sentence.
  - ``fence``: a live spec or active delta with a code fence that is never closed
    (everything after it is hidden from the checker).
  - ``spec-map``: only once a repo declares a spec map (see SPEC MAP): a spec (live, or
    added by an active change, and not removed whole by one) that no map file links, a map
    link into ``openspec/specs/`` that names no spec and no tracked or untracked-unignored file
    of that exact case, a link to a spec an active change removes, or a declared path that
    matches no Markdown file.
  - ``manual`` (a ``NOTE`` line, never a problem): a ``manual: <heading>: <reason>`` line in a
    change in progress. It still covers the heading in every spec of the change; the note
    suggests ``manual: <spec> / <heading>: <reason>``, which covers one spec.
  - ``validate``: only with ``--validate``; ``openspec validate --specs --strict``
    failed (skipped, and said so, when the CLI is absent).

SPEC MAP. A repo that keeps a map from its capabilities and workflows to its specs
declares it in ``cla.io/project-facts.md``: one path or glob per bullet under a
``## Spec map`` heading, in any layout, matched against the tracked and untracked-unignored
Markdown files (``.md``, ``.markdown``) (``*`` stays inside one folder, ``**/`` crosses folders, case counts). No such
heading means no map, and then the rule reports nothing and prints no line. A heading with no
bullet, a second heading, a line that is not a bullet, or a heading that reads as "spec
map" in another form (``### Spec map``) exits 2 and names the line; so does a setext heading
(``Spec maps`` over a ``---`` line) when no map was declared by the exact heading. A link is a Markdown link that renders: inline, or a reference definition
whose label a link uses, and not an image, an escaped bracket, or anything inside a code fence
(also in a block quote), an indented code block, a code span or an HTML comment. It is resolved
against the map file's folder and lands on ``openspec/specs/<name>`` or its ``spec.md``; other
links are not read. A spec an active change removes whole (every requirement REMOVED, none added
or modified) needs no link, and a link to it is reported. See ``read_spec_map``, ``map_links``,
``retired_specs`` and ``check_spec_map``.

An empty corpus (no spec files) exits 2: a misconfigured run must not pass.

TEST FILES. A marker is a comment line in any tracked or untracked-unignored
text file, skipping Markdown and other prose suffixes.
``--tests GLOB`` (repeatable) limits the scan to matching repo-relative paths. A
binary file is skipped and named in the output; a file over 2 MB (or unreadable) is
an ``unchecked`` problem, since a bad marker in it could not be seen. Point
``--tests`` at the test folders to leave generated files out. UTF-16 files are
read.

EXIT CODES: 0 clean; 1 problems found; 2 the checker could not do its job
(bad arguments, no repo, malformed facts line, no specs or no unit parsed from
them, an explicit ``--base`` that does not resolve, a base with no merge-base
such as a shallow clone, no file scanned for markers, an unexpected crash, a report
that could not be written to a closed pipe).
Only "no default branch exists at all" turns the changed-unit rule off with
exit 0, and the output says so.

THE ``manual:`` LINE. ``manual: <spec> / <heading>: <reason>`` covers that heading in that
spec only. The older ``manual: <heading>: <reason>`` still counts, with its old meaning: it
covers the heading in every spec of a touched change, so two specs sharing a heading were
covered by one line. A repo with a change in progress that holds the older form keeps passing,
and gets a ``NOTE`` suggesting the new one. ``waiting:`` lines read the same two forms.

The unit tests live in the canonical source repo's development tree, at
``plugin-tests/tests/skills/_shared/test_check_spec_proof.py``; they are not
shipped.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

# The checker's parts sit beside it. Put this folder on `sys.path` first: a test loads this file by path under
# its own module name, and `python -I` leaves the script's folder off the path.
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# `noqa: F401` names are re-exports: tests and other scripts read them off this module.
from spec_proof_budget import (  # noqa: E402
    _BUDGET_PATTERNS,
    change_budget_for,  # noqa: F401
    change_totals,  # noqa: F401
    check_change_budget,
    read_change_budget,
    read_format_limits,
)
from spec_proof_map import _glob_regex, _link_path, map_links, read_spec_map  # noqa: E402
from spec_proof_notes import PROMPT_HALF, Note, resolve_scenario_marker, scan_notes  # noqa: E402,F401
from spec_proof_parse import (  # noqa: E402
    CheckerError,
    FACTS_RELPATH,
    SpecFile,
    Unit,
    _blocks,
    _delta_ops,  # noqa: F401
    _removed_headings,
    _shared_scenarios,
    _statement,  # noqa: F401
    _unclosed_fence,
    check_format,
    parse_units,
)
from spec_proof_prose import _purpose_paragraphs, _spec_names_in, count_sentences, purpose_notes  # noqa: E402,F401

GRANULARITIES = ("requirement", "scenario")
_FACT_STRICT = re.compile(r"^- Test proof granularity: (requirement|scenario)$")
_FACT_LOOSE = re.compile(r"^[\s>]*(?:(?:[-*+]|\d+[.)])\s*)?[*_`]*test proof granularity", re.I)

_MARKER = re.compile(
    r"^\s*(?:#|//|--|;|%|/\*+|\*|<!--)\s*(requirement|scenario):\s+([a-z0-9][a-z0-9-]*) / (.+?)\s*(?:\*/|-->)?\s*$"
)
# A comment line that starts like a marker but misses the format (an upper-case or
# underscored spec name, no spaces around the slash). Reported, never silently dropped.
# It needs a slash after the colon, so prose such as "# scenario: empty input" is not
# mistaken for an attempted marker, and it is case-insensitive so "Requirement:" is caught.
_MARKER_LOOSE = re.compile(r"^\s*(?:#|//|--|;|%|/\*+|\*|<!--)\s*(?:requirement|scenario):\s*\S[^/]*/\s*\S", re.I)
_REQ_ANYWHERE = re.compile(r"(?mi)^###\s+Requirement:")
_DELTA_SECTION = re.compile(r"(?mi)^##\s+(?:ADDED|MODIFIED|REMOVED|RENAMED)\b")

# A repo-relative path that names a live spec directory or its spec.md (group 1 is the spec name).
_SPEC_LINK = re.compile(r"^openspec/specs/([^/]+)(?:/spec\.md)?/?$")

# Prose and binary suffixes never hold a test marker; skipping them keeps a
# documented example (a fenced `# requirement:` line in a guide) from counting.
_SKIP_SUFFIXES = {
    ".md", ".markdown", ".txt", ".rst", ".json", ".lock", ".svg", ".png", ".jpg",
    ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz", ".pyc", ".woff", ".woff2",
}
_MAX_BYTES = 2_000_000


def _git(root: Path, *args: str) -> tuple[int, str, str]:
    """(exit code, stdout, stderr) of `git <args>` in `root`; 127 and the OS error when git cannot start."""
    try:
        r = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except OSError as exc:
        return 127, "", str(exc)
    return r.returncode, r.stdout, r.stderr


def _said(err: str) -> str:
    """git's own words for a failure, as a suffix for an error message ('' when it said nothing)."""
    err = " ".join(err.split())
    return f"; git said: {err}" if err else ""


def _under_git(path: Path) -> bool:
    """True when a `.git` entry sits at `path` or above it. When git then refuses to answer
    (dubious ownership), the run must stop rather than read the folder as a non-repo."""
    return any((p / ".git").exists() for p in [path.resolve(), *path.resolve().parents])


def find_root(explicit: str | None) -> Path:
    if explicit:
        root = Path(explicit).resolve()
        if not root.is_dir():
            raise CheckerError(f"--root {explicit} is not a directory")
        return root
    rc, out, _ = _git(Path.cwd(), "rev-parse", "--show-toplevel")
    if rc == 0 and out.strip():
        return Path(out.strip()).resolve()
    if _under_git(Path.cwd()):
        raise CheckerError(f"git refused this repo (exit {rc}; dubious ownership?): {Path.cwd()}")
    if (Path.cwd() / "openspec").is_dir():
        return Path.cwd().resolve()
    raise CheckerError("not inside a git repo and no openspec/ in the working directory; pass --root")


def read_granularity(root: Path) -> tuple[str, str]:
    """Return (mode, source). Raise CheckerError on a malformed or repeated line."""
    facts = root / FACTS_RELPATH
    if not facts.is_file():
        return "requirement", "default (no facts file)"
    try:
        lines = facts.read_text(encoding="utf-8-sig").splitlines()  # -sig: a byte-order mark must not hide line 1
    except (OSError, UnicodeDecodeError) as exc:
        raise CheckerError(f"cannot read {FACTS_RELPATH}: {exc}") from exc
    found: list[tuple[int, str]] = []
    for n, line in enumerate(lines, 1):
        line = line.rstrip()
        m = _FACT_STRICT.match(line)
        if m:
            found.append((n, m.group(1)))
        elif _FACT_LOOSE.match(line):
            raise CheckerError(
                f"{FACTS_RELPATH}:{n}: malformed line {line!r}; write exactly "
                "'- Test proof granularity: requirement' or '- Test proof granularity: scenario'"
            )
    if len(found) > 1:
        where = ", ".join(str(n) for n, _ in found)
        raise CheckerError(f"{FACTS_RELPATH}: 'Test proof granularity' appears on lines {where}; keep one")
    if not found:
        return "requirement", "default (no 'Test proof granularity' line)"
    return found[0][1], f"{FACTS_RELPATH}:{found[0][0]}"


_MAP_SUFFIXES = (".md", ".markdown")


def retired_specs(files: list["SpecFile"]) -> dict[str, str]:
    """{spec name: the change that removes it} for each live spec an active change removes whole.

    Whole means the change's delta REMOVES every requirement the live spec holds (archive then deletes the
    spec file), and no active change, this one included, adds or modifies one in it. Such a
    spec is still a live file until the archive, but a map that keeps linking it would dangle after."""
    live = {f.spec: f for f in files if f.kind == "live"}
    kept = {f.spec for f in files if f.kind == "active" and f.units}
    out: dict[str, str] = {}
    for f in files:
        if f.kind != "active" or f.spec not in live or f.spec in kept:  # `kept` holds this delta's own spec if it has units
            continue
        held = {h.strip() for h, _, _ in _blocks(live[f.spec].text, False)}
        if held and held <= {h.strip() for h in _removed_headings(f.text)}:
            out[f.spec] = f.change or ""
    return out


def check_spec_map(
    root: Path, specs: dict[str, str], patterns: list[str], retiring: dict[str, str] | None = None
) -> tuple[list[str], str]:
    """PROBLEM lines for a declared spec map, and the one summary line that describes it.

    `specs` maps each spec name to the file that holds it: a live spec, or a spec only an active change
    adds (so a change that adds a capability can link it before it is archived, and the map still passes
    after). `retiring` maps each spec an active change removes whole to that change (`retired_specs`); it is
    not in `specs`, so the map need not link it, and a link to it is reported. Reports each declared pattern
    that matches no Markdown file (a map is a `.md` file, so a glob that also takes in a binary is not
    read as one), each link into `openspec/specs/` that names no spec and no file in the exact-case list
    of tracked and untracked-unignored files, and each spec no map file links. With no map file at all the
    last rule is skipped, since it would repeat every spec after the first problem."""
    problems: list[str] = []
    retiring = retiring or {}
    listed = [rel for rel in _listed_files(root) if (root / rel).is_file()]
    listed_set = set(listed)
    maps: list[str] = []
    for pattern in patterns:
        hits = [rel for rel in listed if rel.lower().endswith(_MAP_SUFFIXES) and _glob_regex(pattern).fullmatch(rel)]
        if not hits:
            problems.append(f"PROBLEM spec-map: declared path {pattern!r} in {FACTS_RELPATH} matches no file (only .md and .markdown files are read as maps)")
        maps += [rel for rel in hits if rel not in maps]
    linked: set[str] = set()
    for rel in maps:
        try:
            text = (root / rel).read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            raise CheckerError(f"cannot read the spec map {rel}: {exc}") from exc
        links, issues = map_links(text)
        problems += [f"PROBLEM spec-map: {rel}:{n}: {why}" for n, why in issues]
        for n, target in links:
            path = _link_path(rel, target)
            if path is None:
                continue
            into_specs = path.startswith("openspec/specs/")
            # A path that climbs out of the repo and names openspec/specs is a mistyped `..`, not another site.
            if not into_specs and not (path.startswith("../") and "/openspec/specs/" in "/" + path):
                continue
            m = _SPEC_LINK.match(path) if into_specs else None
            if m and m.group(1) in retiring:
                problems.append(f"PROBLEM spec-map: {rel}:{n}: link {target!r} points at spec {m.group(1)}, which change {retiring[m.group(1)]} removes")
            elif m and m.group(1) in specs:
                linked.add(m.group(1))
            elif not (into_specs and path in listed_set):
                problems.append(f"PROBLEM spec-map: {rel}:{n}: link {target!r} points at no spec")
    if maps:
        problems += [f"PROBLEM spec-map: {specs[name]} is linked from no spec map" for name in sorted(set(specs) - linked)]
    summary = f"spec map: {len(maps)} file(s) from {len(patterns)} declared path(s); {len(linked)} of {len(specs)} specs linked"
    return problems, summary


def _spec_files(root: Path, mode: str) -> list[SpecFile]:
    files: list[SpecFile] = []
    specs = root / "openspec" / "specs"
    for p in sorted(specs.glob("*/spec.md")) if specs.is_dir() else []:
        files.append(SpecFile(p.relative_to(root).as_posix(), p.parent.name, "live", None, ""))
    changes = root / "openspec" / "changes"
    if changes.is_dir():
        for p in sorted(changes.glob("*/specs/*/spec.md")):
            if p.parent.parent.parent.name == "archive":
                continue
            files.append(SpecFile(p.relative_to(root).as_posix(), p.parent.name, "active", p.parent.parent.parent.name, ""))
        for p in sorted(changes.glob("archive/*/specs/*/spec.md")):
            files.append(
                SpecFile(p.relative_to(root).as_posix(), p.parent.name, "archived", "archive/" + p.parent.parent.parent.name, "")
            )
    for f in files:
        try:
            f.text = (root / f.rel).read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            raise CheckerError(f"cannot read {f.rel}: {exc}") from exc
        f.units = parse_units(f.text, mode, f.kind != "live")
    return files


def resolve_base(root: Path, explicit: str | None) -> tuple[str | None, str]:
    """Return (merge-base sha or None, note)."""
    candidates = [explicit] if explicit else []
    if not explicit:
        rc, out, _ = _git(root, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
        if rc == 0 and out.strip():
            candidates.append(out.strip().removeprefix("refs/remotes/"))
        candidates += ["origin/main", "origin/master", "main", "master"]
    if not explicit and _git(root, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")[0] != 0:
        return None, "no commit on HEAD yet"
    failed = []
    for ref in candidates:
        rc, _, _ = _git(root, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
        if rc != 0:
            continue
        rc, out, _ = _git(root, "merge-base", "HEAD", ref)
        if rc == 0 and out.strip():
            return out.strip(), f"merge-base with {ref}"
        failed.append(ref)
    if failed:
        # A branch exists but shares no history we can see (a shallow clone): turning the
        # rule off here would pass a branch nobody compared.
        raise CheckerError(f"{failed[0]} exists but git merge-base HEAD {failed[0]} failed (a shallow clone?); fetch more history or pass --base")
    if explicit:
        raise CheckerError(f"--base {explicit} does not resolve to a commit")
    return None, "no default branch found"


def changed_paths(root: Path, base: str) -> set[str]:
    out = set()
    # --relative keeps both lists relative to `root`, which may be a subfolder of the repo.
    for args in (("diff", "--name-only", "--relative", "-z", base), ("ls-files", "-o", "--exclude-standard", "-z")):
        rc, text, err = _git(root, *args)
        if rc != 0:
            # A skipped list would read as "nothing changed": no unit is changed and no spec is touched.
            raise CheckerError(f"git {args[0]} failed (exit {rc}{_said(err)}), so the changed paths are unknown")
        out |= {p for p in text.split("\0") if p}
    return out


def _base_text(root: Path, base: str, rel: str) -> str | None:
    """The text of `rel` at `base`, or None when git confirms the path is not in that tree (a new file).

    Any other failure raises: None means "new at base", so every unit of the file would count as changed.

    `git show <rev>:<path>` is not used. Given an argument that is a valid revision, it also lstat()s the
    argument as a file name, and on Windows that stat fails with "Filename too long" once the working
    directory plus the argument pass 260 characters, which a deep clone and a long archive path do.
    `cat-file blob` reads the object name without that file-name check."""
    rc, out, err = _git(root, "cat-file", "blob", f"{base}:./{rel}")
    if rc == 0:
        return out
    list_rc, listing, list_err = _git(root, "ls-tree", "--name-only", base, "--", rel)
    if list_rc == 0 and not listing.strip():
        return None
    raise CheckerError(
        f"cannot read {rel} at {base[:12]} (git cat-file exit {rc}, ls-tree exit {list_rc}{_said(err or list_err)}); "
        "the changed-requirement rule cannot run"
    )


def _base_for(root: Path, base: str, f: SpecFile) -> str | None:
    text = _base_text(root, base, f.rel)
    if text is None and f.kind == "archived":
        # Archiving moves the delta; compare with the copy that sat in the active change.
        m = re.match(r"openspec/changes/archive/(?:\d{4}-\d{2}-\d{2}-)?([^/]+)/(specs/.+)$", f.rel)
        if m:
            text = _base_text(root, base, f"openspec/changes/{m.group(1)}/{m.group(2)}")
    return text


def changed_units(root: Path, base: str, f: SpecFile, mode: str) -> list[Unit]:
    old = _base_for(root, base, f)
    if old is None:
        return list(f.units)
    old_units = parse_units(old, mode, f.kind != "live")
    now_headings = {u.heading for u in f.units}
    same = {(u.heading, u.body) for u in old_units}
    # A rename is a base unit whose heading is gone, reappearing under a new heading with the
    # same text. Matching on text alone would hide a NEW unit that merely repeats an old one's.
    renamed_from = {u.body for u in old_units if u.heading not in now_headings}
    old_headings = {u.heading for u in old_units}
    return [
        u for u in f.units
        if (u.heading, u.body) not in same and not (u.heading not in old_headings and u.body in renamed_from)
    ]


def _listed_files(root: Path) -> list[str]:
    """Repo-relative paths of the tracked and untracked-unignored files (a directory walk outside git), sorted."""
    rc, out, _ = _git(root, "ls-files", "-co", "--exclude-standard", "-z")
    if rc == 0:
        return sorted({p for p in out.split("\0") if p})
    rels = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in {".git", "node_modules", "__pycache__", ".venv"}]
        rels += [(Path(dp) / fn).relative_to(root).as_posix() for fn in fns]
    return sorted(set(rels))


def scan_markers(root: Path, globs: list[str]) -> tuple[list[tuple[str, str, str, str]], int, list[str]]:
    """Return ([(kind, spec, heading, relpath)], files scanned, files skipped).

    A file is skipped only when it is binary (a NUL byte), unreadable or over the size
    cap, and each is returned by name so the run can say so. Text in another encoding
    is still scanned, with undecodable bytes replaced."""
    found = []
    skipped: list[tuple[str, str]] = []
    scanned = 0
    for rel in _listed_files(root):
        if Path(rel).suffix.lower() in _SKIP_SUFFIXES:
            continue
        if globs and not any(fnmatch.fnmatch(rel, g) for g in globs):
            continue
        p = root / rel
        if not p.is_file():
            continue
        try:
            raw = p.read_bytes() if p.stat().st_size <= _MAX_BYTES else None
        except OSError:
            raw = None
        utf16 = raw is not None and raw[:2] in (b"\xff\xfe", b"\xfe\xff")  # Windows PowerShell writes these
        if raw is None:
            skipped.append((rel, "oversize or unreadable"))
            continue
        if b"\0" in raw and not utf16:
            skipped.append((rel, "binary"))
            continue
        scanned += 1
        for line in raw.decode("utf-16" if utf16 else "utf-8", errors="replace").splitlines():
            m = _MARKER.match(line)
            if m:
                found.append((m.group(1), m.group(2), m.group(3), rel))
            elif _MARKER_LOOSE.match(line) and not line.split(":", 1)[1].lstrip().startswith("<"):
                found.append(("malformed", "", line.strip(), rel))
    return found, scanned, skipped


def _validate(root: Path, problems: list[str], lines: list[str]) -> None:
    exe = shutil.which("openspec")
    if exe is None:
        lines.append("validate: skipped, the openspec CLI is not on PATH")
        return
    r = subprocess.run([exe, "validate", "--specs", "--strict"], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        tail = " | ".join((r.stdout + r.stderr).strip().splitlines()[-5:])
        problems.append(f"PROBLEM validate: openspec validate --specs --strict exited {r.returncode}: {tail}")
    else:
        lines.append("validate: openspec validate --specs --strict passed")


def check(root: Path, base_arg: str | None = None, globs: list[str] | None = None, validate: bool = False) -> tuple[int, list[str]]:
    """Run every rule. Returns (exit code, output lines)."""
    out: list[str] = []
    problems: list[str] = []
    mode, source = read_granularity(root)
    other = "scenario" if mode == "requirement" else "requirement"
    files = _spec_files(root, mode)
    if not files:
        raise CheckerError("no spec files found under openspec/specs or openspec/changes; a run that checks nothing must not pass")

    if not any(f.units for f in files if f.kind != "archived"):
        raise CheckerError(
            f"{len(files)} spec file(s) found but no {mode} parsed from a live spec or active delta; "
            "check the '## Requirements' section and '### Requirement:' headings (an unclosed code fence hides the rest of a file)"
        )

    # Universe a marker may name: live specs plus active deltas.
    universe: dict[str, set[str]] = {}
    for f in files:
        if f.kind != "archived":
            universe.setdefault(f.spec, set()).update(u.heading for u in f.units)
    known = {h for hs in universe.values() for h in hs}
    # For the three-part scenario marker: each spec's requirement headings, and the requirements each scenario sits under.
    reqs: dict[str, set[str]] = {}
    owners: dict[str, dict[str, set[str]]] = {}
    if mode == "scenario":
        for f in files:
            if f.kind != "archived":
                for req_heading, _, scns in _blocks(f.text, f.kind != "live"):
                    reqs.setdefault(f.spec, set()).add(req_heading)
                    for scn_heading, _ in scns:
                        owners.setdefault(f.spec, {}).setdefault(scn_heading, set()).add(req_heading)

    for f in files:
        if f.kind == "archived":
            continue  # archives are not edited, so a repeat there could never be fixed
        seen: dict[str, int] = {}
        for u in f.units:
            seen[u.heading] = seen.get(u.heading, 0) + 1
        for h, n in sorted(seen.items()):
            if n > 1:
                problems.append(f"PROBLEM repeated: {f.rel}: heading {h!r} appears {n} times")
    if mode == "scenario":
        problems += _shared_scenarios(files)

    for f in files:
        # A delta that writes requirements under a heading OpenSpec does not read
        # (`## Requirements` instead of `## ADDED Requirements`) yields nothing to check.
        if f.kind == "active" and not f.units and _REQ_ANYWHERE.search(f.text) and not _DELTA_SECTION.search(f.text):
            problems.append(f"PROBLEM empty: {f.rel}: requirements but no ADDED, MODIFIED, REMOVED or RENAMED section, so none is checked")
        if f.kind == "live" and not f.units:
            problems.append(f"PROBLEM empty: {f.rel}: a live spec with no {mode} parsed")
        if f.kind != "archived":
            if _unclosed_fence(f.text):
                problems.append(f"PROBLEM fence: {f.rel}: a code fence is never closed, so the rest of the file is not read")
            if mode == "scenario":
                # In scenario mode a requirement with no scenario adds no unit, so nothing else would look at it.
                # A live spec with no unit at all gets the generic `empty` line above AND one line per requirement,
                # so the author sees which requirements to fix.
                for heading, _, scns in _blocks(f.text, f.kind != "live"):
                    if not scns:
                        problems.append(f"PROBLEM empty: {f.rel}: requirement {heading!r} has no '#### Scenario:' heading, so none is checked")

    limits, unenforced = read_format_limits(root)
    problems += check_format(files, limits)
    budget, budget_override = read_change_budget(root)
    budget_problems, change_info = check_change_budget(root, budget, budget_override)
    problems += budget_problems

    map_line = None
    map_notes: list[str] = []
    patterns = read_spec_map(root, map_notes)  # None: no map declared, so the rule reports nothing and prints no line
    if patterns is not None:
        retiring = retired_specs(files)
        spec_rels: dict[str, str] = {}
        for f in files:
            # `files` lists live specs first, so a live file names its spec; a spec a change removes whole is not one.
            if f.kind != "archived" and f.spec not in spec_rels and f.spec not in retiring:
                spec_rels[f.spec] = f.rel
        map_problems, map_line = check_spec_map(root, spec_rels, patterns, retiring)
        problems += map_problems

    markers, scanned, skipped = scan_markers(root, globs or [])
    for rel, why in skipped:
        if why != "binary":
            # A marker inside could be dangling or malformed and nobody would know.
            problems.append(f"PROBLEM unchecked: {rel}: {why}, so its markers were not checked")
    skipped = [rel for rel, why in skipped if why == "binary"]
    if scanned == 0:
        raise CheckerError("no file was scanned for markers" + (f" (--tests {' '.join(globs)} matched nothing)" if globs else ""))
    marked: set[tuple[str, str]] = set()
    for kind, spec, heading, rel in markers:
        if kind == "malformed":
            problems.append(f"PROBLEM dangling: {rel}: {heading!r} looks like a marker but is not '{mode}: <spec> / <heading>' (lower-case spec name, spaces around the slash)")
        elif kind == other:
            problems.append(f"PROBLEM dangling: {rel}: '{kind}: {spec} / {heading}' is a {kind} marker; this repo proves per {mode}")
        elif mode == "scenario":
            proven, why = resolve_scenario_marker(spec, heading, universe, owners, reqs)
            if proven is None:
                problems.append(f"PROBLEM dangling: {rel}: '{kind}: {spec} / {heading}' {why}")
            else:
                marked.add((spec, proven))
        elif heading not in universe.get(spec, set()):
            problems.append(f"PROBLEM dangling: {rel}: '{kind}: {spec} / {heading}' names no {mode} in any live spec or active delta")
        else:
            marked.add((spec, heading))

    notes = scan_notes(root, known, universe)
    for n in notes:
        if n.heading is None and not n.archived:
            problems.append(f"PROBLEM dangling: openspec/changes/{n.change}/tasks.md: '{n.kind}: {n.raw}' names no {mode} heading")
        if n.kind == "waiting" and n.archived:
            problems.append(f"PROBLEM waiting: openspec/changes/{n.change}/tasks.md: archived but still waiting: {n.raw!r}")

    base, base_note = (None, "")
    changed: dict[str, list[Unit]] | None = None
    touched: set[str] = set()
    touched_specs: set[str] | None = None  # None: no base, so no way to tell which specs the branch touches
    git_rc = _git(root, "rev-parse", "--git-dir")[0]
    if git_rc == 127:
        raise CheckerError("git is not installed or not on PATH")
    if git_rc == 0:
        base, base_note = resolve_base(root, base_arg)
    elif _under_git(root):
        raise CheckerError(f"git refused this repo (exit {git_rc}; dubious ownership?): {root}")
    elif base_arg:
        raise CheckerError(f"--base {base_arg} given but {root} is not a git repo")
    if base is not None:
        paths = changed_paths(root, base)
        touched_specs = _spec_names_in(paths)
        changed ={f.rel: changed_units(root, base, f, mode) for f in files}
        for p in paths:
            m = re.match(r"openspec/changes/((?:archive/)?[^/]+)/", p)
            if m:
                touched.add(m.group(1))

    def notes_for(heading: str, change: str | None, kind: str, spec: str) -> list[Note]:
        # A line that names a spec covers that spec only; the older heading-only form covers every spec of its change.
        return [
            n for n in notes
            if n.kind == kind and n.heading == heading and n.spec in (None, spec)
            and ((n.change == change) if change else n.change in touched)
        ]

    covered_waiting = 0
    n_changed = 0
    if changed is not None:
        for f in files:
            scope = None if f.kind == "live" else f.change
            for u in changed[f.rel]:
                n_changed += 1
                where = f"{f.rel}: {f.spec} / {u.heading}"
                if (f.spec, u.heading) in marked:
                    continue
                manual = notes_for(u.heading, scope, "manual", f.spec)
                whole = [n for n in manual if not n.prompt_half]
                if whole:
                    continue
                if manual:
                    problems.append(f"PROBLEM prompt-half: {where}: '(prompt half)' manual line but no {mode} marker for the test half")
                    continue
                if any(not n.archived for n in notes_for(u.heading, scope, "waiting", f.spec)):
                    covered_waiting += 1
                    continue
                problems.append(f"PROBLEM uncovered: {where}: changed {mode} has no '{mode}: {f.spec} / {u.heading}' marker and no 'manual: {f.spec} / {u.heading}: <reason>' line")

    whole_manual = [n for n in notes if n.kind == "manual" and not n.prompt_half and n.heading]

    def manual_proves(spec: str | None, heading: str) -> bool:
        """Whether a whole manual line proves `heading` in `spec` (in any spec, when `spec` is None)."""
        return any(n.heading == heading and (spec is None or n.spec in (None, spec)) for n in whole_manual)

    def holders_of(change: str, heading: str) -> list[str]:
        """The specs that hold `heading`: the ones the change's own deltas hold, else every spec."""
        own = {f.spec for f in files if f.kind == "active" and f.change == change and any(u.heading == heading for u in f.units)}
        return sorted(own or {s for s, hs in universe.items() if heading in hs})

    for n in notes:
        if n.kind == "waiting" and n.heading and not n.archived:
            if n.spec:
                proven = manual_proves(n.spec, n.heading) or (n.spec, n.heading) in marked
            else:
                # An older waiting line stands for the heading in every spec of its change. It is stale once a marker
                # or an older manual line proves the heading anywhere, or spec-named manual lines prove it in each spec
                # that holds it; one spec-named line leaves the others still waiting.
                named = {m.spec for m in whole_manual if m.heading == n.heading and m.spec}
                held = holders_of(n.change, n.heading)
                proven = (
                    any(m.heading == n.heading and m.spec is None for m in whole_manual)
                    or any((s, n.heading) in marked for s in universe)
                    or (bool(held) and set(held) <= named)
                )
            if proven:
                problems.append(f"PROBLEM waiting: openspec/changes/{n.change}/tasks.md: {n.heading!r} is already proven, so it is no longer waiting")

    manual_notes = []
    for n in notes:
        if n.kind == "manual" and not n.archived and n.spec is None and n.heading is not None:
            holders = holders_of(n.change, n.heading)
            manual_notes.append(
                f"NOTE manual: openspec/changes/{n.change}/tasks.md: 'manual: {n.heading}: ...' names only the heading, so it covers "
                f"{n.heading!r} in every spec of the change; write 'manual: {holders[0] if len(holders) == 1 else '<spec>'} / {n.heading}: ...' "
                "to cover one spec" + (f" (specs holding it: {', '.join(holders)})" if len(holders) > 1 else "")
            )

    if validate:
        _validate(root, problems, out)

    # Counts (information only, never a gate).
    all_units = [(f.spec, u.heading) for f in files if f.kind != "archived" for u in f.units]
    covered = sum(1 for s, h in all_units if (s, h) in marked or manual_proves(s, h))
    kinds = {k: sum(1 for f in files if f.kind == k) for k in ("live", "active", "archived")}
    live_names = {f.spec for f in files if f.kind == "live"}
    out += [
        f"granularity: {mode} ({source})",
        f"specs: {len(files)} (live {kinds['live']}, active delta {kinds['active']}, archived delta {kinds['archived']})",
        f"{mode}s in live specs and active deltas: {len(all_units)}",
        f"changed {mode}s: " + (f"{n_changed} ({base_note})" if changed is not None else f"unknown, the changed-{mode} rule is off ({base_note or 'not a git repo'})"),
        f"markers: {sum(1 for m in markers if m[0] != 'malformed')} in {scanned} files scanned"
        + (f"; skipped {len(skipped)} binary: {', '.join(skipped[:5])}" if skipped else ""),
        f"manual lines: {sum(1 for n in notes if n.kind == 'manual')} (prompt half: {sum(1 for n in notes if n.kind == 'manual' and n.prompt_half)})",
        f"waiting lines: {sum(1 for n in notes if n.kind == 'waiting')} (covering a changed {mode}: {covered_waiting})",
        f"repo-wide coverage (information only): {covered}/{len(all_units)}",
        "format limits (from openspec/config.yaml): "
        + (", ".join(f"{k} {v}" for k, v in limits.items()) or "none")
        + (f"; not enforced, not found: {', '.join(unenforced)}" if unenforced else ""),
        "change budget (from openspec/config.yaml): "
        + (", ".join(f"{k} {v}" for k, v in budget.items()) or "none, not enforced")
        + (f"; not enforced, not found: {', '.join(k for k in _BUDGET_PATTERNS if k not in budget)}" if budget and len(budget) < len(_BUDGET_PATTERNS) else "")
        + "; protected override: "
        + (", ".join(f"{k} {v}" for k, v in budget_override.items()) or "none"),
        *change_info,
        *([map_line] if map_line else []),
        "purpose notes: "
        + (
            f"{len(touched_specs & live_names)} live spec(s) the branch touches"
            if touched_specs is not None
            else f"every live spec, since the touched specs are unknown ({base_note or 'not a git repo'})"
        ),
        f"problems: {len(problems)}",
    ]
    return (1 if problems else 0), problems + purpose_notes(files, touched_specs) + manual_notes + map_notes + out


def _console_safe(text: str) -> str:
    """`text` with any character the stdout encoding cannot hold written as a backslash escape.

    A cp1252 Windows console cannot print most non-ASCII text, and the resulting UnicodeEncodeError
    would escape `main` as a traceback with exit 1, which reads as "problems found". On a console that
    can hold the text (UTF-8) the result is `text` itself."""
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        return text.encode(enc, errors="backslashreplace").decode(enc)
    except LookupError:  # an encoding name Python does not know: ASCII holds any text once escaped
        return text.encode("ascii", errors="backslashreplace").decode("ascii")


def _report(text: str) -> bool:
    """Print `text` to stdout. False when stdout cannot take it (a closed pipe, a full disk).

    The failed handle is pointed at the null device first: left alone, Python flushes it again on exit,
    prints a second traceback and replaces the exit code. With no stdout at all (descriptor 1 closed when the
    process started, so `sys.stdout` is None) there is nothing to point anywhere, and the run says so."""
    try:
        if sys.stdout is None:
            raise OSError("standard output is closed")
        print(_console_safe(text))
        sys.stdout.flush()
    except (OSError, ValueError) as exc:  # ValueError: stdout was closed
        try:
            fd = sys.stdout.fileno()
            null = os.open(os.devnull, os.O_WRONLY)
            try:
                os.dup2(null, fd)
            finally:
                os.close(null)
        except (OSError, ValueError, AttributeError):  # no descriptor to redirect (a test double, a closed stream)
            pass
        try:
            print(f"check_spec_proof: cannot write the report: {exc}", file=sys.stderr)
        except (OSError, ValueError):  # stderr is gone too
            pass
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    # Python 3.14 argparse colours by default and probes stdout with isatty() while building
    # the parser. On a closed stdout that probe raises ValueError before the guarded report
    # code runs, so the promised exit 2 never happens. Both the parser and its formatter probe:
    # HelpFormatter.__init__ defaults to color=True before the parser's own setting is applied.
    # Older versions reject the keyword, so it is passed only from 3.14 on.
    no_colour = {"color": False} if sys.version_info >= (3, 14) else {}

    class _PlainFormatter(argparse.HelpFormatter):
        def __init__(self, prog: str, **kw: object) -> None:
            super().__init__(prog, **{**no_colour, **kw})

    ap = argparse.ArgumentParser(
        description="Report requirements with no test marker or manual note. Never edits anything.",
        formatter_class=_PlainFormatter,
        **no_colour,
    )
    ap.add_argument("--root", help="repo root (default: the git toplevel of the working directory)")
    ap.add_argument("--base", help="ref to compare with (default: the default branch)")
    ap.add_argument("--tests", action="append", default=[], metavar="GLOB", help="limit the marker scan to matching repo-relative paths; repeatable")
    ap.add_argument("--validate", action="store_true", help="also run 'openspec validate --specs --strict' when the CLI is present")
    args = ap.parse_args(argv)
    try:
        code, lines = check(find_root(args.root), args.base, args.tests, args.validate)
    except CheckerError as exc:
        print(f"check_spec_proof: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - a crash must read as "could not run", never as "problems found"
        print(f"check_spec_proof: unexpected {type(exc).__name__}: {exc}\n{traceback.format_exc()}", file=sys.stderr)
        return 2
    return code if _report("\n".join(lines)) else 2  # a report nobody could read must not read as "clean" or "problems found"


if __name__ == "__main__":
    sys.exit(main())
