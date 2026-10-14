#!/usr/bin/env python3
"""Report requirements (or scenarios) that no test or manual note proves.

A repo's OpenSpec rules ask that each requirement a change adds or modifies is
proven by a test carrying a comment line ``requirement: <spec> / <heading>``, or
by a tasks.md line ``manual: <heading>: <reason>``. Nothing but a reviewer reads
that rule, and a consuming repo has no test gate over the plugin, so this is a
program a repo runs, not a test::

    python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/check_spec_proof.py

It only reports. It never edits, files or opens anything.

PROOF GRANULARITY. The default is per requirement. A repo opts in to per-scenario
proof (``scenario: <spec> / <heading>`` markers, scenario headings in ``manual:``
lines) with exactly one line in ``cla.io/project-facts.md``::

    - Test proof granularity: requirement
    - Test proof granularity: scenario

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
    heading that no live spec or active delta holds. A marker of the other
    granularity is also reported, since nothing reads it.
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
    requirement in a live spec or active delta with no ``#### Scenario:`` heading.
  - ``fence``: a live spec or active delta with a code fence that is never closed
    (everything after it is hidden from the checker).
  - ``validate``: only with ``--validate``; ``openspec validate --specs --strict``
    failed (skipped, and said so, when the CLI is absent).

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
such as a shallow clone, no file scanned for markers, an unexpected crash).
Only "no default branch exists at all" turns the changed-unit rule off with
exit 0, and the output says so.

KNOWN LIMIT. A ``manual:`` line names a heading, not a spec, so one line covers a
changed unit of that heading in every spec of a touched change. That is the
format the repo's tasks rule fixes; two specs sharing a heading need a rename.

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
from dataclasses import dataclass, field
from pathlib import Path

FACTS_RELPATH = "cla.io/project-facts.md"
GRANULARITIES = ("requirement", "scenario")
_FACT_STRICT = re.compile(r"^- Test proof granularity: (requirement|scenario)$")
_FACT_LOOSE = re.compile(r"^[\s>]*(?:(?:[-*+]|\d+[.)])\s*)?[*_`]*test proof granularity", re.I)

_H2 = re.compile(r"^##\s+(?!#)(.+?)\s*$")
_H3 = re.compile(r"^###\s+(?!#)")
_REQ = re.compile(r"^###\s+Requirement:\s*(.+?)\s*$")
_SCN = re.compile(r"^####\s+Scenario:\s*(.+?)\s*$")
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
_REQ_ANYWHERE = re.compile(r"(?m)^###\s+Requirement:")
_DELTA_SECTION = re.compile(r"(?mi)^##\s+(?:ADDED|MODIFIED|REMOVED|RENAMED)\b")
_NOTE = re.compile(
    r"^\s*(?:[-*+]\s+)?(?:\[[ xX]\]\s+)?(?:\d+(?:\.\d+)*\.?\s+)?(manual|waiting):\s+(.+?)\s*$"
)
PROMPT_HALF = "(prompt half)"

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


class CheckerError(Exception):
    """The checker cannot do its job (exit 2)."""


def _git(root: Path, *args: str) -> tuple[int, str]:
    try:
        r = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except OSError:
        return 127, ""
    return r.returncode, r.stdout


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
    rc, out = _git(Path.cwd(), "rev-parse", "--show-toplevel")
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
        rc, out = _git(root, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
        if rc == 0 and out.strip():
            candidates.append(out.strip().removeprefix("refs/remotes/"))
        candidates += ["origin/main", "origin/master", "main", "master"]
    if not explicit and _git(root, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")[0] != 0:
        return None, "no commit on HEAD yet"
    failed = []
    for ref in candidates:
        rc, _ = _git(root, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
        if rc != 0:
            continue
        rc, out = _git(root, "merge-base", "HEAD", ref)
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
        rc, text = _git(root, *args)
        if rc == 0:
            out |= {p for p in text.split("\0") if p}
    return out


def _base_text(root: Path, base: str, rel: str) -> str | None:
    rc, out = _git(root, "show", f"{base}:./{rel}")
    return out if rc == 0 else None


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


def scan_markers(root: Path, globs: list[str]) -> tuple[list[tuple[str, str, str, str]], int, list[str]]:
    """Return ([(kind, spec, heading, relpath)], files scanned, files skipped).

    A file is skipped only when it is binary (a NUL byte), unreadable or over the size
    cap, and each is returned by name so the run can say so. Text in another encoding
    is still scanned, with undecodable bytes replaced."""
    rc, out = _git(root, "ls-files", "-co", "--exclude-standard", "-z")
    if rc == 0:
        rels = [p for p in out.split("\0") if p]
    else:
        rels = []
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d not in {".git", "node_modules", "__pycache__", ".venv"}]
            rels += [(Path(dp) / fn).relative_to(root).as_posix() for fn in fns]
    found = []
    skipped: list[tuple[str, str]] = []
    scanned = 0
    for rel in sorted(set(rels)):
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


def scan_notes(root: Path, known: set[str]) -> list[Note]:
    """manual:/waiting: lines of every change's tasks.md. A line naming no known heading keeps heading None."""
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
            heading = max((h for h in known if body.startswith(h + ": ")), key=len, default=None)
            notes.append(Note(m.group(1), heading, body, change, archived, PROMPT_HALF in body))
    return notes


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
                for heading, _, scns in _blocks(f.text, f.kind != "live"):
                    if not scns:
                        problems.append(f"PROBLEM empty: {f.rel}: requirement {heading!r} has no '#### Scenario:' heading, so none is checked")

    limits, unenforced = read_format_limits(root)
    problems += check_format(files, limits)

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
        elif heading not in universe.get(spec, set()):
            problems.append(f"PROBLEM dangling: {rel}: '{kind}: {spec} / {heading}' names no {mode} in any live spec or active delta")
        else:
            marked.add((spec, heading))

    notes = scan_notes(root, known)
    for n in notes:
        if n.heading is None and not n.archived:
            problems.append(f"PROBLEM dangling: openspec/changes/{n.change}/tasks.md: '{n.kind}: {n.raw}' names no {mode} heading")
        if n.kind == "waiting" and n.archived:
            problems.append(f"PROBLEM waiting: openspec/changes/{n.change}/tasks.md: archived but still waiting: {n.raw!r}")

    base, base_note = (None, "")
    changed: dict[str, list[Unit]] | None = None
    touched: set[str] = set()
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
        changed = {f.rel: changed_units(root, base, f, mode) for f in files}
        for p in paths:
            m = re.match(r"openspec/changes/((?:archive/)?[^/]+)/", p)
            if m:
                touched.add(m.group(1))

    def notes_for(heading: str, change: str | None, kind: str) -> list[Note]:
        return [
            n for n in notes
            if n.kind == kind and n.heading == heading
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
                manual = notes_for(u.heading, scope, "manual")
                whole = [n for n in manual if not n.prompt_half]
                if whole:
                    continue
                if manual:
                    problems.append(f"PROBLEM prompt-half: {where}: '(prompt half)' manual line but no {mode} marker for the test half")
                    continue
                if any(not n.archived for n in notes_for(u.heading, scope, "waiting")):
                    covered_waiting += 1
                    continue
                problems.append(f"PROBLEM uncovered: {where}: changed {mode} has no '{mode}: {f.spec} / {u.heading}' marker and no 'manual: {u.heading}: <reason>' line")

    whole_manual = {n.heading for n in notes if n.kind == "manual" and not n.prompt_half and n.heading}
    for n in notes:
        if n.kind == "waiting" and n.heading and not n.archived:
            if n.heading in whole_manual or any((s, n.heading) in marked for s in universe):
                problems.append(f"PROBLEM waiting: openspec/changes/{n.change}/tasks.md: {n.heading!r} is already proven, so it is no longer waiting")

    if validate:
        _validate(root, problems, out)

    # Counts (information only, never a gate).
    all_units = [(f.spec, u.heading) for f in files if f.kind != "archived" for u in f.units]
    covered = sum(1 for s, h in all_units if (s, h) in marked or h in whole_manual)
    kinds = {k: sum(1 for f in files if f.kind == k) for k in ("live", "active", "archived")}
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
        f"problems: {len(problems)}",
    ]
    return (1 if problems else 0), problems + out


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
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())
