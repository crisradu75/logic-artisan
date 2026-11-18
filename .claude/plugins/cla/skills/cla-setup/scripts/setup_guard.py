#!/usr/bin/env python3
"""Check that /cla:cla-setup left alone the files it promises to leave alone.

cla-setup promises, in prose, that a run leaves the repo's instruction files byte-identical, never
touches the Claude Code settings or the repo's own rules files, always skips an existing feedback
``notes.md``, never reshapes a machine-read ``*.local.md`` file, never creates the terminology file
or an overlay, and changes an existing terminology file, local file or overlay only on the owner's
yes. Nothing checked those promises. This script records the files at the start of a run and
compares them at the end::

    python3 "${CLAUDE_PLUGIN_ROOT}/skills/cla-setup/scripts/setup_guard.py" snapshot --out <file> [--root <dir>]
    python3 "${CLAUDE_PLUGIN_ROOT}/skills/cla-setup/scripts/setup_guard.py" verify --snapshot <file> [--approved <path> ...] [--root <dir>]

``--root`` (default: the working directory) may be anywhere inside the checkout; the script works
on its top level.

WHY A SNAPSHOT AND NOT GIT. ``git diff`` and ``git status`` compare with the last commit, not with
the start of the run, so they cannot tell three cases apart: a protected file the owner had already
edited before the run (git shows it changed whether or not the run touched it), a gitignored file
(``cla.io/fleet.local.md`` and ``CLAUDE.local.md`` are usually ignored, so git shows nothing
whatever the run did) and an untracked overlay that existed before the run (``??`` either way). The
snapshot hashes the files on disk, so it sees each of those. Git is used only to find the
checkout's top level and git directories, ``HEAD``, nested instruction files git can see, and
whether ``--out`` is ignored.

PROTECTED PATHS (repo-relative) and what may happen to each during a run:
  instruction files  ``CLAUDE.md``, ``AGENTS.md`` and ``CLAUDE.local.md`` at the root and in
                     ``.claude/``, recorded even when absent or gitignored, plus any root or
                     ``.claude/`` file whose name matches one of them in another letter case (a
                     lowercase ``claude.md`` on Linux), plus any file of exactly those names deeper
                     in the tree that git tracks or sees as untracked. No change, creation or
                     deletion; ``--approved`` does not cover them, since the skill never touches them.
  settings           ``.claude/settings*.json`` and ``.claude-plugin/plugin.json`` (a non-goal of
                     the skill). Same as instruction files.
  rules files        every ``*.md`` under ``.claude/rules/`` except ``cla-economy.md``, which the
                     skill owns and replaces. Same as instruction files: the skill writes repo
                     content only under ``cla.io/`` and the spec map path.
  feedback notes     ``cla.io/feedback/notes.md``. Created when absent (item 3's seed); an existing
                     one is never changed or deleted, approved or not.
  local files        every ``*.local.md`` under ``cla.io/``. Any change, creation or deletion needs
                     ``--approved`` (item 12 adds token-list entries on a yes).
  terminology        ``cla.io/terminology.md``. Never created, approved or not; a change or deletion
                     needs ``--approved`` (item 11 reconciles it on a yes).
  overlays           ``cla.io/overlays/*.md`` other than ``*.local.md``. Never created, approved or
                     not; a change or deletion needs ``--approved`` (item 13 edits or deletes one on
                     a yes).
A gitignored instruction file deeper than ``.claude/`` is not found, so not checked.

SNAPSHOT FILE. JSON: ``{"version": 1, "root": <absolute top level>, "created": <unix seconds>,
"head": <HEAD commit or null when the branch has none>, "files": {<path>: <sha256 hex, a
"not-a-file:..." marker, or null>}}``. ``null`` means absent. The overlays present at the start are
the overlay keys whose value is not ``null``. ``snapshot`` refuses (exit 2) an ``--out`` inside a
git directory, inside the checkout unless git ignores it, at a protected path, at a directory, or at
an existing file that is neither empty nor a setup snapshot; it writes through a new temporary file
in the same folder and moves it into place, so it never overwrites any other file.

STALE SNAPSHOT. ``verify`` exits 2, never 0 or 1, when the snapshot was taken more than
``MAX_AGE_HOURS`` ago or more than ``FUTURE_SKEW_SECONDS`` in the future, or when ``HEAD`` has
moved since to a commit that does not descend from the recorded one (a branch switch or a reset
changes files the run never touched), or when the branch had a commit and now has none. A commit
that descends from the recorded one passes: the comparison is of the files on disk, not of commits.

OUTPUT. The first line is the verdict, and its first word is ``OK``, ``FAIL`` or ``UNCHECKED``.
Each later line is one finding: ``PROBLEM <kind>: <path> (<why>)``, where the kind is ``changed``,
``created`` or ``deleted``, or ``UNCHECKED <kind>: <detail>``. Callers read the exit code and the
first line, and report every later line; keep all three stable. A passing ``verify`` names each
approved change on its first line.

EXIT CODES (both subcommands):
  0 = every check ran and passed
  1 = a protected file changed without the owner's yes, or an overlay or the terminology file was
      created (``PROBLEM`` lines say which); a found problem wins over a check that could not run,
      whose ``UNCHECKED`` lines follow the ``PROBLEM`` lines
  2 = no problem found, but a check could not run (not a repository, a missing, corrupt or stale
      snapshot, a snapshot of another checkout, an unreadable file, a bad argument). Never a pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

VERSION = 1
MAX_AGE_HOURS = 24
FUTURE_SKEW_SECONDS = 300
INSTRUCTION_NAMES = ("CLAUDE.md", "AGENTS.md", "CLAUDE.local.md")
INSTRUCTION_DIRS = ("", ".claude/")  # where a name in another letter case is still protected
SETTINGS_FILES = (".claude/settings.json", ".claude/settings.local.json", ".claude-plugin/plugin.json")
RULES_DIR = ".claude/rules"
ECONOMY_RULES = ".claude/rules/cla-economy.md"
NOTES = "cla.io/feedback/notes.md"
TERMINOLOGY = "cla.io/terminology.md"
OVERLAY_DIR = "cla.io/overlays"
LOCAL_SUFFIX = ".local.md"
FIXED = (
    *(d + n for d in INSTRUCTION_DIRS for n in INSTRUCTION_NAMES),
    *SETTINGS_FILES,
    NOTES,
    TERMINOLOGY,
)
_FOLDED = {n.casefold() for n in INSTRUCTION_NAMES}


class Unchecked(Exception):
    """A check that could not run. Carries (kind, detail)."""

    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except FileNotFoundError:
        raise Unchecked("git", "the git binary was not found") from None
    except OSError as exc:
        raise Unchecked("git", f"git could not be started: {exc}") from None


def _first_err(r: subprocess.CompletedProcess[str]) -> str:
    text = (r.stderr or r.stdout or "").strip().splitlines()
    return text[0] if text else f"exit {r.returncode}"


def _toplevel(start: Path) -> Path:
    if not start.is_dir():
        raise Unchecked("repo", f"{start} is not a directory")
    r = _git(start, "rev-parse", "--show-toplevel")
    if r.returncode != 0 or not r.stdout.strip():
        raise Unchecked("repo", f"{start} is not inside a git working tree: {_first_err(r)}")
    return Path(r.stdout.strip()).resolve()


def _head(root: Path) -> str | None:
    """The HEAD commit, or None on a branch with no commit yet."""
    r = _git(root, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip()
    if r.returncode == 1:
        return None
    raise Unchecked("git", f"git rev-parse HEAD failed: {_first_err(r)}")


def _git_dirs(root: Path) -> list[Path]:
    dirs = []
    for flag in ("--absolute-git-dir", "--git-common-dir"):
        r = _git(root, "rev-parse", flag)
        if r.returncode != 0 or not r.stdout.strip():
            raise Unchecked("git", f"git rev-parse {flag} failed: {_first_err(r)}")
        p = Path(r.stdout.strip())
        dirs.append((p if p.is_absolute() else root / p).resolve())
    return dirs


# ---------------------------------------------------------------- what is protected


def kind_of(rel: str) -> str:
    """The class of a protected repo-relative path. Raises ValueError for any other path."""
    folder, _, name = rel.rpartition("/")
    folder = folder + "/" if folder else ""
    if name in INSTRUCTION_NAMES or (folder in INSTRUCTION_DIRS and name.casefold() in _FOLDED):
        return "instruction"
    if rel in SETTINGS_FILES or (folder == ".claude/" and name.startswith("settings") and name.endswith(".json")):
        return "settings"
    if rel.startswith(RULES_DIR + "/") and rel.endswith(".md") and rel != ECONOMY_RULES:
        return "rules"
    if rel == NOTES:
        return "notes"
    if rel.startswith("cla.io/") and rel.endswith(LOCAL_SUFFIX):
        return "local"
    if rel == TERMINOLOGY:
        return "terminology"
    if rel.startswith(OVERLAY_DIR + "/") and rel.count("/") == 2 and rel.endswith(".md"):
        return "overlay"
    raise ValueError(f"not a protected path: {rel}")


def _is_protected(rel: str) -> bool:
    try:
        kind_of(rel)
        return True
    except ValueError:
        return False


def _listdir(root: Path, folder: str) -> list[str]:
    d = root / folder
    try:
        return sorted(os.listdir(d)) if d.is_dir() else []
    except OSError as exc:
        raise Unchecked("read", f"cannot list {folder or '.'}: {exc}") from None


def _walk_md(root: Path, folder: str, suffix: str) -> list[str]:
    base = root / folder
    found: list[str] = []
    if not base.is_dir():
        return found
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        dirnames.sort()
        found.extend((Path(dirpath) / n).relative_to(root).as_posix() for n in filenames if n.endswith(suffix))
    return found


def _same_file(a: Path, b: Path) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def _case_variants(root: Path) -> list[str]:
    """Root and ``.claude/`` files named like an instruction file in another letter case.

    On a case-insensitive file system the variant is the same file as the fixed name, which is
    already recorded, so it is skipped rather than reported twice."""
    found = []
    for folder in INSTRUCTION_DIRS:
        for name in _listdir(root, folder.rstrip("/")):
            if name.casefold() in _FOLDED and name not in INSTRUCTION_NAMES:
                canonical = next(n for n in INSTRUCTION_NAMES if n.casefold() == name.casefold())
                if not _same_file(root / folder / name, root / folder / canonical):
                    found.append(folder + name)
    return found


def _nested_instruction_files(root: Path) -> list[str]:
    """Instruction files git tracks or sees as untracked, at any depth."""
    r = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if r.returncode != 0:
        raise Unchecked("git", f"git ls-files failed: {_first_err(r)}")
    return [p for p in r.stdout.split("\0") if p and p.rsplit("/", 1)[-1] in INSTRUCTION_NAMES]


def protected_paths(root: Path) -> set[str]:
    paths = set(FIXED)
    paths.update(_case_variants(root))
    paths.update(_nested_instruction_files(root))
    paths.update(".claude/" + n for n in _listdir(root, ".claude") if _is_protected(".claude/" + n))
    paths.update(p for p in _walk_md(root, RULES_DIR, ".md") if p != ECONOMY_RULES)
    paths.update(_walk_md(root, "cla.io", LOCAL_SUFFIX))
    paths.update(OVERLAY_DIR + "/" + n for n in _listdir(root, OVERLAY_DIR) if _is_protected(OVERLAY_DIR + "/" + n))
    return paths


def _digest(root: Path, rel: str) -> str | None:
    """The file's SHA-256, or None when absent. A non-file at the path hashes as a fixed marker."""
    p = root / rel
    if not os.path.lexists(p):
        return None
    if p.is_dir():
        return "not-a-file:directory"
    h = hashlib.sha256()
    try:
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 16), b""):
                h.update(chunk)
    except FileNotFoundError:
        # A symlink whose target is gone: present as a link, absent as a file.
        return "not-a-file:dangling-link"
    except OSError as exc:
        raise Unchecked("read", f"{rel}: {exc}") from None
    return h.hexdigest()


