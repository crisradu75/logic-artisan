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
that itself holds `` / `` is read as the two-part form first. The ``requirement:`` marker, and the ``manual:`` and ``waiting:`` lines, have no
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
  - ``repeated``: a heading repeated within one spec or delta.
  - ``prompt-half``: a ``manual: ... (prompt half)`` line with no marker beside it.
  - ``waiting``: a ``waiting:`` line in an archived change, or beside a unit a
    marker or ``manual:`` line already proves.
  - ``format``: a live spec or active delta over the limits in the repo's
    ``openspec/config.yaml`` ``rules.specs`` (``read_format_limits`` reads the
    numbers from that text, so nothing is copied here): a requirement statement
    over N characters, a requirement with more than N scenarios, a spec with more
    than N requirements. A limit the config does not state is not enforced, and the
    ``format limits`` output line names it. Archives are not edited and are skipped.
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
import posixpath
import re
import shutil
import subprocess
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path

FACTS_RELPATH = "cla.io/project-facts.md"
GRANULARITIES = ("requirement", "scenario")
_FACT_STRICT = re.compile(r"^- Test proof granularity: (requirement|scenario)$")
_FACT_LOOSE = re.compile(r"^[\s>]*(?:(?:[-*+]|\d+[.)])\s*)?[*_`]*test proof granularity", re.I)

_H2 = re.compile(r"^##\s+(?!#)(.+?)\s*$")
_H3 = re.compile(r"^###\s+(?!#)")
# OpenSpec reads the keyword case-insensitively, so `### requirement:` must not dodge the counts.
_REQ = re.compile(r"^###\s+Requirement:\s*(.+?)\s*$", re.I)
_SCN = re.compile(r"^####\s+Scenario:\s*(.+?)\s*$", re.I)
_PURPOSE_H = re.compile(r"^##\s+Purpose\s*$", re.I)
# A path of a live spec (group 1) or of a delta in an active or archived change (group 2), relative to the repo root.
_SPEC_PATH = re.compile(r"^openspec/(?:specs/([^/]+)|changes/(?:archive/)?[^/]+/specs/([^/]+))/")
_H4 = re.compile(r"^####\s+(?!#)")
_FENCE = re.compile(r"^\s*(```|~~~)")

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
_NOTE = re.compile(
    r"^\s*(?:[-*+]\s+)?(?:\[[ xX]\]\s+)?(?:\d+(?:\.\d+)*\.?\s+)?(manual|waiting):\s+(.+?)\s*$"
)
PROMPT_HALF = "(prompt half)"

_MAP_HEADING = re.compile(r"^##\s+Spec map\s*$", re.I)
# An ATX heading of any level (up to 3 spaces of indent, optional closing hashes). `_reads_as_map_heading`
# uses it to find a heading that reads as "Spec map" but is not the exact form above (`### Spec map`,
# `## Spec map:`, `## Spec  maps`, `## **Spec-map**`): reported, never silently read as no declaration.
_ATX_HEADING = re.compile(r"^ {0,3}#{1,6}[ \t]+(.*?)[ \t]*#*[ \t]*$")
# For the backstop in `read_spec_map`: a line that, once indent, list markers and quote markers are set aside,
# is an ATX "Spec map" heading, or the text of a setext one (followed by a `===` or `---` underline) in any of the
# forms `_map_words` reads ("Spec maps", "Spec-map", "**Spec map**").
_LINE_PREFIX = re.compile(r"^(?:\s+|>|[-*+]\s+|\d+[.)]\s+)+")
_HEADING_LIKE = re.compile(r"^#{1,6}\s*spec\s+map\s*#*\s*$", re.I)
_SETEXT_UNDERLINE = re.compile(r"^(?:=+|-{2,})\s*$")
_ANY_HEADING = re.compile(r"^#{1,6}\s")
_HTML_COMMENT = re.compile(r"<!--.*?-->")
# A line that can open or close a fence: its indent, a run of 3 or more backticks or tildes, the rest.
_FENCE_LINE = re.compile(r"^([ \t]*)(`{3,}|~{3,})(.*)$")
_BULLET = re.compile(r"^[-*+]\s+(.+?)\s*$")
_CODE_START = re.compile(r"^`([^`]+)`")
# A reference definition `[label]: target` (group 1 is the label, group 2 the target). Inline targets are read by `_scan_links`.
# It must fill the line (a destination and an optional title, nothing after): `[^1]: see [beta](..)` is prose with a link.
_REF_DEF = re.compile(r"^\s{0,3}\[([^\]^][^\]]*)\]:\s*<?([^\s>]+)>?(?:\s+[\"'(].*)?\s*$")
# A repo-relative path that names a live spec directory or its spec.md (group 1 is the spec name).
_SPEC_LINK = re.compile(r"^openspec/specs/([^/]+)(?:/spec\.md)?/?$")

# Prose and binary suffixes never hold a test marker; skipping them keeps a
# documented example (a fenced `# requirement:` line in a guide) from counting.
_SKIP_SUFFIXES = {
    ".md", ".markdown", ".txt", ".rst", ".json", ".lock", ".svg", ".png", ".jpg",
    ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz", ".pyc", ".woff", ".woff2",
}
_MAX_BYTES = 2_000_000


@dataclass
class Unit:
    heading: str
    body: str


@dataclass
class SpecFile:
    rel: str
    spec: str
    kind: str  # "live" | "active" | "archived"
    change: str | None
    text: str
    units: list[Unit] = field(default_factory=list)


@dataclass
class Note:
    kind: str  # "manual" | "waiting"
    heading: str | None  # None when it names no known heading
    raw: str
    change: str
    archived: bool
    prompt_half: bool
    spec: str | None = None  # the spec a `<spec> / <heading>` line names; None for the older heading-only form


class CheckerError(Exception):
    """The checker cannot do its job (exit 2)."""


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


def _norm(lines: list[str]) -> str:
    return " ".join(" ".join(lines).split())


