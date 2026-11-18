#!/usr/bin/env python3
"""Check a chain item's recorded head against git and GitHub before it is merged or resumed.

``/cla:multi-pr`` and ``/cla:multi-lite`` merge pull requests with nobody watching. Their safety
rules were comparisons the agent made by eye: the head the run notes recorded against ``HEAD``,
the remote branch and the PR's head; a clean tree; the PR's state. A comparison left to the reader
is the step that fails, and here a missed one merges commits nobody tested. This script makes each
comparison and states the verdict in its exit code::

    python3 "${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/chain_check.py" before-merge --notes <run-notes> --id <id> --base <base-branch>
    python3 "${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/chain_check.py" after-merge --notes <run-notes> --id <id> --base <base-branch>
    python3 "${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/chain_check.py" fix-pushed --notes <run-notes> --id <id>
    python3 "${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/chain_check.py" resume --notes <run-notes> --id <id> --base <base-branch>
    python3 "${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/chain_check.py" deps --notes <run-notes> --ids <id> [<id> ...] [--against <rev>]

It reads git and GitHub state only, and never writes the run notes: the agent writes what the
first line reports. Every subcommand takes ``--root <dir>`` (default: the working directory), the
checkout it checks against the remote ``origin``. ``gh`` runs there too. The clean-tree checks
cover the whole working tree of that checkout, whatever subdirectory ``--root`` names.

``--notes`` takes one or more files or quoted globs (``'cla.io/retro/multi-pr-run-notes-*.md'``),
which the script expands itself. A relative one is read from the PRIMARY checkout of ``--root``
(the folder that holds the shared ``.git``), because the run notes live there: from a linked
worktree, the same relative path still finds them. A chain that resumes on a later date writes a
new dated file, so an item's row may sit in an older one; the script looks in every file given,
and a row for the id in more than one file is ambiguous and exits 2. A globbed file with no
run-notes table is skipped; no table in any file exits 2.

THE RUN NOTES. The chain's own file, ``cla.io/retro/<skill>-run-notes-<date>.md``, read as it is.
The script reads the markdown table whose header names ``branch``, ``pr_number`` and ``head_sha``
(``multi-lite``: ``id | status | branch | pr_number | head_sha | deferred | review | merge_commit``;
``multi-pr``: ``change | branch | pr_number | head_sha | status | merge_commit | notes``). Columns
are found by header name; the FIRST column is the item's id. A cell is read with surrounding
spaces and backticks removed, a leading ``#`` dropped from ``pr_number``, and a cell of only ``-``
or a dash counted as empty. The PR number and the branch always come from the row, never from
the caller: the chain never acts on a PR it did not record when it opened it.

``head_sha`` must be a full commit id (40 or 64 hex digits) when present, because a prefix would
compare unequal to every real head. An empty ``head_sha`` is a recorded fact (the notes were
lost or the head never recorded), reported as ``head unverifiable (ledger lost)``.

OUTPUT. The first line is the verdict and starts with ``OK``, ``FAIL`` or ``UNCHECKED``:
  ``OK <subcommand>[ <mode>]: <what holds>``
  ``FAIL <subcommand>: <reason>`` -- the reason is the exact status text the chain writes beside
      the item (``head moved``, ``fix not committed``, ...). Several problems: the reason of the
      first, in the order each subcommand lists below.
  ``UNCHECKED <kind>: <detail>`` -- a check that could not run.
Each later line is one finding: ``PROBLEM <kind>: <detail>`` or ``UNCHECKED <kind>: <detail>``.
Callers read the exit code and the first line; keep both stable.

EXIT CODES (the same for every subcommand, and the same as ``ship_check.py``):
  0 = every check ran and passed
  1 = a check found a problem; a found problem wins over a check that could not run
  2 = no problem found, but a check could not run (no notes row, a malformed cell, ``gh`` missing
      or failing, the remote not answering, not a repository). Never a pass.

before-merge (``--base`` is the repo's default branch, resolved). Reasons, in precedence order:
  recorded PR not found            ``gh`` reports no PR with the row's number
  head unverifiable (ledger lost)  the row has no ``head_sha``
  not opened by this chain         the PR's head branch is not the row's ``branch``, or it comes
                                   from a fork
  wrong base (<name>)              the PR's base is not ``--base``
  not open (state <STATE>)         the PR's ``state`` is not ``OPEN``
  head moved                       the PR's ``headRefOid``, or ``origin``'s ``refs/heads/<branch>``
                                   (``git ls-remote``, exact name), is not ``head_sha``
  local head mismatch              ``git rev-parse HEAD`` is not ``head_sha``
  uncommitted changes              ``git status --porcelain -- ':(top)' ':(top,exclude)cla.io/retro'``
                                   lists anything; the run notes live under ``cla.io/retro``
                                   uncommitted

after-merge (``--base`` as in before-merge). ``state`` must be ``MERGED``, into ``--base``, at the
recorded ``head_sha``; the first line then names the merge commit, and a merged PR with no merge
commit exits 2. Otherwise, in precedence order:
  head unverifiable (ledger lost)            the row has no ``head_sha``
  wrong base (<name>)                        merged into another base
  merged at a head this run did not check    merged, but ``headRefOid`` is not ``head_sha``
  queued: merges later outside this run      not merged and ``autoMergeRequest`` is set
  merge not confirmed (state <STATE>)        not merged otherwise

fix-pushed (after the orchestrator commits and pushes its own fix to the row's branch):
  fix not committed   ``HEAD`` still equals the row's ``head_sha`` (no commit was made), or the
                      tree outside ``cla.io/retro`` is dirty (part of the fix is not in the commit)
  push not verified   ``origin`` has no ``refs/heads/<branch>``, or it is not ``HEAD``
  On a pass the first line names ``HEAD``: the new ``head_sha`` to write.

resume (``--base`` as in before-merge; before an item that already has a PR is handed back to
the skill or merged):
  recorded PR not found                      ``gh`` reports no PR with the row's number
  head unverifiable (ledger lost)            open or merged, and the row has no ``head_sha``
  not opened by this chain                   as in before-merge, whatever the state
  wrong base (<name>)                        the PR's base is not ``--base``, whatever the state
  PR closed without merging                  ``state`` is ``CLOSED``
  merged at a head this run did not check    merged, but ``headRefOid`` is not ``head_sha``
  head moved since review                    open, but ``headRefOid`` is not ``head_sha``
  A pass has a mode: ``OK resume open:`` (open, on the recorded head) or ``OK resume merged:``
  (merged into the base at the recorded head, with the merge commit to record; a merged PR with no
  merge commit exits 2).

deps (before a dependent item runs). For each id in ``--ids``: its row must exist, its ``status``
must start with the word ``merged``, its ``merge_commit`` must be set, and
``git merge-base --is-ancestor <merge_commit> <against>`` must succeed (``--against`` defaults to
``HEAD``; in a worktree pivot pass ``origin/<base-branch>`` after a fetch). The reason names every
dependency that fails: ``not merged into <against>: <id>, ...``.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path

# The sibling ship_check.py holds the git plumbing both scripts share. Importing it writes no
# bytecode into the installed plugin.
sys.dont_write_bytecode = True
from ship_check import (  # noqa: E402
    REMOTE,
    REMOTE_TIMEOUT,
    Findings,
    Unchecked,
    _first_err,
    _git,
    _remote_sha,
    _require_repo,
    _rev,
)

NOTES_DIR = "cla.io/retro"
_SHA = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_HEXISH = re.compile(r"^[0-9a-f]{7,64}$")
_EMPTY = {"", "-", "–", "—"}
_PR_FIELDS = "number,state,headRefOid,headRefName,baseRefName,isCrossRepository,mergeCommit,autoMergeRequest"
_NOT_FOUND = "Could not resolve to a PullRequest"

# Each subcommand's problem kinds in precedence order: the first line names the first one's reason.
_RANK = {
    kind: n
    for n, kind in enumerate([
        "not-found", "head-unverifiable", "not-chain-pr", "wrong-base", "not-open", "closed",
        "pr-head", "merged-head", "remote-head", "local-head", "dirty",
        "queued", "not-merged", "no-commit", "remote-missing", "remote-differs",
        "dep-missing", "dep-not-merged", "dep-no-merge-commit", "dep-not-in-base",
    ])
}


class Out(Findings):
    """Findings plus the status reason each problem gives, for the first line."""

    def __init__(self) -> None:
        super().__init__()
        self.reasons: list[tuple[int, str]] = []

    def fail(self, kind: str, detail: str, reason: str) -> None:
        self.problem(kind, detail)
        self.reasons.append((_RANK[kind], reason))

    def reason(self) -> str:
        return min(self.reasons)[1]


# ---------------------------------------------------------------- the run notes


@dataclass
class Row:
    item: str
    cells: dict[str, str]

    def pr(self) -> int:
        raw = self.cells.get("pr_number", "")
        if raw in _EMPTY:
            raise Unchecked("notes", f"row {self.item!r} records no pr_number")
        if not re.fullmatch(r"\d+", raw):
            raise Unchecked("notes", f"row {self.item!r} pr_number {raw!r} is not a number")
        return int(raw)

    def branch(self) -> str:
        raw = self.cells.get("branch", "")
        if raw in _EMPTY:
            raise Unchecked("notes", f"row {self.item!r} records no branch")
        if any(c.isspace() for c in raw):
            raise Unchecked("notes", f"row {self.item!r} branch {raw!r} is not one branch name")
        return raw

    def head(self) -> str | None:
        """The recorded head, or None when the row records none."""
        raw = self.cells.get("head_sha", "").lower()
        if raw in _EMPTY:
            return None
        if not _SHA.match(raw):
            raise Unchecked(
                "notes", f"row {self.item!r} head_sha {raw!r} is not a full commit id (40 or 64 hex digits)",
            )
        return raw


def _clean(cell: str) -> str:
    cell = cell.strip()
    while len(cell) >= 2 and cell[0] == "`" and cell[-1] == "`":
        cell = cell[1:-1].strip()
    return "" if cell in _EMPTY else cell


def _cells(line: str) -> list[str]:
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return [c.replace("\x00", "|") for c in body.replace("\\|", "\x00").split("|")]


_SEPARATOR = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")


def _tables(text: str) -> list[tuple[list[str], list[tuple[int, list[str]]]]]:
    """Every pipe table: (lowercased header names, [(line number, cells)])."""
    lines = text.splitlines()
    found = []
    i = 0
    while i < len(lines) - 1:
        if lines[i].lstrip().startswith("|") and _SEPARATOR.match(lines[i + 1]):
            header = [_clean(c).lower() for c in _cells(lines[i])]
            rows = []
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                rows.append((j + 1, _cells(lines[j])))
                j += 1
            found.append((header, rows))
            i = j
        else:
            i += 1
    return found


def _ledger(notes: Path) -> list[tuple[list[str], list[tuple[int, list[str]]]]]:
    """The run-notes tables in one file; [] when it has none."""
    try:
        text = notes.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise Unchecked("notes", f"{notes} does not exist") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise Unchecked("notes", f"{notes} could not be read: {exc}") from None
    return [t for t in _tables(text) if {"branch", "pr_number", "head_sha"} <= set(t[0])]


def _primary(root: Path) -> Path:
    """The primary checkout of ``root``: the folder holding the shared ``.git`` directory."""
    r = _git(root, "rev-parse", "--git-common-dir")
    if r.returncode != 0 or not r.stdout.strip():
        raise Unchecked("repo", f"git rev-parse --git-common-dir failed: {_first_err(r)}")
    common = (root / r.stdout.strip()).resolve()
    if common.name != ".git":
        raise Unchecked("repo", f"cannot tell the primary checkout from the git directory {common}")
    return common.parent


def notes_files(root: Path, specs: list[str]) -> list[Path]:
    """The files ``--notes`` names: relative ones from the primary checkout, globs expanded."""
    base = _primary(root)
    files: list[Path] = []
    for spec in specs:
        path = Path(spec) if Path(spec).is_absolute() else base / spec
        if any(c in spec for c in "*?["):
            found = sorted(Path(f) for f in glob.glob(str(path)))
            if not found:
                raise Unchecked("notes", f"no file matches {path}")
            files += found
        else:
            files.append(path)
    unique: list[Path] = []
    for f in files:
        if f.resolve() not in [u.resolve() for u in unique]:
            unique.append(f)
    return unique


def find_row(files: list[Path], item: str, need: tuple[str, ...] = ()) -> Row | None:
    """The row whose first cell is ``item``, across ``files``; None when no row names it.

    A malformed row, two rows in one file, or rows in two files raise: a chain that resumed on a
    later date writes a new file, and the script cannot tell which row is the item's.
    """
    found: dict[Path, list[Row]] = {}
    tables_seen = 0
    for notes in files:
        tables = _ledger(notes)
        tables_seen += len(tables)
        for header, rows in tables:
            missing = [c for c in need if c not in header]
            if missing:
                raise Unchecked("notes", f"{notes}: the run-notes table has no {', '.join(missing)} column")
            for lineno, cells in rows:
                if _clean(cells[0]) != item:
                    continue
                if len(cells) != len(header):
                    raise Unchecked(
                        "notes", f"{notes}:{lineno}: row {item!r} has {len(cells)} cells, the header has {len(header)}",
                    )
                values = {name: _clean(cell) for name, cell in zip(header, cells)}
                if values.get("pr_number", "").startswith("#"):
                    values["pr_number"] = values["pr_number"][1:]
                found.setdefault(notes, []).append(Row(item, values))
    if not tables_seen:
        names = ", ".join(str(f) for f in files)
        raise Unchecked("notes", f"{names}: no table with branch, pr_number and head_sha columns")
    for notes, rows in found.items():
        if len(rows) > 1:
            raise Unchecked("notes", f"{notes} has {len(rows)} rows for {item!r}")
    if len(found) > 1:
        raise Unchecked("notes", f"rows for {item!r} in {len(found)} files: {', '.join(str(f) for f in found)}")
    return next(iter(found.values()))[0] if found else None


def row_for(files: list[Path], item: str) -> Row:
    row = find_row(files, item)
    if row is None:
        raise Unchecked("notes", f"{', '.join(str(f) for f in files)}: no row for {item!r}")
    # Every subcommand that reads a row checks all three cells, so a malformed row is never half-read.
    row.pr(), row.branch(), row.head()
    return row


# ---------------------------------------------------------------- gh and git


class NotFound(Exception):
    pass


@dataclass
class PR:
    number: int
    state: str
    head_oid: str
    head_ref: str
    base_ref: str
    cross_repo: bool
    merge_commit: str | None
    auto_merge: bool


def _gh(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    exe = shutil.which("gh")
    if exe is None:
        raise Unchecked("gh", "gh was not found on PATH")
    env = dict(os.environ, GH_PROMPT_DISABLED="1", GH_NO_UPDATE_NOTIFIER="1", NO_COLOR="1")
    try:
        return subprocess.run(
            [exe, *args], cwd=root, capture_output=True, text=True, encoding="utf-8",
            errors="replace", env=env, timeout=REMOTE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise Unchecked("gh", f"'gh {' '.join(args)}' did not finish in {REMOTE_TIMEOUT}s") from None
    except OSError as exc:
        raise Unchecked("gh", f"gh could not be started: {exc}") from None


def pr_view(root: Path, number: int) -> PR:
    r = _gh(root, "pr", "view", str(number), "--json", _PR_FIELDS)
    if r.returncode != 0:
        if _NOT_FOUND in (r.stderr or "") + (r.stdout or ""):
            raise NotFound(f"gh reports no pull request #{number}")
        raise Unchecked("gh", f"'gh pr view {number}' failed: {_first_err(r)}")
    try:
        data = json.loads(r.stdout)
        state = data["state"]
        head_oid = str(data["headRefOid"]).lower()
        merge = data.get("mergeCommit")
        cross = data["isCrossRepository"]
        if not isinstance(cross, bool):
            raise TypeError(f"isCrossRepository is {cross!r}, not true or false")
        pr = PR(
            number=int(data.get("number", number)),
            state=state,
            head_oid=head_oid,
            head_ref=str(data["headRefName"]),
            base_ref=str(data["baseRefName"]),
            cross_repo=cross,
            merge_commit=str(merge["oid"]).lower() if isinstance(merge, dict) and merge.get("oid") else None,
            auto_merge=bool(data.get("autoMergeRequest")),
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise Unchecked("gh", f"'gh pr view {number}' output could not be read: {exc!r}") from None
    if pr.number != number:
        raise Unchecked("gh", f"asked for #{number}, gh answered with #{pr.number}")
    if pr.state not in ("OPEN", "CLOSED", "MERGED"):
        raise Unchecked("gh", f"#{number} has an unknown state {pr.state!r}")
    if not _SHA.match(pr.head_oid):
        raise Unchecked("gh", f"#{number} headRefOid {pr.head_oid!r} is not a commit id")
    return pr


def _dirty(root: Path) -> list[str]:
    r = _git(root, "status", "--porcelain", "--", ":(top)", f":(top,exclude){NOTES_DIR}")
    if r.returncode != 0:
        raise Unchecked("status", f"git status failed: {_first_err(r)}")
    return [line for line in r.stdout.splitlines() if line.strip()]


def _remote_head(root: Path, branch: str, out: Out) -> tuple[bool, str | None]:
    """(the remote answered, its refs/heads/<branch> sha or None)."""
    asked = len(out.unchecked)
    sha = out.attempt(_remote_sha, root, REMOTE, f"refs/heads/{branch}")
    return len(out.unchecked) == asked, (sha.lower() if sha else None)


def _not_chain_pr(pr: PR, branch: str, out: Out) -> None:
    if pr.head_ref != branch:
        out.fail("not-chain-pr", f"#{pr.number}'s head branch is {pr.head_ref}, the row records {branch}",
                 "not opened by this chain")
    elif pr.cross_repo:
        out.fail("not-chain-pr", f"#{pr.number}'s head branch {branch} is on a fork, not on {REMOTE}",
                 "not opened by this chain")


# ---------------------------------------------------------------- subcommands


def before_merge(root: Path, row: Row, base: str, out: Out) -> str:
    number, branch, head = row.pr(), row.branch(), row.head()
    if head is None:
        out.fail("head-unverifiable", f"row {row.item!r} records no head_sha", "head unverifiable (ledger lost)")
    try:
        pr = out.attempt(pr_view, root, number)
    except NotFound as exc:
        out.fail("not-found", str(exc), "recorded PR not found")
        pr = None
    if pr is not None:
        if pr.state != "OPEN":
            out.fail("not-open", f"#{number} is {pr.state}", f"not open (state {pr.state})")
        _not_chain_pr(pr, branch, out)
        if pr.base_ref != base:
            out.fail("wrong-base", f"#{number} is opened against {pr.base_ref}, not {base}", f"wrong base ({pr.base_ref})")
        if head and pr.head_oid != head:
            out.fail("pr-head", f"#{number}'s headRefOid is {pr.head_oid}, head_sha is {head}", "head moved")
    answered, remote = _remote_head(root, branch, out)
    if answered and head:
        if remote is None:
            out.fail("remote-head", f"{REMOTE} has no refs/heads/{branch}", "head moved")
        elif remote != head:
            out.fail("remote-head", f"{REMOTE} refs/heads/{branch} is {remote}, head_sha is {head}", "head moved")
    local = _rev(root, "HEAD")
    if local is None:
        raise Unchecked("head", "HEAD names no commit")
    if head and local.lower() != head:
        out.fail("local-head", f"HEAD is {local}, head_sha is {head}", "local head mismatch")
    dirty = _dirty(root)
    if dirty:
        shown = "; ".join(dirty[:5]) + (f"; and {len(dirty) - 5} more" if len(dirty) > 5 else "")
        out.fail("dirty", f"{len(dirty)} path(s) not committed: {shown}", "uncommitted changes")
    return f"OK before-merge: #{number} open on {branch} at {head}, checkout clean"


def _merged_here(pr: PR, row: Row, base: str, out: Out) -> str | None:
    """For a merged PR: its merge commit when it merged into ``base`` at the recorded head."""
    head = row.head()
    if pr.base_ref != base:
        out.fail("wrong-base", f"#{pr.number} merged into {pr.base_ref}, not {base}", f"wrong base ({pr.base_ref})")
    if head is None:
        out.fail("head-unverifiable", f"#{pr.number} merged and row {row.item!r} records no head_sha",
                 "head unverifiable (ledger lost)")
    elif pr.head_oid != head:
        out.fail("merged-head", f"#{pr.number} merged at {pr.head_oid}, head_sha is {head}",
                 "merged at a head this run did not check")
    if pr.merge_commit is None:
        raise Unchecked("gh", f"#{pr.number} is MERGED but gh names no merge commit")
    return pr.merge_commit


def after_merge(root: Path, row: Row, base: str, out: Out) -> str:
    number = row.pr()
    try:
        pr = pr_view(root, number)
    except NotFound as exc:
        raise Unchecked("gh", str(exc)) from None
    if pr.state == "MERGED":
        return f"OK after-merge: #{number} merged as {_merged_here(pr, row, base, out)}"
    if pr.auto_merge:
        out.fail("queued", f"#{number} is {pr.state} with auto-merge pending", "queued: merges later outside this run")
    else:
        out.fail("not-merged", f"#{number} is {pr.state}", f"merge not confirmed (state {pr.state})")
    return ""


def fix_pushed(root: Path, row: Row, out: Out) -> str:
    branch, head = row.branch(), row.head()
    if head is None:
        raise Unchecked("notes", f"row {row.item!r} records no head_sha to compare the fix against")
    local = _rev(root, "HEAD")
    if local is None:
        raise Unchecked("head", "HEAD names no commit")
    local = local.lower()
    if local == head:
        out.fail("no-commit", f"HEAD is still head_sha {head}: no commit was made", "fix not committed")
    dirty = _dirty(root)
    if dirty:
        shown = "; ".join(dirty[:5]) + (f"; and {len(dirty) - 5} more" if len(dirty) > 5 else "")
        out.fail("dirty", f"{len(dirty)} path(s) not in the commit: {shown}", "fix not committed")
    answered, remote = _remote_head(root, branch, out)
    if answered:
        if remote is None:
            out.fail("remote-missing", f"{REMOTE} has no refs/heads/{branch}", "push not verified")
        elif remote != local:
            out.fail("remote-differs", f"HEAD is {local}, {REMOTE} refs/heads/{branch} is {remote}", "push not verified")
    return f"OK fix-pushed: new head_sha {local}"


def resume(root: Path, row: Row, base: str, out: Out) -> str:
    number, branch, head = row.pr(), row.branch(), row.head()
    try:
        pr = pr_view(root, number)
    except NotFound as exc:
        out.fail("not-found", str(exc), "recorded PR not found")
        return ""
    _not_chain_pr(pr, branch, out)
    if pr.state == "MERGED":
        return f"OK resume merged: #{number} as {_merged_here(pr, row, base, out)}"
    if pr.base_ref != base:
        out.fail("wrong-base", f"#{number} is opened against {pr.base_ref}, not {base}", f"wrong base ({pr.base_ref})")
    if pr.state == "CLOSED":
        out.fail("closed", f"#{number} was closed without merging", "PR closed without merging")
    elif head is None:
        out.fail("head-unverifiable", f"#{number} is open and row {row.item!r} records no head_sha",
                 "head unverifiable (ledger lost)")
    elif pr.head_oid != head:
        out.fail("pr-head", f"#{number}'s headRefOid is {pr.head_oid}, head_sha is {head}", "head moved since review")
    return f"OK resume open: #{number} at {head}"


def deps(root: Path, notes: list[Path], ids: list[str], against: str, out: Out) -> str:
    target = _rev(root, against)
    if target is None:
        raise Unchecked("against", f"{against!r} names no commit")
    unmet: list[str] = []
    try:
        _deps(root, notes, ids, against, target, unmet, out)
    finally:
        # Also when a later row could not be read: the first line names what was found unmet.
        if unmet:
            out.reasons = [(0, f"not merged into {against}: {', '.join(unmet)}")]
    return f"OK deps: {', '.join(ids)} merged into {against}"


def _deps(root: Path, notes: list[Path], ids: list[str], against: str, target: str, unmet: list[str], out: Out) -> None:
    for dep in ids:
        row = find_row(notes, dep, need=("status", "merge_commit"))
        if row is None:
            out.fail("dep-missing", f"{dep}: the run notes have no row for it", "")
            unmet.append(dep)
            continue
        status = row.cells.get("status", "")
        if not re.match(r"merged(?![\w-])", status):
            out.fail("dep-not-merged", f"{dep}: status is {status or '(empty)'!r}, not merged", "")
            unmet.append(dep)
            continue
        commit = row.cells.get("merge_commit", "").lower()
        if commit in _EMPTY:
            out.fail("dep-no-merge-commit", f"{dep}: status merged but no merge_commit recorded", "")
            unmet.append(dep)
            continue
        if not _HEXISH.match(commit):
            raise Unchecked("notes", f"row {dep!r} merge_commit {commit!r} is not a commit id")
        r = _git(root, "merge-base", "--is-ancestor", commit, target)
        if r.returncode == 0:
            continue
        if r.returncode == 1 or _rev(root, commit) is None:
            out.fail("dep-not-in-base", f"{dep}: merge_commit {commit} is not in {against}", "")
            unmet.append(dep)
            continue
        raise Unchecked("ancestry", f"'git merge-base --is-ancestor {commit} {against}' failed: {_first_err(r)}")


# ---------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=".", help="the checkout to check (default: the working directory)")
    common.add_argument("--notes", nargs="+", required=True,
                        help="the chain's run-notes files or quoted globs; relative ones from the primary checkout")
    ap = argparse.ArgumentParser(
        description="Check a chain item's recorded head. Exit 0 pass, 1 problem, 2 could not check.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, text in (
        ("before-merge", "before a chain merges an item's PR"),
        ("after-merge", "after gh pr merge: did it merge"),
        ("fix-pushed", "after the chain commits and pushes its own fix"),
        ("resume", "before an item with a recorded PR is handed back or merged"),
    ):
        p = sub.add_parser(name, parents=[common], help=text)
        p.add_argument("--id", required=True, help="the item's id: the first cell of its run-notes row")
        if name in ("before-merge", "after-merge", "resume"):
            p.add_argument("--base", required=True, help="the repo's default branch, resolved")
    p = sub.add_parser("deps", parents=[common], help="before a dependent runs: every dependency merged")
    p.add_argument("--ids", nargs="+", required=True, help="the ids the item depends on")
    p.add_argument("--against", default="HEAD", help="the ref that must contain them (default: HEAD)")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    out = Out()
    try:
        _require_repo(root)
        notes = notes_files(root, args.notes)
        if args.cmd == "deps":
            ok = deps(root, notes, args.ids, args.against, out)
        else:
            row = row_for(notes, args.id)
            if args.cmd == "before-merge":
                ok = before_merge(root, row, args.base, out)
            elif args.cmd == "after-merge":
                ok = after_merge(root, row, args.base, out)
            elif args.cmd == "fix-pushed":
                ok = fix_pushed(root, row, out)
            else:
                ok = resume(root, row, args.base, out)
    except Unchecked as exc:
        out.unchecked.append(f"UNCHECKED {exc.kind}: {exc.detail}")
        ok = ""
    except Exception as exc:  # noqa: BLE001 - a crash must read as "could not check", never as a verdict
        print(f"UNCHECKED error: unexpected {type(exc).__name__}: {exc}")
        print(traceback.format_exc(), file=sys.stderr)
        return 2
    if out.problems:
        print(f"FAIL {args.cmd}: {out.reason()}")
        for line in out.problems + out.unchecked:
            print(line)
        return 1
    if out.unchecked:
        print(out.unchecked[0])
        for line in out.unchecked[1:]:
            print(line)
        return 2
    print(ok)
    return 0


if __name__ == "__main__":
    sys.exit(main())