# ---------------------------------------------------------------- the snapshot file


def _is_digest(v: object) -> bool:
    if v is None:
        return True
    if not isinstance(v, str):
        return False
    if v.startswith("not-a-file:"):
        return True
    return len(v) == 64 and all(c in "0123456789abcdef" for c in v)


def _shape_problem(data: object) -> str | None:
    """Why ``data`` is not a version-1 setup snapshot, or None when it is one."""
    if not isinstance(data, dict) or data.get("version") != VERSION:
        return f"is not a version-{VERSION} setup snapshot"
    files, created, head = data.get("files"), data.get("created"), data.get("head")
    if not isinstance(files, dict) or not files or not all(
        isinstance(k, str) and _is_digest(v) for k, v in files.items()
    ):
        return "has no valid 'files' map"
    for rel in files:
        if not _is_protected(rel):
            return f"records {rel!r}, which is not a protected path"
    if not all(rel in files for rel in FIXED):
        return "does not record every fixed protected path"
    if not isinstance(data.get("root"), str):
        return "has no 'root'"
    if isinstance(created, bool) or not isinstance(created, (int, float)):
        return "has no 'created' time"
    if head is not None and not (
        isinstance(head, str) and len(head) in (40, 64) and all(c in "0123456789abcdef" for c in head)
    ):
        return "has no valid 'head'"
    return None


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _check_out(root: Path, out: Path) -> None:
    """Refuse an --out that would overwrite or add anything the user owns."""
    for gd in _git_dirs(root):
        if _inside(out, gd):
            raise Unchecked("out", f"{out} is inside the git directory {gd}")
    if _inside(out, root):
        rel = out.relative_to(root).as_posix()
        if _is_protected(rel):
            raise Unchecked("out", f"{rel} is a protected path; write the snapshot to the session scratchpad")
        r = _git(root, "check-ignore", "-q", "--", rel)
        if r.returncode == 1:
            raise Unchecked("out", f"{rel} is inside the repo and git does not ignore it; "
                                   "write the snapshot to the session scratchpad or a gitignored folder")
        if r.returncode != 0:
            raise Unchecked("out", f"git check-ignore failed on {rel}: {_first_err(r)}")
    if out.is_dir():
        raise Unchecked("out", f"{out} is a directory")
    if os.path.lexists(out):
        try:
            existing = out.read_bytes()
        except OSError as exc:
            raise Unchecked("out", f"{out} exists and cannot be read: {exc}") from None
        if existing:
            try:
                why = _shape_problem(json.loads(existing.decode("utf-8")))
            except (UnicodeDecodeError, json.JSONDecodeError):
                why = "is not JSON"
            if why is not None:
                raise Unchecked("out", f"{out} exists and {why}; it is not overwritten, so choose a new path")