def parse_units(text: str, mode: str, delta: bool) -> list[Unit]:
    """Requirements (or scenarios) in a spec or the ADDED/MODIFIED part of a delta.

    A requirement's body is everything under its heading, scenarios included, so
    a changed scenario changes its requirement. A scenario's body is its own lines.
    """
    reqs = _blocks(text, delta)
    if mode == "requirement":
        return [Unit(h, _norm(body)) for h, body, _ in reqs]
    return [Unit(h, _norm(sb)) for _, _, scns in reqs for h, sb in scns]


def _blocks(text: str, delta: bool) -> list[tuple[str, list[str], list[tuple[str, list[str]]]]]:
    """(heading, every line under it, [(scenario heading, its lines)]) per requirement."""
    reqs: list[tuple[str, list[str], list[tuple[str, list[str]]]]] = []
    in_scope = False
    cur_req = cur_scn = None
    fence = False
    for line in text.splitlines():
        if _FENCE.match(line):
            fence = not fence
        elif not fence:
            m = _H2.match(line)
            if m:
                title = m.group(1).strip().upper()
                in_scope = title.startswith(("ADDED", "MODIFIED")) if delta else title.startswith("REQUIREMENTS")
                cur_req = cur_scn = None
                continue
            if in_scope:
                m = _REQ.match(line)
                if m:
                    cur_req = (m.group(1), [], [])
                    reqs.append(cur_req)
                    cur_scn = None
                    continue
                if _H3.match(line):
                    cur_req = cur_scn = None
                    continue
                m = _SCN.match(line)
                if m and cur_req is not None:
                    cur_scn = (m.group(1), [])
                    cur_req[2].append(cur_scn)
                    cur_req[1].append(line)
                    continue
                if _H4.match(line):
                    cur_scn = None
        if cur_req is not None:
            cur_req[1].append(line)
            if cur_scn is not None:
                cur_scn[1].append(line)
    return reqs


def _unclosed_fence(text: str) -> bool:
    """True when a code fence opens and the file ends before it closes (`_blocks` skips everything after it)."""
    fence = False
    for line in text.splitlines():
        if _FENCE.match(line):
            fence = not fence
    return fence


_LIMIT_PATTERNS = {
    "chars": r"(\d+)\s+characters\s+or\s+(?:fewer|less)",
    "scenarios": r"(?:at\s+most|no\s+more\s+than|up\s+to)\s+(\d+)\s+scenarios",
    "requirements": r"(?:at\s+most|no\s+more\s+than|up\s+to)\s+(\d+)\s+requirements",
}
_LIMIT_WORDS = {"chars": "characters", "scenarios": "scenarios", "requirements": "requirements"}
_NUMBER_WORDS = r"one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d+"


def _specs_rules_block(text: str) -> str | None:
    """The lines of `rules:` -> `specs:` in a config, at any indent and in either list style
    (items deeper than the key, or at the key's own indent). None when there is no such key."""
    lines = text.splitlines()
    in_rules = False
    rules_indent = 0
    for i, line in enumerate(lines):
        if not in_rules:
            if re.match(r"^rules:\s*(?:#.*)?$", line):
                in_rules, rules_indent = True, 0
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= rules_indent:
            return None  # left `rules:` without meeting `specs:`
        if re.match(r"^specs:\s*(?:[|>][-+]?\s*)?(?:#.*)?$", stripped):
            block = []
            for nxt in lines[i + 1:]:
                s = nxt.strip()
                n_indent = len(nxt) - len(nxt.lstrip())
                if s and not s.startswith("#"):
                    if n_indent < indent or (n_indent == indent and not s.startswith("- ")):
                        break
                block.append(nxt)
            return "\n".join(block)
    return None


def read_format_limits(root: Path) -> tuple[dict[str, int], list[str]]:
    """The spec format limits, read from the `rules.specs` text of openspec/config.yaml (or .yml).

    Nothing is copied into this script: the numbers come from the sentences the repo
    wrote ("500 characters or fewer", "at most 3 scenarios", "at most 8 requirements").
    Returns ({limit: number}, [names of limits not found]). No config, or a config with no
    `rules.specs`, means no limits and every name is returned as not enforced.

    A `rules.specs` that exists but yields no limit at all, or that gives a number for a
    limit in words this reader does not know ("at most three scenarios"), raises: a
    guard that enforces nothing must not look like one that found nothing wrong."""
    cfg = next((p for p in (root / "openspec" / "config.yaml", root / "openspec" / "config.yml") if p.is_file()), None)
    try:
        text = cfg.read_text(encoding="utf-8-sig") if cfg else ""
    except (OSError, UnicodeDecodeError) as exc:
        raise CheckerError(f"cannot read {cfg.name}: {exc}") from exc
    block = _specs_rules_block(text)
    if block is None:
        return {}, list(_LIMIT_PATTERNS)
    found, missing = {}, []
    for name, pat in _LIMIT_PATTERNS.items():
        hit = re.search(pat, block, re.I)
        if hit:
            found[name] = int(hit.group(1))
        else:
            missing.append(name)
            word = _LIMIT_WORDS[name]
            if re.search(rf"(?i)\b(?:{_NUMBER_WORDS})\s+(?:\w+\s+)?{word}\b", block):
                raise CheckerError(f"rules.specs in {cfg.name} gives a number for {word} in wording this checker does not read; use e.g. 'at most 3 scenarios', '500 characters or fewer'")
    if not found:
        raise CheckerError(f"rules.specs in {cfg.name} states none of the format limits this checker reads")
    return found, missing


def _removed_headings(text: str) -> set[str]:
    out, in_removed = set(), False
    for line in text.splitlines():
        m = _H2.match(line)
        if m:
            in_removed = m.group(1).strip().upper().startswith("REMOVED")
        elif in_removed:
            r = _REQ.match(line)
            if r:
                out.add(r.group(1))
    return out


