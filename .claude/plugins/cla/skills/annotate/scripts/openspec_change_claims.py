"""Reading a change's files and the claims in them, for `openspec_change.py`.

Finds the change's folder, reads its files, and parses the claims out of the raw
markdown: promises, impacts, capabilities, tasks, requirements, decisions and
goals. Matches nothing across files; `openspec_change_links.py` does. Not a
command: import it, or use `openspec_change.py`.
"""

import os
import re


# Fixed order, never directory order: it is the order a change is written in and
# the order it is read in, and a reader should know where a file will be before
# looking. `design.md` is optional in OpenSpec.
CORE_FILES = (("proposal", "proposal.md"), ("design", "design.md"), ("tasks", "tasks.md"))

BACKTICK_RE = re.compile(r"`([^`]+)`")
# OpenSpec 1.14.1's own task line (`TASK_LINE_PATTERN` in
# dist/utils/task-progress.js), so this page counts exactly the tasks
# `openspec list` and `archive` count: any CommonMark list marker (`-`, `*`,
# `+`, `1.`, `1)`), a box holding at most one mark, and a box that a `(` or `[`
# does not follow — `- [A](url)` and `- [1][ref]` are links — unless the box is
# whitespace only. Done means the mark, lower-cased, is `x`. Every line counts,
# wherever it sits. Only the optional task number on the tail is ours.
TASK_RE = re.compile(r"^\s*(?:[-*+]|\d{1,9}[.)])\s*\[(?:\s*([^\]\s]?)\s*\](?![(\[])|\s+\])"
                     r"\s*(\d+(?:\.\d+)*)?\s*(.*)")
BULLET_RE = re.compile(r"^\s{0,3}[-*]\s+(.*)$")
DECISION_RE = re.compile(r"^\s{0,3}(\d+)\.\s+(.*)$")
# OpenSpec 1.14.1's requirement header (REQUIREMENT_HEADER_REGEX in
# dist/core/parsers/requirement-blocks.js): `###`, optional space, the word in
# any case. Its group headings are matched case-insensitively too.
REQ_RE = re.compile(r"^###\s*Requirement:\s*(.+?)\s*$", re.I)
REQ_GROUP_RE = re.compile(r"^##\s+(ADDED|MODIFIED|REMOVED|RENAMED)\s+Requirements\s*$", re.I)
_FENCE_OPEN_RE = re.compile(r"^\s*(`{3,}|~{3,})")
_FENCE_CLOSE_RE = re.compile(r"^\s*(`{3,}|~{3,})\s*$")


def fence_mask(lines):
    """True for each line inside a fenced code block, fence lines included —
    OpenSpec's `buildCodeFenceMask` (dist/core/parsers/code-fence.js). A
    requirement or group heading shown inside an example is not one."""
    mask, active = [False] * len(lines), None
    for i, line in enumerate(lines):
        if active is None:
            m = _FENCE_OPEN_RE.match(line)
            if m:
                active = (m.group(1)[0], len(m.group(1)))
                mask[i] = True
            continue
        mask[i] = True
        m = _FENCE_CLOSE_RE.match(line)
        if m and m.group(1)[0] == active[0] and len(m.group(1)) >= active[1]:
            active = None
    return mask


def _lines(text):
    """A markdown file's lines as OpenSpec reads them: a leading byte-order mark
    dropped, every line ending normalised."""
    return (text or "").lstrip(chr(0xFEFF)).replace("\r\n", "\n").replace("\r", "\n").split("\n")


def strip_md(s):
    """Inline markers removed, whitespace collapsed. The rendered page shows text
    without them, so a claim compared against a block has to lose them too."""
    s = re.sub(r"`([^`]*)`", r"\1", s or "")
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s, flags=re.S)
    s = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    return " ".join(s.split())


def sections_of(text):
    """`## Heading` -> the lines beneath it, in file order, with line numbers."""
    out, current = {}, None
    for n, line in enumerate(text.replace("\r\n", "\n").split("\n"), 1):
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            current = strip_md(m.group(1))
            out.setdefault(current, [])
            continue
        if current is not None:
            out[current].append((n, line))
    return out


# ---------------------------------------------------------------- discovery


class ChangeUnreadable(Exception):
    """This change cannot be rendered. A real exception rather than SystemExit,
    which is a BaseException: raised inside the server's worker thread it was
    caught by nothing — `_render` catches OSError, `ThreadingMixIn` catches
    Exception — and `threading` swallowed it in silence. The reader saw the
    browser's generic "Failed to fetch", identical to a dead server, while the
    one sentence saying what to fix was constructed and thrown into a void.

    Defined here, where discovery can raise it, and re-exported by
    render_change, whose name the server catches."""