def snapshot(root: Path, out: Path) -> tuple[int, int, int]:
    """Write the snapshot. Returns (paths recorded, present, overlays present)."""
    out = out.resolve()
    _check_out(root, out)
    files = {rel: _digest(root, rel) for rel in sorted(protected_paths(root))}
    data = {"version": VERSION, "root": str(root), "created": time.time(), "head": _head(root), "files": files}
    tmp: str | None = None
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        # A new file of its own (O_EXCL), so no file of any name is overwritten on the way.
        fd, tmp = tempfile.mkstemp(dir=out.parent, prefix=f".{out.name}.", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data, indent=1, sort_keys=True) + "\n")
        os.replace(tmp, out)
        tmp = None
    except OSError as exc:
        raise Unchecked("out", f"cannot write {out}: {exc}") from None
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    present = sum(1 for v in files.values() if v is not None)
    overlays = sum(1 for k, v in files.items() if v is not None and kind_of(k) == "overlay")
    return len(files), present, overlays


def load_snapshot(path: Path, root: Path, now: float | None = None) -> dict:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        raise Unchecked("snapshot", f"{path} does not exist; was the snapshot step run?") from None
    except OSError as exc:
        raise Unchecked("snapshot", f"cannot read {path}: {exc}") from None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise Unchecked("snapshot", f"{path} is not valid JSON: {exc}") from None
    why = _shape_problem(data)
    if why is not None:
        raise Unchecked("snapshot", f"{path} {why}")
    snap_root = data["root"]
    if os.path.normcase(str(Path(snap_root).resolve())) != os.path.normcase(str(root)):
        raise Unchecked("snapshot", f"{path} was taken in {snap_root!r}, not in {root}")
    age = (time.time() if now is None else now) - data["created"]
    if age > MAX_AGE_HOURS * 3600:
        raise Unchecked("snapshot", f"{path} was taken {age / 3600:.1f} h ago, more than {MAX_AGE_HOURS} h; "
                                    "it is not this run's snapshot")
    if age < -FUTURE_SKEW_SECONDS:
        raise Unchecked("snapshot", f"{path} is dated {-age:.0f} s in the future; it is not this run's snapshot")
    then, now_head = data["head"], _head(root)
    if then is not None and then != now_head:
        if now_head is None:
            raise Unchecked("snapshot", f"HEAD was {then[:12]} at the snapshot and the branch now has no commit")
        r = _git(root, "merge-base", "--is-ancestor", then, now_head)
        if r.returncode == 1:
            raise Unchecked("snapshot", f"HEAD moved from {then[:12]} to {now_head[:12]}, which does not descend "
                                        "from it; files changed by the checkout are not the run's")
        if r.returncode != 0:
            raise Unchecked("snapshot", f"cannot relate the snapshot's HEAD {then[:12]} to {now_head[:12]}: "
                                        f"{_first_err(r)}")
    return data