def _statement(body: list[str]) -> str:
    """A requirement's own sentence: its lines before the first `####` heading outside a fence."""
    out, fence = [], False
    for line in body:
        if _FENCE.match(line):
            fence = not fence
        elif not fence and _H4.match(line):
            break
        out.append(line)
    return _norm(out)


def check_format(files: list["SpecFile"], limits: dict[str, int]) -> list[str]:
    """PROBLEM lines for each live spec or active delta over the limits. Archives are not edited, so skipped.

    A delta's requirement count is the size its spec would have after archiving: the live
    spec's requirements, plus the delta's new headings, minus the ones it removes."""
    problems = []
    live = {f.spec: f for f in files if f.kind == "live"}
    for f in files:
        if f.kind == "archived":
            continue
        reqs = _blocks(f.text, f.kind != "live")
        if "requirements" in limits:
            total = len(reqs)
            if f.kind == "active":
                base = {h for h, _, _ in _blocks(live[f.spec].text, False)} if f.spec in live else set()
                total = len(base | {h for h, _, _ in reqs}) - len(base & _removed_headings(f.text))
            if total > limits["requirements"]:
                problems.append(f"PROBLEM format: {f.rel}: {total} requirements, the limit is {limits['requirements']}")
        for heading, body, scns in reqs:
            if "scenarios" in limits and len(scns) > limits["scenarios"]:
                problems.append(
                    f"PROBLEM format: {f.rel}: requirement {heading!r} has {len(scns)} scenarios, the limit is {limits['scenarios']}"
                )
            if "chars" in limits:
                n = len(_statement(body))
                if n > limits["chars"]:
                    problems.append(f"PROBLEM format: {f.rel}: requirement {heading!r} states {n} characters, the limit is {limits['chars']}")
    return problems


_ABBREVIATIONS = {
    "inc", "ltd", "corp", "approx", "etc", "vs", "cf", "dr", "mr", "mrs",
    "fig", "vol", "dept", "nos",
}
# A sentence ends at ., ! or ? (plus any closing quote, bracket or emphasis mark) followed by
# whitespace and then ANYTHING: the next sentence may open with a code span, digit, quote,
# paren or bold, so no capital letter is required.
_SENT_END = re.compile(r"([.!?])((?:[\"')\]”’]|\*\*|[*_])*)\s+(?=(\S))")
_URL = re.compile(r"(?:https?://|www\.)\S*[^\s.,;:!?)\]]")


# A code span opens and closes with a backtick run of the same length (CommonMark).
_CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)")


_BACKTICK_RUN = re.compile(r"(?<!`)`+(?!`)")


def _render_code_spans(t: str, open_len: int = 0, later_closer=None) -> tuple[str, int]:
    """(`t` with each code span replaced by `CODE`, the length of a backtick run left open at its end).

    Backtick runs pair the way a Markdown page pairs them: left to right, each opener with the next run of
    the same length, so a backtick with no partner stays literal. Used for links, where what renders matters.
    A span can run over the lines of one paragraph, so the caller carries state from line to line:
    `open_len` is the run a line before left open (0 for none), and the text of `t` up to the first run of
    that length is inside the span. `later_closer(length)` says whether a later line of the paragraph holds
    a run of that length; only then does an unpaired run on `t` open a span, which hides the rest of `t`.
    With no `later_closer`, an unpaired run stays literal, as at the end of a paragraph."""
    out, pos = "", 0
    if open_len:
        closer = next((m for m in _BACKTICK_RUN.finditer(t) if len(m.group()) == open_len), None)
        if closer is None:
            return "", open_len  # the whole line is inside the span
        out, pos = "CODE", closer.end()
    runs = [m for m in _BACKTICK_RUN.finditer(t, pos)]
    i = 0
    while i < len(runs):
        length = len(runs[i].group())
        partner = next((k for k in range(i + 1, len(runs)) if len(runs[k].group()) == length), None)
        if partner is not None:
            out += t[pos:runs[i].start()] + "CODE"
            pos, i = runs[partner].end(), partner + 1
        elif later_closer is not None and later_closer(length):
            return out + t[pos:runs[i].start()] + "CODE", length
        else:
            i += 1
    return out + t[pos:], 0


def _mask_code_spans(t: str) -> str:
    """Replace each code span with `CODE` for the sentence count. A page pairs a stray backtick with the
    next one and hides the text between them, but an author who left one stray meant the later pair as the
    span, so when any backtick is left unpaired no span is masked and every backtick is dropped. That
    over-counts when a real span holds a period and a stray sits elsewhere in the text (`Run `a. b` and
    ` more.` counts 2): a note that may say 'more than one sentence' for a text that has one. The other
    choice, masking the pairs and dropping the leftover, under-counts the case the test pins instead
    (`A stray ` mark. Then `code` here.`), and no rule tells the two apart."""
    masked = _CODE_SPAN.sub("CODE", t)
    return t.replace("`", "") if "`" in masked else masked


def count_sentences(text: str) -> int:
    """How many sentences `text` holds: 0 for blank text, else the boundaries found plus one.

    A period is not a boundary after an abbreviation (`Inc.`, `approx.`, `etc.`), a dotted
    initialism (`U.S.`, `e.g.`), or `No.` before a digit. A code span, a URL, a link target
    and an ellipsis (`...` or the one-character form) are masked first, so a period inside
    them never counts, and an ellipsis never ends a sentence. This errs toward fewer
    boundaries: a missed second sentence is a missed note, a false one is noise. The one known
    exception is an unpaired backtick (see `_mask_code_spans`)."""
    t = _mask_code_spans(" ".join(text.split()))
    t = re.sub(r"\]\([^)]*\)", "]", t)
    t = _URL.sub("URL", t)
    t = re.sub(r"\.{3,}|…", ",", t)
    if not t:
        return 0
    boundaries = 0
    for m in _SENT_END.finditer(t):
        if m.group(1) == ".":
            prev = re.search(r"(\S+)$", t[: m.start()])
            word = re.sub(r"^[\"'(\[*_“‘]+", "", prev.group(1)) if prev else ""
            if re.fullmatch(r"(?:[A-Za-z]\.)+[A-Za-z]", word) or word.lower() in _ABBREVIATIONS:
                continue
            if word.lower() == "no" and m.group(3).isdigit():
                continue
        boundaries += 1
    return boundaries + 1