def find_change(target, root):
    """The directory of a change, given an id, a path, or a directory.

    Active changes and archived ones are both annotatable — a review of what was
    shipped is as legitimate as a review of what is proposed, and the archive is
    where the finished examples live.
    """
    cands = []
    if os.path.isdir(target):
        cands.append(target)
    base = os.path.join(root, "openspec", "changes")
    cands += [os.path.join(base, target), os.path.join(base, "archive", target)]
    for c in cands:
        if os.path.isfile(os.path.join(c, "proposal.md")):
            return os.path.abspath(c)
    # An archived change is prefixed with its date, so the bare id does not match
    # the directory name; suffix-matching finds it without the caller knowing it.
    arch = os.path.join(base, "archive")
    if os.path.isdir(arch):
        hits = [d for d in sorted(os.listdir(arch)) if d.endswith("-" + target)
                and os.path.isfile(os.path.join(arch, d, "proposal.md"))]
        if len(hits) == 1:
            return os.path.abspath(os.path.join(arch, hits[0]))
    return None


def _inside(path, root):
    """Whether `path` is `root` or below it. Paths on two drives are not."""
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def _is_link(path):
    """A symlink or a Windows junction: anything whose real path is elsewhere."""
    return (os.path.normcase(os.path.realpath(path))
            != os.path.normcase(os.path.abspath(path)))


def change_files(change_dir):
    """[(key, label, absolute path)] in the fixed order, existing files only."""
    out = []
    for key, name in CORE_FILES:
        p = os.path.join(change_dir, name)
        if os.path.isfile(p):
            out.append((key, key, p))
    # A capability is a PATH, and may have several segments: `identity/user-auth`
    # lives at specs/identity/user-auth/spec.md. Walked to any depth, and the
    # path is posix-joined so the key is the same on every platform.
    #
    # A folder that cannot be listed is refused, never skipped: a delta silently
    # left out of the page is a tab the reader never knows to look for. Linked
    # folders are followed only while they resolve inside specs/, and each real
    # folder is visited once so a link cycle ends.
    specs = os.path.join(change_dir, "specs")
    found = []

    def refuse(err):
        raise ChangeUnreadable("cannot list %s: %s" % (err.filename, err.strerror or err))

    seen = set()
    walk = os.walk(specs, onerror=refuse, followlinks=True) if os.path.isdir(specs) else ()
    root_real = os.path.normcase(os.path.realpath(specs))
    for dirpath, dirs, names in walk:
        real = os.path.normcase(os.path.realpath(dirpath))
        # A link that leads out of specs/ is not part of this change: its
        # folder may hold another change's deltas, or anything else.
        if real in seen or not _inside(real, root_real):
            dirs[:] = []
            continue
        seen.add(real)
        # Real folders before linked ones, so a link to a folder already under
        # specs/ is the copy that gets skipped, never the folder's own name.
        dirs.sort(key=lambda n: (_is_link(os.path.join(dirpath, n)), n))
        if "spec.md" in names and os.path.abspath(dirpath) != os.path.abspath(specs):
            cap = os.path.relpath(dirpath, specs).replace(os.sep, "/")
            found.append((cap, os.path.join(dirpath, "spec.md")))
    for cap, p in sorted(found):
        out.append(("spec-" + cap, "spec · " + cap, p))
    return out


# ---------------------------------------------------------------- claims


def claim_id(file_key, num):
    """The join key for links, coverage and block binding. Spelled here and
    nowhere else: `detect_links` used to rebuild it by hand for citations, and a
    format change would have turned every citation into a silent no-op."""
    return "%s:%s" % (file_key, num)


def _claim(file_key, kind, num, text, line, **extra):
    assert kind in CLAIM_KINDS, kind
    cid = claim_id(file_key, num)
    rec = {"id": cid, "file": file_key, "kind": kind, "num": num,
           "text": strip_md(text), "raw": text, "line": line}
    rec.update(extra)
    return rec


def promises(text):
    """The proposal's `## What Changes` bullets — what the change promises to do.

    Only top-level bullets. A sub-bullet elaborates its parent rather than
    promising something separate, and counting it as its own claim reports the
    parent as covered while its detail goes unmentioned by any task.
    """
    out = []
    for title, lines in sections_of(text).items():
        if title.lower() != "what changes":
            continue
        for n, line in lines:
            if line[:1] not in ("-", "*"):
                continue
            m = BULLET_RE.match(line)
            if m:
                out.append(_claim("proposal", "promise", "p%d" % (len(out) + 1),
                                  m.group(1), n))
    return out


