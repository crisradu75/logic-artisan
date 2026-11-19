#!/usr/bin/env python3
"""Write a repo's economy rules file, ``.claude/rules/cla-economy.md``, for /cla:cla-setup item 7a.

    python3 "${CLAUDE_PLUGIN_ROOT}/skills/cla-setup/scripts/render_economy_rules.py" --root "$ROOT"

THE TEXT. ``skills/_shared/references/economy-rules-file.md`` (the frame) with two sources inlined,
each at the line that holds its include marker alone: ``orchestration-economy.md`` whole at
``<!-- include: cost-rules -->``, and the lines of ``model-routing.md`` strictly between its
``<!-- economy-rules-file:review-sizing:begin -->`` and ``...:end -->`` lines at
``<!-- include: review-sizing -->``. The sources are read from this script's own plugin tree, so
the plugin root is never typed. Every carriage return is dropped from each source, trailing
newlines are dropped from each source and from the result, and the file ends with one newline:
a CRLF checkout and an LF one write the same bytes, the bytes the bash block this replaced wrote.

CHECKS BEFORE WRITING, each a ``NOT written`` refusal:
  * every source is present and not empty (after dropping carriage returns and trailing newlines);
  * the begin and end lines each occur exactly once in ``model-routing.md``, begin first, with at
    least one non-blank line between them;
  * each include marker is alone on exactly one line of the frame, and the frame holds no other
    ``<!--`` line;
  * ``--root`` is a directory, and the file, when present, is a regular file (a folder there is
    not the file the plugin owns, so it is left alone rather than replaced).

SYMBOLIC LINKS. A symbolic link at ``.claude/``, at ``.claude/rules/`` or at the file is refused
("is a symbolic link") and nothing is written through it or over it, before any folder is made:
writing through one could land outside the repo, and replacing one turns a link the user set up
into a plain file. ``save-permissions``'s ``merge_permissions.py`` follows the same rule for
``.claude/`` and its settings file.

THE WRITE. An existing file whose bytes, with carriage returns dropped, equal the text is left
alone (``unchanged``). Otherwise the text goes to a new, uniquely named temporary file in
``.claude/rules/``, which then replaces the file in one step (``os.replace``); on any failure the
temporary file is removed and an existing file is left whole. A replaced file keeps its
permission bits. A hand edit is replaced: the plugin owns this file whole.

NAMED LIMITS, each the same as the bash block this replaced:
  * A read-only file is replaced on POSIX, where renaming over it needs only a writable folder;
    on Windows the replace fails and the script exits 1 with the file unchanged.
  * A hard-linked file is split: the repo gets the new file, and every other name for the old one
    keeps the old content.
  * Nothing is fsynced: after a power loss the file is whole, but may be the old version.

OUTPUT, one line on stdout (two for ``replaced``), the same words the skill reports:
  ``.claude/rules/cla-economy.md: created`` | ``replaced`` (+ a line saying local edits were
  overwritten) | ``unchanged`` | ``NOT written, <reason>``

EXIT CODES:
  0 = created, replaced or unchanged
  1 = NOT written: a check failed or the write failed; an existing file is as it was
  2 = usage (a bad or missing argument); nothing written
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

REF = Path(__file__).resolve().parents[2] / "_shared" / "references"
RULES = Path(".claude") / "rules" / "cla-economy.md"
LABEL = ".claude/rules/cla-economy.md"
BEGIN = b"<!-- economy-rules-file:review-sizing:begin -->"
END = b"<!-- economy-rules-file:review-sizing:end -->"
INC_COST = b"<!-- include: cost-rules -->"
INC_SIZING = b"<!-- include: review-sizing -->"


class NotWritten(Exception):
    pass


def _read(path: Path) -> bytes:
    """A source with every CR dropped and trailing newlines stripped (bash's ``$(tr -d '\\r' < f)``)."""
    try:
        data = path.read_bytes()
    except OSError:
        return b""
    return data.replace(b"\r", b"").rstrip(b"\n")


def _lines(text: bytes) -> list[bytes]:
    return text.split(b"\n")


def render(ref: Path = REF) -> bytes:
    frame = _read(ref / "economy-rules-file.md")
    cost = _read(ref / "orchestration-economy.md")
    model = _read(ref / "model-routing.md")
    if not frame or not cost or not model:
        raise NotWritten(f"a source is missing or empty under {ref.as_posix()}")
    mlines = _lines(model)
    if mlines.count(BEGIN) != 1 or mlines.count(END) != 1:
        raise NotWritten("model-routing.md must hold the review-sizing begin and end comments exactly once each")
    lb, le = mlines.index(BEGIN), mlines.index(END)
    if lb >= le:
        raise NotWritten("model-routing.md has the review-sizing end comment before the begin comment")
    sizing = b"\n".join(mlines[lb + 1:le]).rstrip(b"\n")
    if not sizing:
        raise NotWritten("the review-sizing span in model-routing.md is empty")
    flines = _lines(frame)
    if (flines.count(INC_COST) != 1 or flines.count(INC_SIZING) != 1
            or sum(b"<!--" in line for line in flines) != 2):
        raise NotWritten("economy-rules-file.md must hold each include marker alone on a line exactly once, and no other comment")
    out = []
    for line in flines:
        out.append(cost if line == INC_COST else sizing if line == INC_SIZING else line)
    # Every part was stripped of trailing newlines, so the text ends on a non-empty line.
    return b"\n".join(out) + b"\n"


def _mode_for(path: Path) -> int:
    try:
        return path.stat().st_mode & 0o7777
    except FileNotFoundError:
        umask = os.umask(0)
        os.umask(umask)
        return 0o666 & ~umask
    except OSError as exc:
        raise NotWritten(f"cannot read the permission bits of {LABEL} ({exc})") from None


def _replace(target: Path, text: bytes) -> None:
    mode = _mode_for(target)
    try:
        fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix="." + target.name + ".", suffix=".tmp")
    except OSError as exc:
        raise NotWritten(f"cannot write a temporary file in {target.parent.as_posix()} ({exc})") from None
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, str(target))
    except BaseException as exc:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        if isinstance(exc, OSError):
            raise NotWritten(f"cannot move the new text into place ({exc})") from None
        raise