def _ends_a_sentence(line: str) -> bool:
    """True when `line` closes a sentence at its end, judged as `count_sentences` judges it: more text after
    it would start another (so an abbreviation such as `Inc.` at the end of a wrapped line does not)."""
    return count_sentences(line + " x") > 1


def _purpose_paragraphs(text: str) -> list[list[str]] | None:
    """The paragraphs (runs of non-blank lines, each line stripped) under `## Purpose` (any case),
    up to the next `##` heading. None if there is no Purpose."""
    paras: list[list[str]] = []
    cur: list[str] = []
    found, fence = False, False
    for line in text.splitlines():
        if _FENCE.match(line):
            fence = not fence
        elif not fence:
            if _PURPOSE_H.match(line):
                found = True
                continue
            if found and _H2.match(line):
                break
        if not found:
            continue
        if line.strip():
            cur.append(line.strip())
        elif cur:
            paras.append(cur)
            cur = []
    if cur:
        paras.append(cur)
    return paras if found else None


def _spec_names_in(paths: set[str]) -> set[str]:
    """The spec names whose live file, or whose delta in any change (active or archived), is among `paths`."""
    out = set()
    for p in paths:
        m = _SPEC_PATH.match(p)
        if m:
            out.add(m.group(1) or m.group(2))
    return out


def purpose_notes(files: list["SpecFile"], touched: set[str] | None = None) -> list[str]:
    """One NOTE line per live spec whose Purpose is not a `**Serves:**` line plus exactly one sentence.

    `touched` is the set of spec names the branch changes (`_spec_names_in`); only those are noted, so an
    older spec the branch leaves alone does not repeat its note on every run. None means every live spec.

    A blank line after the first paragraph makes that whole paragraph the Serves line, so a hard-wrapped
    Serves line is one line, unless its first line already ends a sentence: then that line alone is the
    Serves line and the rest of the paragraph is text after it. With no blank line the Purpose is one
    paragraph and its first line is the Serves line, the rest being the sentence.

    Advisory: the repo's spec rules call this form advisory, so these are notes, never problems."""
    notes = []
    for f in files:
        if f.kind != "live" or (touched is not None and f.spec not in touched):
            continue
        paras =_purpose_paragraphs(f.text)
        why = None
        if paras is None:
            why = "has no '## Purpose' section"
        elif not paras or re.match(r"(?i)tbd\b", paras[0][0].lstrip("*_ ")):
            why = "Purpose is empty or TBD"
        else:
            if len(paras) > 1 and len(paras[0]) > 1 and _ends_a_sentence(paras[0][0]):
                # The first line already closes the Serves sentence, so the next line is the sentence after it,
                # and the paragraphs below are more text after that: not one long Serves line.
                serves_lines, rest = paras[0][:1], paras[0][1:] + [ln for p in paras[1:] for ln in p]
            elif len(paras) > 1:
                serves_lines, rest = paras[0], [ln for p in paras[1:] for ln in p]
            else:
                serves_lines, rest = paras[0][:1], paras[0][1:]
            m = re.match(r"\*\*Serves:\*\*\s*(.*)$", " ".join(serves_lines))
            if m and re.match(r"(?i)\W*tbd\b", m.group(1)):
                why = "Purpose is empty or TBD"
            elif not m or not m.group(1).strip():
                why = "Purpose does not open with a '**Serves:** <who or what it serves>' line"
            elif count_sentences(m.group(1)) > 1:
                why = "the Serves line holds more than one sentence"
            else:
                n = count_sentences(" ".join(rest))
                if n == 0:
                    why = "Purpose has no sentence after the Serves line"
                elif n > 1:
                    why = f"Purpose has {n} sentences after the Serves line, expected one"
        if why:
            notes.append(f"NOTE purpose: {f.rel}: {why}")
    return notes


_ITEM = re.compile(r"^([ \t]*)([-*+]|\d{1,9}[.)])([ \t]+|$)")

# (character, run length, indent, line it opened on, inside a list item, depth of block quote it opened in)
Fence = tuple[str, int, int, int, bool, int]

# One level of block quote marker: up to 3 spaces, `>`, and one optional space.
_QUOTE_MARK = re.compile(r"^ {0,3}>[ \t]?")


def _strip_quote(line: str) -> tuple[str, int]:
    """`line` without its block quote markers, and how many it had (its quote depth, 0 outside a quote). A line
    holds the content of the quote it sits in, so the markers are set aside as a list marker is."""
    depth = 0
    while True:
        m = _QUOTE_MARK.match(line)
        if not m:
            return line, depth
        line, depth = line[m.end():], depth + 1


# A line that starts a new block, so it cannot be a lazy continuation of a paragraph: an ATX heading, a
# thematic break, a block quote, or an HTML comment (which can interrupt a paragraph). (A fence or a list
# marker is checked beside it.)
_NEW_BLOCK = re.compile(r"^(?:#{1,6}(?:[ \t]|$)|(?:-[ \t]*){3,}$|(?:\*[ \t]*){3,}$|(?:_[ \t]*){3,}$|>|<!--)")


def _opens_fence(m: re.Match[str] | None) -> bool:
    """True when `m`, a `_FENCE_LINE` match, opens a fence. A backtick run whose info string holds a backtick
    does not: the line is a code span (`` ```x``` ``), which is paragraph text."""
    return bool(m) and not (m.group(2)[0] == "`" and "`" in m.group(3))