# ---------------------------------------------------------------- verify


def _normalise_approved(root: Path, raw: list[str]) -> set[str]:
    out: set[str] = set()
    for item in raw:
        p = Path(item)
        if not p.is_absolute():
            p = root / p
        p = Path(os.path.normpath(p))
        if not _inside(p, root):
            # normpath keeps a symlinked root unresolved; try the resolved form too.
            q = p.resolve()
            if not _inside(q, root):
                raise Unchecked("approved", f"{item} is outside the repo {root}")
            p = q
        out.add(p.relative_to(root).as_posix())
    return out


APPROVABLE = ("local", "terminology", "overlay")
_WHY = {
    "instruction": "an instruction file; cla-setup never touches it, so a yes does not cover it",
    "settings": "a Claude Code settings or plugin manifest file; cla-setup never touches it, so a yes does not cover it",
    "rules": "a rules file of the repo's own; cla-setup writes only cla-economy.md there, so a yes does not cover it",
    "notes": "the feedback notes file; an existing one is always skipped, so a yes does not cover it",
    "local": "a machine-read local file; changed without the owner's yes",
    "terminology": "the terminology file; changed without the owner's yes",
    "overlay": "an overlay; changed without the owner's yes",
}


def verify(root: Path, snap: dict, approved: set[str]) -> tuple[int, list[str], list[str], list[str]]:
    """Returns (paths compared, problems, unchecked, approved changes)."""
    before: dict[str, str | None] = snap["files"]
    problems: list[str] = []
    unchecked: list[str] = []
    taken: list[str] = []
    compared = sorted(set(before) | protected_paths(root))
    for rel in compared:
        kind = kind_of(rel)
        old = before.get(rel)
        try:
            new = _digest(root, rel)
        except Unchecked as exc:
            unchecked.append(f"UNCHECKED {exc.kind}: {exc.detail}")
            continue
        if old == new:
            continue
        action = "created" if old is None else "deleted" if new is None else "changed"
        if kind == "overlay" and action == "created":
            problems.append(f"PROBLEM created: {rel} (an overlay; cla-setup never creates one, "
                            "so a yes does not cover it)")
            continue
        if kind == "terminology" and action == "created":
            problems.append(f"PROBLEM created: {rel} (the terminology file; cla-setup never creates it, "
                            "so a yes does not cover it)")
            continue
        if kind == "notes" and action == "created":
            continue  # item 3 seeds it when absent
        if kind in APPROVABLE and rel in approved:
            taken.append(f"{rel} {action}")
            continue
        problems.append(f"PROBLEM {action}: {rel} ({_WHY[kind]})")
    return len(compared), problems, unchecked, taken


