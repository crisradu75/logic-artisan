#!/usr/bin/env python3
"""Where a document's annotations live, and what a line in that file means.

Stdlib only, and it runs on Windows and POSIX alike — the plugin ships to repos
on both, and there is no CI to catch a divergence.

**The corpus is committed, one file per annotated document, at
`cla.io/annotations/<path-relative-to-the-repo-root>.jsonl`.** Mirroring the
document's own path is what makes the mapping total and reversible: two files
called `README.md` in different directories cannot collide, and the document a
corpus belongs to is readable straight off the corpus's path. A document outside
the repo goes to `_external/<basename>-<8 hex of its absolute path>.jsonl`,
because a path that cannot be made relative still needs a stable home.

**The repo root is resolved from git or by walking up for a `.git`, never from
this file's own location.** The plugin is installed into a cache directory that
has no fixed relationship to the repo being worked in, so a root computed by
counting `..` from `__file__` is right only in the repo that authored it.

**Append-only, one JSON object per line**, so the file diffs as additions rather
than rewrites. Four kinds of line, all keyed by `id`:

  annotation   the note as written — doc, blk, sec, line, off, text, before,
               after, note
  tombstone    {"id": ..., "deleted": true} — retracted, hidden from view
  resolution   {"id": ..., "resolved": true, "was": ..., "now": ...} — answered
               by an edit; `was` is the passage objected to and `now` the text
               that replaced it. Both are written by whoever made the edit, who
               therefore knows them, rather than reconstructed afterwards by
               matching against a moved document.
  amendment    {"id": ..., "note": ..., "edited": true} — the note rewritten

**Later lines merge onto earlier ones rather than replacing them**, so a
resolution keeps the annotation's own fields and a tombstone need carry nothing
but its id. Replacing wholesale is the obvious implementation and it is wrong:
it drops `text` and `note` the moment anything else is written against that id.
**`at` is the exception and is never overwritten** — when the objection was made
is evidence, and a resolution carrying its own `at` would redate every
annotation to the day it was answered. Resolutions write `resolved_at` instead.

**A tombstone hides an annotation; it does not remove it.** Nothing here ever
deletes a line. The alternative — rewriting the file without the record — makes
every delete a full rewrite of a file whose whole value is that it only grows,
and puts the corpus one interrupted write away from gone.

**Damage is reported, never absorbed.** A line that will not parse is skipped
*and counted*, because a corpus that has lost half its records must not read the
same as one that never had any. An unresolved merge refuses to load at all: this
file is committed and appended to on every branch, so conflict markers are an
expected state, and reading past them accepts both sides and fabricates a
corpus.
"""
import hashlib
import itertools
import json
import os
import re
import secrets
import subprocess
import threading
from datetime import datetime, timezone

LOCK = threading.Lock()
COUNTER = itertools.count(1)

CONFLICT_MARKERS = ("<<<<<<<", "=======", ">>>>>>>")
BOM = "﻿"

ANNOTATIONS_DIR = ("cla.io", "annotations")
EXTERNAL_DIR = "_external"


class CorpusUnreadable(Exception):
    """The file cannot be read without inventing content. Raised rather than
    returning a partial list, because every caller's failure mode is to print
    'no annotations' and let the reader believe the corpus is empty."""


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id():
    """Two annotations saved inside the same second must not share an id — the
    reader keys on id and merges, so a collision silently welds two notes into
    one record."""
    return "a%s-%03d-%s" % (now().replace(":", "").replace("-", ""),
                            next(COUNTER) % 1000, secrets.token_hex(2))