def _interrupts_paragraph(line: str, item: re.Match[str]) -> bool:
    """True when the list item `item` matched on `line` can start inside a paragraph. A bullet can; an ordered
    item only when it numbers from 1; an empty one never does. Otherwise (`2026.` at the start of a run-on
    line) the text goes on."""
    return bool(line[item.end():].strip()) and (item.group(2) in ("-", "+", "*") or item.group(2)[:-1] == "1")


class _Lists:
    """What `_fence_step` remembers between lines about the list items still open.

    `cols` holds the column where each open item's content begins. `lazy` is True when the last line was
    paragraph text, so that a following plain line indented less than the item still belongs to it
    (CommonMark's paragraph continuation text, "laziness"). `in_quote` is True when the last line sat in a
    block quote, so that only the line that opens the quote counts as the start of a block."""

    def __init__(self) -> None:
        self.cols: list[int] = []
        self.lazy = False
        self.in_quote = False


def _fence_step(line: str, n: int, fence: Fence | None, lists: _Lists) -> tuple[Fence | None, bool]:
    """Advance a code-fence tracker by one line: (new state, whether the line is a fence line or inside one).

    The state is None outside a fence. `lists` is the caller's `_Lists`, which this function keeps.
    List items follow the CommonMark rule: an item stays open while lines are indented to its content
    column, and ends at a less indented line, EXCEPT that a plain line directly after paragraph text (no blank
    line, not a heading, thematic break, quote, fence or list marker) is a lazy continuation of that paragraph
    and leaves the item open. A blank line, a fence or a heading ends the laziness.
    A fence opens on a run of 3 or more backticks (whose info string holds no backtick) or tildes at ANY
    indent: a fence inside a list item sits 4 or more spaces in and still renders as a fence, so a cap of 3
    would miss it and count a link shown in an example. A list marker before the run (`- ```) counts as
    indent. It closes on a bare run of the same character at least as long, indented at most 3 spaces deeper
    than the opener, so a more deeply indented run inside the fence is content. A fence opened inside a
    list item also ends at the first non-blank line indented less than its opener, as the item does on the
    page; a fence at the top level does not, since its content may sit less indented than its opener. A
    fence left open at the end hides the rest of the file, as on the page.
    Block quote markers (`> `) are set aside before a line is read, so a fence opened inside a quote is a
    fence; it ends where the quote does, at the first line with no marker, blank lines included. A line
    inside a fence that was opened outside a quote is read whole, markers and all. A fence opened at quote
    depth 2 also ends at the first line of depth 1: the inner quote ended there and took its fence with it."""
    in_quote_fence = fence is not None and fence[5] > 0
    orig_indent = len(line) - len(line.lstrip())
    core, quoted = _strip_quote(line)
    if in_quote_fence and quoted < fence[5]:
        fence = None  # the quote holding the fence has ended, and the fence with it; read this line afresh
    entering = False  # whether this line opens a block quote (the line before it was not quoted)
    if fence is None or in_quote_fence:
        line = core
        entering = bool(quoted) and not lists.in_quote
        lists.in_quote = bool(quoted)
    indent = len(line) - len(line.lstrip())
    if fence is not None and fence[4] and line.strip() and indent < fence[2]:
        fence = None  # the list item holding the fence has ended, and the fence with it; read this line afresh
    paragraph = False  # whether this line is paragraph text, which a following plain line may continue lazily
    if fence is None and line.strip():
        core = line.lstrip()
        item = _ITEM.match(line)
        # (only on a line indented to the open item: a less indented marker is outside its paragraph, and starts a list)
        if item and lists.lazy and (not lists.cols or indent >= lists.cols[-1]) and not _interrupts_paragraph(line, item):
            item = None  # `2026.` on a run-on line is text, not a list marker
        # The line that opens a quote starts a block too; its `>` was set aside above, so `_NEW_BLOCK` no longer sees
        # it, and it ends the list items that sit deeper than the `>` itself. The lines after it belong to the quote.
        starts_block = bool(entering or _NEW_BLOCK.match(core) or _opens_fence(_FENCE_LINE.match(line)) or item)
        if not (lists.lazy and not starts_block):
            while lists.cols and lists.cols[-1] > (orig_indent if entering else indent):
                lists.cols.pop()
        if item:
            gap = len(item.group(3))
            col = len(item.group(1)) + len(item.group(2)) + (gap if 0 < gap < 5 else 1)
            lists.cols.append(col)
            line = " " * col + line[item.end():]
        paragraph = not _NEW_BLOCK.match(core) and not _opens_fence(_FENCE_LINE.match(line)) and bool(line.strip())
    m = _FENCE_LINE.match(line)
    if fence is not None:
        lists.lazy = False
        closes = m and m.group(2)[0] == fence[0] and len(m.group(2)) >= fence[1] and not m.group(3).strip()
        if closes and len(m.group(1)) <= fence[2] + 3:
            return None, True
        return fence, True
    lists.lazy = paragraph
    if _opens_fence(m):
        lists.lazy = False
        return (m.group(2)[0], len(m.group(2)), len(m.group(1)), n, bool(lists.cols), quoted), True
    return None, False


def _reads_as_map_heading(line: str) -> bool:
    """True for an ATX heading whose words are "spec map" (or "spec maps") once emphasis, underscores,
    hyphens, non-breaking spaces and trailing punctuation are set aside."""
    m = _ATX_HEADING.match(line)
    return bool(m) and _map_words(m.group(1))


def _map_words(text: str) -> bool:
    """True when `text` is the words "spec map" (or "spec maps") once emphasis, underscores, hyphens,
    non-breaking spaces and trailing punctuation are set aside."""
    return re.sub(r"[\s_\-*`]+", " ", text).strip(" .:").lower() in ("spec map", "spec maps")


def _map_heading_like_lines(lines: list[str]) -> list[int]:
    """The 1-based numbers of the lines that look like the "Spec map" heading, in any fence, comment, list
    item or quote. Prose that only says the words, inline code, and a longer heading (`## Spec map notes`)
    do not look like it."""
    found = []
    for i, line in enumerate(lines):
        core = _LINE_PREFIX.sub("", line)
        if _HEADING_LIKE.match(core):
            found.append(i + 1)
        elif _map_words(core) and i + 1 < len(lines) and _SETEXT_UNDERLINE.match(_LINE_PREFIX.sub("", lines[i + 1])):
            found.append(i + 1)
    return found