def impacts(text):
    """`## Impact` bullets. Claims about consequence rather than work, so they
    are shown but never counted as uncovered: nothing is owed against them."""
    out = []
    for title, lines in sections_of(text).items():
        if title.lower() != "impact":
            continue
        for n, line in lines:
            m = BULLET_RE.match(line)
            if m and line[:1] in ("-", "*"):
                out.append(_claim("proposal", "impact", "i%d" % (len(out) + 1),
                                  m.group(1), n))
    return out


def capabilities(text):
    """Capability names under `## Capabilities`, and whether they are new."""
    out = []
    for title, lines in sections_of(text).items():
        if "capabilit" not in title.lower():
            continue
        new = False
        for n, line in lines:
            h = re.match(r"^###\s+(.+?)\s*$", line)
            if h:
                new = "new" in h.group(1).lower()
                continue
            m = BULLET_RE.match(line)
            if not m or line[:1] not in ("-", "*"):
                continue
            name = BACKTICK_RE.search(m.group(1))
            if name:
                out.append({"name": name.group(1), "new": new, "line": n,
                            "text": strip_md(m.group(1))})
    return out


def tasks(text):
    """Every task line `TASK_RE` matches, with its done state and its `## N.`
    group. A line counts as a task here exactly when OpenSpec 1.14.1 counts it,
    and is done exactly when OpenSpec calls it done: the mark is `x` in either
    case. Every other mark is a task not yet done.

    A leading byte-order mark is dropped first: OpenSpec's `\\s` matches it, so
    a first task line behind one still counts there. Lines inside a code fence
    count, as they do in OpenSpec (dist/utils/task-progress.js)."""
    out, group = [], ""
    for n, line in enumerate(_lines(text), 1):
        h = re.match(r"^##\s+(.+?)\s*$", line)
        if h:
            group = strip_md(h.group(1))
            continue
        m = TASK_RE.match(line)
        if not m:
            continue
        num = m.group(2) or str(len(out) + 1)
        out.append(_claim("tasks", "task", num, m.group(3), n,
                          done=(m.group(1) or "").lower() == "x", group=group))
    return out


def requirements(text, file_key):
    """`### Requirement: X` headings, tagged with the ADDED/MODIFIED/REMOVED
    group they sit under. A REMOVED requirement still needs a task — deleting a
    requirement is work — so it is a claim like any other.

    Any other `##` heading ends the group: a new capability's delta opens with
    `## Purpose`, which is not a group, and a heading under one is in none.
    Lines inside a code fence are skipped, as OpenSpec skips them: a heading
    shown in an example is not a requirement."""
    out, group = [], ""
    lines = _lines(text)
    mask = fence_mask(lines)
    for n, line in enumerate(lines, 1):
        if mask[n - 1]:
            continue
        g = REQ_GROUP_RE.match(line)
        if g:
            group = g.group(1).upper()
            continue
        if re.match(r"^##\s", line):
            group = ""
            continue
        m = REQ_RE.match(line)
        if m:
            out.append(_claim(file_key, "requirement", "r%d" % (len(out) + 1),
                              m.group(1), n, group=group))
    return out


def decisions(text):
    """The design's numbered decisions. The bold lead sentence is the title —
    the rest is the argument, and a decision is cited by its number."""
    out = []
    for title, lines in sections_of(text).items():
        if title.lower() != "decisions":
            continue
        for n, line in lines:
            m = DECISION_RE.match(line)
            if not m:
                continue
            body = m.group(2)
            lead = re.match(r"\*\*(.+?)\*\*", body)
            out.append(_claim("design", "decision", m.group(1),
                              lead.group(1) if lead else body, n, body=strip_md(body)))
    return out


def goals(text):
    """`## Goals / Non-Goals` bullets — cited by tasks and worth linking, but
    never owed anything, so they are never uncovered."""
    out = []
    for title, lines in sections_of(text).items():
        if "goal" not in title.lower():
            continue
        for n, line in lines:
            m = BULLET_RE.match(line)
            if m and line[:1] in ("-", "*"):
                out.append(_claim("design", "goal", "g%d" % (len(out) + 1),
                                  m.group(1), n))
    return out


# Every kind a claim may have. `coverage` scopes ubiquity to promises and falls
# back to all claims when it finds none — so a typo in one producer does not skip
# a branch, it silently restores the all-claims rule the sweep measured wrong.
CLAIM_KINDS = frozenset({"promise", "impact", "requirement", "decision", "goal", "task"})