# ---------------------------------------------------------------- main


def _report(first: str, lines: list[str]) -> None:
    print(first)
    for line in lines:
        print(line)


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=".", help="a directory inside the checkout (default: the working directory)")
    ap = argparse.ArgumentParser(
        description="Check that cla-setup left its protected files alone. Exit 0 pass, 1 problem, 2 could not check.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("snapshot", parents=[common], help="at the start of a run: record the protected files")
    p.add_argument("--out", required=True, help="a new snapshot file, outside the repo or in a gitignored folder")
    p = sub.add_parser("verify", parents=[common], help="at the end of a run: compare with the snapshot")
    p.add_argument("--snapshot", required=True, help="the file the snapshot step wrote")
    p.add_argument("--approved", action="append", default=[], metavar="PATH",
                   help="a protected file the owner said yes to changing in this run (repeatable)")
    args = ap.parse_args(argv)

    try:
        root = _toplevel(Path(args.root).resolve())
        if args.cmd == "snapshot":
            n, present, overlays = snapshot(root, Path(args.out))
            _report(f"OK snapshot: {n} protected path(s) recorded, {present} present, "
                    f"{overlays} overlay(s), in {Path(args.out).resolve()}", [])
            return 0
        approved = _normalise_approved(root, args.approved)
        snap = load_snapshot(Path(args.snapshot), root)
        compared, problems, unchecked, taken = verify(root, snap, approved)
    except Unchecked as exc:
        _report(f"UNCHECKED {exc.kind}: {exc.detail}", [])
        return 2
    except Exception as exc:  # noqa: BLE001 - a crash must read as "could not check", never as a verdict
        _report(f"UNCHECKED error: unexpected {type(exc).__name__}: {exc}", [])
        print(traceback.format_exc(), file=sys.stderr)
        return 2
    if problems:
        _report(f"FAIL verify: {len(problems)} protected file problem(s)", problems + unchecked)
        return 1
    if unchecked:
        _report(unchecked[0], unchecked[1:])
        return 2
    approved_note = f"; approved: {', '.join(taken)}" if taken else ""
    _report(f"OK verify: {compared} protected path(s) as promised{approved_note}", [])
    return 0


if __name__ == "__main__":
    sys.exit(main())