def read_spec_map(root: Path, notes: list[str] | None = None) -> list[str] | None:
    """The paths or globs under `## Spec map` in the facts file, or None when the repo declares no map.

    A bullet is `- <path or glob>`, or `` - `<path or glob>` `` followed by any prose. A heading with
    no bullet, a second heading, or a line under it that is not a bullet raises: a declaration read
    loosely would turn the rule off without a word.

    With no declaration read, a line OUTSIDE any fence or comment that looks like the heading raises
    too (`##Spec map`, `- ## Spec map`). The same line INSIDE a fence or comment, which is how a facts
    file shows the format, is only a note: it is appended to `notes` when the caller passes a list."""
    facts = root / FACTS_RELPATH
    if not facts.is_file():
        return None
    try:
        lines = facts.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise CheckerError(f"cannot read {FACTS_RELPATH}: {exc}") from exc
    heads = []
    fence = None
    lists = _Lists()
    in_comment = False
    hidden_lines = set()  # lines inside a fence or an HTML comment, which cannot declare anything
    for n, line in enumerate(lines, 1):
        if fence is None:
            # A heading inside an HTML comment is not a declaration. (A line that begins with a comment is raw HTML.)
            if in_comment:
                in_comment = "-->" not in line
                hidden_lines.add(n)
                continue
            if line.lstrip().startswith("<!--"):
                _fence_step(line, n, None, lists)  # the comment starts a block, which ends the list item before it
                in_comment = "-->" not in line
                hidden_lines.add(n)
                continue
        fence, hidden = _fence_step(line, n, fence, lists)
        if hidden:
            hidden_lines.add(n)
            continue
        if _MAP_HEADING.match(line.rstrip()):
            heads.append(n)
        elif _reads_as_map_heading(line):
            raise CheckerError(f"{FACTS_RELPATH}:{n}: {line.strip()!r} reads as the spec map heading but is not '## Spec map'; write it exactly so, or rename it")
    if fence is not None:
        # The fence swallowed the rest of the file. A file with no map heading after it declares no map and
        # stays quiet; one with a heading after it has had its declaration hidden, which must not read as none.
        for n in range(fence[3] + 1, len(lines) + 1):
            if _MAP_HEADING.match(lines[n - 1].rstrip()) or _reads_as_map_heading(lines[n - 1]):
                raise CheckerError(f"{FACTS_RELPATH}:{fence[3]}: a code fence is never closed, so the spec map heading on line {n} is not read; close the fence")
    if not heads:
        # Backstop: the scans above can be fooled by Markdown a renderer reads differently from this line scan.
        # A line that looks like the "Spec map" heading, with no declaration read, may be a declaration that was
        # missed, and the guard going quiet is the one outcome this rule must not have. Prose that merely says
        # the words does not trigger it. Inside a fence or comment the line is most likely an example of the
        # format, so it is a note and never fails the run.
        like = _map_heading_like_lines(lines)
        shown = [n for n in like if n not in hidden_lines]
        if shown:
            raise CheckerError(f"{FACTS_RELPATH}:{shown[0]}: looks like the 'Spec map' heading but was not read as a declaration; write it exactly as '## Spec map'")
        if notes is not None:
            notes += [f"NOTE spec-map: {FACTS_RELPATH}:{n}: looks like the 'Spec map' heading but sits inside a code fence or comment, so it is not read as a declaration" for n in like]
        return None
    if len(heads) > 1:
        raise CheckerError(f"{FACTS_RELPATH}: '## Spec map' appears on lines {', '.join(map(str, heads))}; keep one")
    patterns = []
    for n in range(heads[0] + 1, len(lines) + 1):
        line = lines[n - 1].strip()
        if not line or (line.startswith("<!--") and line.endswith("-->")):
            continue
        if _ANY_HEADING.match(line):
            break
        m = _BULLET.match(line)
        if not m:
            raise CheckerError(f"{FACTS_RELPATH}:{n}: expected a '- <path or glob>' bullet under '## Spec map', got {line!r}")
        code = _CODE_START.match(m.group(1))
        pattern = (code.group(1) if code else m.group(1)).strip().replace("\\", "/")
        patterns.append(pattern.removeprefix("./"))
    if not patterns:
        raise CheckerError(f"{FACTS_RELPATH}:{heads[0]}: '## Spec map' lists no path; add a '- <path or glob>' bullet or remove the heading")
    return patterns


def _label_key(label: str) -> str:
    """A reference label as the page matches it: case folded, runs of whitespace as one space."""
    return " ".join(label.split()).casefold()


def _indented_code(line: str, cols: list[int], lazy: bool) -> bool:
    """True when `line` is a line of an indented code block, which renders no link.

    That is a non-blank line at least 4 columns past the content column of the list item it sits in (`cols`,
    as the line before it left them; column 0 outside a list), unless the line before it was paragraph text
    (`lazy`), in which case it only continues that paragraph."""
    if lazy or not line.strip():
        return False
    expanded = line.expandtabs(4)
    indent = len(expanded) - len(expanded.lstrip(" "))
    base = max((c for c in cols if c <= indent), default=0)
    return indent - base >= 4


_REF_LABEL = re.compile(r"\[((?:[^\[\]\\]|\\.)*)\]")
_INLINE_TARGET = re.compile(r"\(\s*<?([^)\s>]+)")