def repo_root(start=None):
    """The repo the annotations belong to.

    git first, because it is right in a worktree, a submodule and a linked
    checkout, where walking up for a `.git` *directory* is not — a worktree's
    `.git` is a file. The walk is the fallback for a git that is absent or
    refuses, and `start`'s own directory is the last resort — the cwd only when
    the caller passed nothing — so a caller always gets a path rather than an
    exception it has no way to act on.

    When git refuses, its reason is printed. "detected dubious ownership", a
    corrupt index and "not a repository" are different problems with the same
    silent consequence: the fallback relocates the corpus, `read_all` finds
    nothing there, and the banner says "no annotations yet; this is the first
    pass" over work that is safe in a file the reader cannot find.
    """
    start = os.path.abspath(start or os.getcwd())
    base = start if os.path.isdir(start) else os.path.dirname(start)
    try:
        out = subprocess.run(["git", "-C", base, "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=15,
                             encoding="utf-8", errors="replace")
        if out.returncode == 0 and out.stdout.strip():
            return os.path.abspath(out.stdout.strip())
        if out.stderr.strip():
            print("git could not resolve the repo root: %s" % out.stderr.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    cur = base
    while True:
        if os.path.exists(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return base
        cur = parent


def rel_to_root(doc_path, root):
    """The document's path relative to `root`, forward-slashed — or None when it
    lies outside.

    Not `os.path.relpath`, which happily returns a `..`-prefixed path for a
    document outside the tree — this needs to know that, not paper over it.
    (`ntpath.relpath` does normcase its own comparison, so casing alone is not
    the problem it looks like.) The prefix is compared under `normcase` and the *original*
    spelling is sliced out, so the corpus path keeps the document's own casing
    while the comparison stays case-insensitive where the filesystem is.
    """
    doc = os.path.abspath(doc_path)
    root = os.path.abspath(root)
    nd, nr = os.path.normcase(doc), os.path.normcase(root)
    if nd == nr:
        return None
    nr = nr.rstrip("\\/")
    if not nd.startswith(nr + os.sep):
        return None
    return doc[len(nr) + 1:].replace("\\", "/")


def doc_key(doc_path, root=None):
    """A stable, human-readable name for the document — its repo-relative path,
    or `_external/<basename>-<hash>` when it has none. Used for the corpus path,
    the page filename and the `doc` field on every record, so all three agree."""
    root = root or repo_root(doc_path)
    rel = rel_to_root(doc_path, root)
    if rel:
        return rel
    absolute = os.path.abspath(doc_path)
    digest = hashlib.sha1(
        os.path.normcase(absolute).replace("\\", "/").encode("utf-8")).hexdigest()[:8]
    return "%s/%s-%s" % (EXTERNAL_DIR, os.path.basename(absolute) or "document", digest)


def path_for(doc_path, root=None):
    """The corpus for one document, mirroring its path under cla.io/annotations."""
    root = root or repo_root(doc_path)
    parts = doc_key(doc_path, root).split("/")
    return os.path.join(root, *ANNOTATIONS_DIR, *parts) + ".jsonl"


def page_name(doc_path, root=None):
    """A filesystem-safe name for the rendered page.

    The flattened key alone is not enough: `a/b.md` and `a-b.md` both flatten to
    `a-b-md`, and two documents sharing one page file would each rebuild over the
    other's window. The digest is what keeps them apart; the readable half is
    what makes the temp directory legible when something goes wrong.
    """
    key = doc_key(doc_path, root)
    flat = re.sub(r"[^A-Za-z0-9._-]+", "-", key).strip("-") or "document"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:6]
    return "%s-%s.html" % (flat[:80], digest)


def documents_with_annotations(root=None):
    """Every document key that has a corpus, in path order. The inverse of
    strip the `.jsonl` and what remains is the document's own path — except
    for an external document, whose key carries a hash and is not invertible."""
    root = root or repo_root()
    base = os.path.join(root, *ANNOTATIONS_DIR)
    if not os.path.isdir(base):
        return []
    found = []
    for dirpath, _dirs, files in os.walk(base):
        for name in files:
            if not name.endswith(".jsonl"):
                continue
            full = os.path.join(dirpath, name)
            key = os.path.relpath(full, base).replace("\\", "/")
            found.append(key[:-len(".jsonl")])
    return sorted(found)


def read_raw(path, problems=None):
    """Every line, in file order, unmerged. None if the file does not exist.

    `problems`, if given a list, collects "line N: reason" for every line that
    could not be used. A caller that passes nothing still gets the records, but
    the corpus's own silence about damage is then its problem to explain.
    """
    # `os.path.exists` answers False for a stat that FAILED — a permission error
    # on any parent, an I/O error, or a path over MAX_PATH on Windows, which
    # corpus paths court because they are the document's own path plus ~25
    # characters. Returning None there means the caller prints "no annotations
    # yet; this is the first pass" over a corpus full of work. Three states, and
    # this is the primitive that has two.
    try:
        os.stat(path)
    except FileNotFoundError:
        return None
    except OSError as e:
        raise CorpusUnreadable(
            "%s exists but cannot be read (%s). This is not an empty corpus." % (path, e))
    try:
        with open(path, "r", encoding="utf-8", newline="") as fh:
            raw_lines = fh.readlines()
    except UnicodeDecodeError as e:
        # Not CorpusUnreadable would mean every caller tracebacks instead of
        # reporting, and the page gets a bare 500 rather than the wording that
        # tells the reader what to fix.
        raise CorpusUnreadable(
            "%s is not valid UTF-8 (%s at byte %d). Every line is evidence, so "
            "this is repaired by hand rather than by re-encoding." % (path, e.reason, e.start))
    out = []
    for n, line in enumerate(raw_lines, 1):
        line = line.strip().lstrip(BOM).strip()
        if not line:
            continue
        if line.startswith(CONFLICT_MARKERS):
            raise CorpusUnreadable(
                "%s: line %d is an unresolved merge conflict marker (%s...). "
                "Resolve it by hand — keeping BOTH sides, since every line is "
                "evidence — before reading this corpus." % (path, n, line[:7]))
        try:
            rec = json.loads(line)
        except ValueError:
            if problems is not None:
                problems.append("line %d: not valid JSON (%s...)" % (n, line[:40]))
            continue
        if not isinstance(rec, dict) or not rec.get("id"):
            if problems is not None:
                problems.append("line %d: no id, cannot be merged or amended" % n)
            continue
        out.append(rec)
    return out


def read_all(path, include_deleted=False, problems=None, merge=True):
    """Merged records, in the order their first line appeared. None if the file
    does not exist — a different state from a file holding nothing, and callers
    must say which one they found.

    Deleted ones are dropped unless asked for; resolved ones are always kept,
    because a resolved annotation is the finished half of a pair and hiding it
    is how the corpus would quietly become a list of open complaints.

    `merge=False` exists for the one test that proves the merge rule is not
    vacuous. It was a module-level global — a test seam shipped in the plugin,
    which any caller could flip for the whole process, taking the `at` exemption
    with it.
    """
    raw = read_raw(path, problems)
    if raw is None:
        return None
    merged, order = {}, []
    for rec in raw:
        rid = rec["id"]
        if rid not in merged:
            merged[rid] = {}
            order.append(rid)
        if merge:
            first_at = merged[rid].get("at")
            merged[rid].update(rec)
            if first_at:                      # the objection's own date survives
                merged[rid]["at"] = first_at
        else:
            merged[rid] = rec
    rows = [merged[r] for r in order]
    return rows if include_deleted else [r for r in rows if not r.get("deleted")]


def _refuse_if_conflicted(path):
    """A conflict marker means append() would interleave new records into a file
    read_all() will not read. Checked before writing rather than after, because
    the write is the thing that cannot be taken back."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            head = fh.read()
    except OSError as e:
        # Absorbing this would let the one guard between an append and a
        # conflicted file fail open. "Damage is reported, never absorbed" is this
        # file's whole standard, and a read that cannot happen is damage.
        raise CorpusUnreadable("cannot check %s before appending to it: %s" % (path, e))
    for mark in CONFLICT_MARKERS:
        if any(l.startswith(mark) for l in head.split("\n")):
            raise CorpusUnreadable(
                "%s carries an unresolved merge conflict; refusing to append to it" % path)


def append(path, rec):
    """One record, one line. Raises rather than losing an annotation quietly.

    Two things here are not incidental. `newline="\\n"` keeps the committed file
    LF on both platforms — text mode would write CRLF on Windows and the next
    POSIX append would put LF in the same file, which is the end of the
    append-only diff. And a file not ending in a newline gets one first: a torn
    write leaves a fragment, and appending onto it would make the pair parse as
    neither, costing the next annotation as well as the torn one.
    """
    # Refused at the WRITE, not only at the read. `read_raw` drops an id-less
    # line and counts it as damage — but by then the write has returned cleanly,
    # fsynced, and told the page it saved, in a store whose whole premise is that
    # nothing is ever lost. The server guards this on its own path; `append` is
    # the module's public writer and the server is one caller of it.
    if not isinstance(rec, dict) or not rec.get("id"):
        raise ValueError("a record with no id is dropped by every reader; "
                         "refusing to write it to %s" % path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with LOCK:
        if os.path.exists(path):
            _refuse_if_conflicted(path)
        with open(path, "a", encoding="utf-8", newline="\n") as fh:
            if fh.tell():
                with open(path, "rb") as probe:
                    probe.seek(-1, os.SEEK_END)
                    if probe.read(1) != b"\n":
                        fh.write("\n")        # close off a torn line
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())             # the page is told it saved


def split(rows):
    """Open annotations and resolved ones, in that order."""
    return ([r for r in rows or [] if not r.get("resolved")],
            [r for r in rows or [] if r.get("resolved")])