def write(root: Path, ref: Path = REF) -> list[str]:
    """Render and write; return the lines to print. Raises NotWritten."""
    if not root.is_dir():
        raise NotWritten(f"{root.as_posix()} is not a directory")
    text = render(ref)
    target = root / RULES
    rules_dir = target.parent
    # Checked before mkdir, so no folder is made through a link.
    for link, name in ((rules_dir.parent, ".claude"), (rules_dir, ".claude/rules")):
        if link.is_symlink():
            raise NotWritten(f"{name} is a symbolic link; left as it is")
    try:
        rules_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise NotWritten(f"cannot create {rules_dir.as_posix()}") from None
    if not rules_dir.is_dir():
        raise NotWritten(f"cannot create {rules_dir.as_posix()}")
    if target.is_symlink():
        raise NotWritten(f"{LABEL} is a symbolic link; left as it is")
    if target.exists() and not target.is_file():
        raise NotWritten(f"{LABEL} is not a regular file; left as it is")
    if not target.exists():
        _replace(target, text)
        return [f"{LABEL}: created"]
    try:
        current = target.read_bytes()
    except OSError as exc:
        raise NotWritten(f"cannot read the existing file ({exc})") from None
    if current.replace(b"\r", b"") == text:
        return [f"{LABEL}: unchanged"]
    _replace(target, text)
    return [f"{LABEL}: replaced",
            f"any local edits to {LABEL} were overwritten; the repo's own rules go in its own instruction files"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write .claude/rules/cla-economy.md in a repo.")
    parser.add_argument("--root", required=True, help="the repo root (cla-setup's $ROOT)")
    args = parser.parse_args(argv)
    try:
        lines = write(Path(args.root))
    except NotWritten as exc:
        print(f"{LABEL}: NOT written, {exc}")
        return 1
    except OSError as exc:  # a check that touched the disk and failed
        print(f"{LABEL}: NOT written, {exc}")
        return 1
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