def _scan_links(masked: str, openers: list[tuple[int | None, bool]]) -> tuple[list[str], set[str]]:
    """(targets of the inline links, labels the reference links use) on one line with its code spans and
    comments already taken out.

    Only what renders as a link counts. An escaped bracket (`\\[x\\](..)`) opens nothing, an image
    (`![x](..)`) is not a link, and a `](..)` with no `[` before it is text. A reference link is
    `[text][label]`, `[label][]` or `[label]`; whether the label is defined is for the caller.

    `openers` holds the brackets still open: (position after the bracket, whether it opens an image). The
    caller keeps the list from line to line of one paragraph, so link text wrapped over two lines is one link;
    this function leaves the brackets it did not close in it, with the position gone (None), since the
    position belongs to a line that is over. A reference whose label is that text cannot be read then."""
    targets: list[str] = []
    labels: set[str] = set()
    i = 0
    while i < len(masked):
        c = masked[i]
        if c == "\\":
            i += 2
            continue
        if c == "!" and masked[i + 1:i + 2] == "[":
            openers.append((i + 2, True))
            i += 2
            continue
        if c == "[":
            openers.append((i + 1, False))
        elif c == "]" and openers:
            start, image = openers.pop()
            nxt = masked[i + 1:i + 2]
            if nxt == "(":
                m = _INLINE_TARGET.match(masked, i + 1)
                if m and not image:
                    targets.append(m.group(1))
            else:
                m = _REF_LABEL.match(masked, i + 1) if nxt == "[" else None
                if not image:
                    label = m.group(1) if m and m.group(1).strip() else (masked[start:i] if start is not None else "")
                    if label.strip():
                        labels.add(_label_key(label))
                if m:  # the `[label]` after the text is not an opener of its own
                    i = m.end()
                    continue
        i += 1
    openers[:] = [(None, image) for _, image in openers]
    return targets, labels


def _ends_paragraph(core: str) -> bool:
    """True when `core`, a line with its quote markers set aside, cannot continue the paragraph before it: a
    blank line, a heading, a rule, an underline, a fence, an HTML comment or a list item that can interrupt."""
    stripped = core.strip()
    if not stripped or _NEW_BLOCK.match(core.lstrip()) or _SETEXT_UNDERLINE.match(stripped):
        return True
    if _opens_fence(_FENCE_LINE.match(core)):
        return True
    item = _ITEM.match(core)
    return bool(item) and _interrupts_paragraph(core, item)


def _later_closer_in(lines: list[str], n: int, depth: int):
    """A function that says whether a run of backticks of a given length sits on a line after line `n`
    (1-based) in the same paragraph, at quote depth `depth`: the lines up to the first one that ends the
    paragraph (`_ends_paragraph`) or sits in another quote. `_render_code_spans` asks it before it lets an
    unpaired run open a span over a line break."""
    def later_closer(length: int) -> bool:
        for line in lines[n:]:
            core, d = _strip_quote(line)
            if d != depth or _ends_paragraph(core):
                return False
            if any(len(m.group()) == length for m in _BACKTICK_RUN.finditer(core)):
                return True
        return False
    return later_closer


def map_links(text: str) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """([(line number, target)], [(line number, problem)]) for the Markdown links in `text`.

    Links inside a code fence, an indented code block, a code span or an HTML comment are not links on the
    rendered page and are not read, nor are an image, an escaped `\\[x\\](..)` and a reference definition no link
    uses. Block quote markers are set aside first. Code spans pair as on the page, and a span can run over the lines of one paragraph (see `_render_code_spans`). Link text wrapped over several lines of one paragraph is one link.
    One pass, line by line, so a `<!--` quoted in a code span or fence opens nothing. A fence
    closes only on a bare line of the same character at least as long as the opener. A fence or a
    comment still open at the end hides the rest of the file, as on the page, and is returned as a
    problem naming the line it began on: otherwise every later link would vanish with no word said."""
    links: list[tuple[int, str]] = []
    defs: dict[str, tuple[int, str]] = {}  # normalised label -> (line, target) of its first reference definition
    openers: list[tuple[int | None, bool]] = []  # the brackets open at the end of the last line of this paragraph
    was_quoted = False  # whether the last line read sat in a block quote
    used: set[str] = set()  # normalised labels some `[text][label]`, `[label][]` or `[label]` uses
    fence = None
    lists = _Lists()
    comment_from: int | None = None
    all_lines = text.splitlines()
    span_open = 0  # length of a backtick run left open on an earlier line of this paragraph, 0 for none
    for n, line in enumerate(all_lines, 1):
        if fence is None and comment_from is not None:
            if "-->" not in line:
                continue
            comment_from, line = None, ""  # what follows the closer on its line is raw HTML too
        cols_before, lazy_before = list(lists.cols), lists.lazy
        fence, hidden = _fence_step(line, n, fence, lists)
        if hidden:
            openers.clear()
            span_open = 0
            continue
        core, quoted = _strip_quote(line)
        if _indented_code(core, cols_before, lazy_before):
            was_quoted = quoted  # (no brackets can be open here: code never interrupts a paragraph, and a blank line cleared them)
            continue
        if quoted and not was_quoted:
            openers.clear()  # a quote starts here; the text before it was another block
        was_quoted = quoted
        stripped = core.lstrip()
        if stripped.startswith("<!--"):
            openers.clear()
            # A line that begins with a comment is an HTML block: all of it is raw HTML, up to the line holding `-->`.
            if "-->" not in stripped[4:]:
                comment_from = n
            continue
        breaks = _ends_paragraph(core)
        if breaks:
            span_open = 0  # a span never runs over the end of its paragraph
        later = None if _NEW_BLOCK.match(stripped) else _later_closer_in(all_lines, n, quoted)
        rendered, span_open = _render_code_spans(core, span_open, later)
        masked = _HTML_COMMENT.sub("", rendered)
        start = masked.find("<!--")
        if start >= 0:
            masked, comment_from = masked[:start], n
        ref = _REF_DEF.match(masked)
        if ref:
            openers.clear()
            defs.setdefault(_label_key(ref.group(1)), (n, ref.group(2)))  # the first definition of a label is the one that counts
            continue
        item = _ITEM.match(core)
        # A new list item ends the paragraph before it, unless it is an ordered item that does not start at 1 or an
        # empty one: those cannot interrupt a paragraph, so on the page the text goes on.
        new_item = bool(item) and bool(core[item.end():].strip()) and (item.group(2) in ("-", "+", "*") or item.group(2)[:-1] == "1")
        closes = bool(_NEW_BLOCK.match(stripped) or _SETEXT_UNDERLINE.match(stripped.strip()))  # a heading, a rule or an underline
        if not stripped.strip() or closes or new_item:
            openers.clear()  # a blank line, a heading, a rule, an underline or a new list item ends the paragraph
        targets, labels = _scan_links(masked, openers)
        if closes:
            openers.clear()  # a heading's own unclosed bracket ends with it
        links += [(n, target) for target in targets]
        used |= labels
    # A definition renders nothing until a link uses its label, so an unused one links no spec.
    links += [(n, target) for label, (n, target) in defs.items() if label in used]
    links.sort(key=lambda link: link[0])
    issues = []
    if fence is not None:
        issues.append((fence[3], "a code fence is never closed, so the rest of the map is not read"))
    if comment_from is not None:
        issues.append((comment_from, "an HTML comment is never closed, so the rest of the map is not read"))
    return links, issues


def _link_path(map_rel: str, target: str) -> str | None:
    """The repo-relative path a link in the map file `map_rel` points at, or None for an empty target.

    The fragment and query are dropped, a relative target is resolved against the map file's folder and
    a leading `/` means the repo root. A URL or a path that leaves the repo lands on no spec path."""
    target = re.split(r"[#?]", target.replace("\\", "/"), maxsplit=1)[0]
    if not target:
        return None
    joined = target.lstrip("/") if target.startswith("/") else posixpath.join(posixpath.dirname(map_rel), target)
    return posixpath.normpath(joined)


def _glob_regex(pattern: str) -> re.Pattern[str]:
    """A repo-relative glob as a regex: `*` and `?` stay inside one folder, `**/` crosses folders, the rest is literal.

    Not `fnmatch`, where `*` also crosses `/`: a map declared as `docs/*.md` would then take in every
    nested file, and any link in one of them would count as the map linking that spec."""
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out))


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


def scan_notes(root: Path, known: set[str], universe: dict[str, set[str]] | None = None) -> list[Note]:
    """manual:/waiting: lines of every change's tasks.md. A line naming no known heading keeps heading None.

    A line is `<kind>: <spec> / <heading>: <reason>` (it covers that spec only: `universe` maps each spec to
    its headings) or the older `<kind>: <heading>: <reason>` (every spec of its change). The first form is
    tried first, and the longest name wins."""
    universe = universe or {}
    notes = []
    changes = root / "openspec" / "changes"
    if not changes.is_dir():
        return notes
    paths = sorted(changes.glob("*/tasks.md")) + sorted(changes.glob("archive/*/tasks.md"))
    for p in paths:
        archived = p.parent.parent.name == "archive"
        change = ("archive/" if archived else "") + p.parent.name
        try:
            lines = p.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            raise CheckerError(f"cannot read {p.relative_to(root).as_posix()}: {exc}") from exc
        for line in lines:
            m = _NOTE.match(line)
            if not m:
                continue
            body = m.group(2)
            if body.startswith("<"):
                continue  # a template placeholder in prose, not a note
            named = [(s, h) for s, hs in universe.items() for h in hs if body.startswith(f"{s} / {h}: ")]
            if named:
                spec, heading = max(named, key=lambda pair: len(pair[0]) + len(pair[1]))
            else:
                spec, heading = None, max((h for h in known if body.startswith(h + ": ")), key=len, default=None)
            notes.append(Note(m.group(1), heading, body, change, archived, PROMPT_HALF in body, spec))
    return notes


def resolve_scenario_marker(
    spec: str, rest: str, universe: dict[str, set[str]], owners: dict[str, dict[str, set[str]]], reqs: dict[str, set[str]]
) -> tuple[str | None, str]:
    """What a scenario marker ``scenario: <spec> / <rest>`` proves: (scenario heading, "") or (None, why not).

    ``rest`` is the two-part form's scenario heading, or the three-part form's ``<requirement> / <scenario>``.
    ``universe`` maps a spec to its scenario headings, ``owners`` a spec to each scenario's requirement headings
    and ``reqs`` a spec to its requirement headings (live specs and active deltas, as ``universe`` is).

    The whole of ``rest`` is tried as a scenario heading first, so a heading that itself holds `` / `` keeps
    its two-part meaning and the three-part form never shadows it. Otherwise ``rest`` is split at each `` / ``
    (a requirement or scenario heading may hold one too) and the marker proves the scenario when some split
    names a requirement the scenario sits under. A split whose scenario exists but whose requirement does not
    hold it is a named problem, never "names no scenario"."""
    scenarios = universe.get(spec, set())
    if rest in scenarios:
        return rest, ""
    parts = rest.split(" / ")
    splits = [(" / ".join(parts[:i]), " / ".join(parts[i:])) for i in range(1, len(parts))]
    found = [(req, scn) for req, scn in splits if scn in scenarios]
    for req, scn in found:
        if req in owners.get(spec, {}).get(scn, set()):
            return scn, ""
    if not found:
        return None, "names no scenario in any live spec or active delta"
    # Prefer the split whose requirement exists, so the message says "wrong requirement" when it can.
    req, scn = next(((r, s) for r, s in found if r in reqs.get(spec, set())), found[0])
    held = ", ".join(repr(r) for r in sorted(owners.get(spec, {}).get(scn, set())))
    if req in reqs.get(spec, set()):
        return None, f"wrong requirement: scenario {scn!r} sits under {held}, not under requirement {req!r}"
    return None, f"unknown requirement: spec {spec!r} has no requirement {req!r} (scenario {scn!r} sits under {held})"


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
    ap = argparse.ArgumentParser(description="Report requirements with no test marker or manual note. Never edits anything.")
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
