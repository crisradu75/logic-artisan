"""Recheck a change's `path:line` cites after earlier changes in a chain merged.

A `/cla:multi-pr` batch is written against one commit. By the time a later change
runs, earlier merges may have moved or removed the lines its `tasks.md` and
`design.md` cite. This reads each cite whose file changed between the chain's
start commit and the ref, looks up the cited text at the start commit, and finds
it again at the ref:

    ok          the cited lines are still at the cited place
    drifted     the same lines are now elsewhere, at exactly one place
    gone        the lines no longer exist as cited (removed, edited, or the
                whole file deleted or renamed away)
    ambiguous   the lines now occur at more than one place, or already occurred
                at more than one place at the start commit
    unchecked   the check cannot judge this cite; the row says why

Cite numbers are read as start-commit line numbers. After `--fix` they are not,
so never run `--fix` twice over the same artifacts.

A cite is a repo-relative path with a file extension, optionally led by `./`,
then `:N` or `:N-M`. Not recognised, so never counted: `#L12`, `:12,14`, an
en-dash range, a path with no extension, spaces or brackets, a backslash path.
Matching is by text, so a short generic line (`}`) can still read `ok` when an
identical line sits at the cited place.

`--fix` rewrites each drifted cite in place, after every cite is judged. It
never touches gone, ambiguous or unchecked cites.

`--list` prints every cite the artifacts hold, one per line, and judges nothing.

Output, one tab-separated row per cite that is not `ok`:
    <status>  <artifact>:<artifact line>  <cite>  [<new cite> | <reason>]
and a count summary on stderr.

Exit 0: nothing left to judge (every cite ok or unchecked, or drifted and fixed).
Exit 1: a gone or ambiguous cite, or a drifted one without --fix.
Exit 2: the check could not run (not a git repo, an unknown commit, no
artifacts, an unreadable artifact or object, a failed write).

    python3 check_cite_drift.py --since <sha> [--ref <ref>] [--fix] <change-dir>
    python3 check_cite_drift.py --list <change-dir>
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ARTIFACTS = ("tasks.md", "design.md")
EXIT_CLEAN, EXIT_DRIFT, EXIT_CANNOT_RUN = 0, 1, 2
STATUSES = ("ok", "drifted", "gone", "ambiguous", "unchecked")

# A path with a file extension (a leading `./` matches as a directory), then `:N` or `:N-M`. The lookbehind keeps it from
# starting inside a longer token; the lookahead keeps `:12` from matching `:123`.
CITE = re.compile(r"(?<![\w./-])((?:[\w.-]+/)*[\w.-]+\.[A-Za-z0-9]+):(\d+)(?:-(\d+))?(?![\d-])")


class CannotRun(Exception):
    pass


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-c", "core.quotePath=false", *args],
            cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CannotRun(f"git could not be run ({type(exc).__name__})") from exc


def _file_at(repo: Path, ref: str, path: str) -> list[str] | None:
    """The file's lines at `ref`, or None when it does not exist there."""
    if _git(repo, "cat-file", "-e", f"{ref}:{path}").returncode != 0:
        return None
    shown = _git(repo, "show", f"{ref}:{path}")
    if shown.returncode != 0:
        raise CannotRun(f"git show {ref}:{path} failed: {shown.stderr.strip()}")
    return [line.rstrip() for line in shown.stdout.splitlines()]


def _find(block: list[str], lines: list[str]) -> list[int]:
    """Every 1-based line where `block` starts in `lines`."""
    size = len(block)
    return [i + 1 for i in range(len(lines) - size + 1) if lines[i:i + size] == block]


def judge(old: list[str] | None, new: list[str] | None, start: int, end: int) -> tuple[str, int | None, str]:
    """(status, new start line, reason) for one cite of lines start..end."""
    if old is None:
        return "unchecked", None, "file absent at the start commit"
    if start < 1 or end < start or end > len(old):
        return "unchecked", None, "range runs past the start-commit file"
    block = old[start - 1:end]
    if not any(line.strip() for line in block):
        return "unchecked", None, "cited lines are blank"
    if new is None:
        return "gone", None, ""
    places = _find(block, new)
    if start in places:
        return "ok", start, ""
    if len(_find(block, old)) > 1:
        return "ambiguous", None, ""
    if len(places) == 1:
        return "drifted", places[0], ""
    return ("ambiguous" if places else "gone"), None, ""


def _read(artifact: Path) -> str:
    try:
        # Bytes, not read_text: newline translation would rewrite every CRLF on --fix.
        return artifact.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CannotRun(f"cannot read {artifact}: {exc}") from exc


def _artifacts(change_dir: Path) -> list[Path]:
    found = [change_dir / name for name in ARTIFACTS if (change_dir / name).is_file()]
    if not found:
        raise CannotRun(f"no {' or '.join(ARTIFACTS)} in {change_dir}")
    return found


def list_cites(change_dir: Path) -> list[str]:
    return [m.group(0) for a in _artifacts(change_dir) for m in CITE.finditer(_read(a))]


def check(repo: Path, change_dir: Path, since: str, ref: str, fix: bool) -> tuple[list[str], Counter, int]:
    for commit in (since, ref):
        if _git(repo, "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}").returncode != 0:
            raise CannotRun(f"unknown commit: {commit}")
    # --no-renames: a renamed file's old path must show as deleted, or its cites go unread.
    diff = _git(repo, "diff", "--no-renames", "--name-only", since, ref)
    if diff.returncode != 0:
        raise CannotRun(f"git diff {since} {ref} failed")
    changed = set(diff.stdout.splitlines())
    texts = {artifact: _read(artifact) for artifact in _artifacts(change_dir)}

    report: list[str] = []
    counts: Counter = Counter()
    needs_judging = False
    cache: dict[tuple[str, str], list[str] | None] = {}
    fixed: dict[Path, str] = {}
    for artifact, text in texts.items():
        out_lines = []
        for number, line in enumerate(text.splitlines(keepends=True), start=1):
            def replace(match: re.Match[str]) -> str:
                nonlocal needs_judging
                cite, start = match.group(0), int(match.group(2))
                path = match.group(1).removeprefix("./")
                end = int(match.group(3)) if match.group(3) else start
                if path not in changed:
                    counts["ok"] += 1
                    return cite
                for key in ((since, path), (ref, path)):
                    if key not in cache:
                        cache[key] = _file_at(repo, *key)
                status, moved, reason = judge(cache[(since, path)], cache[(ref, path)], start, end)
                counts[status] += 1
                if status == "ok":
                    return cite
                new_cite = ""
                if status == "drifted" and moved is not None:
                    new_cite = f"{match.group(1)}:{moved}" + (f"-{moved + end - start}" if match.group(3) else "")
                report.append("\t".join(filter(None, (status, f"{artifact.name}:{number}", cite, new_cite or reason))))
                if status == "unchecked":
                    return cite
                if status == "drifted" and fix:
                    return new_cite
                needs_judging = True
                return cite

            out_lines.append(CITE.sub(replace, line))
        if fix and "".join(out_lines) != text:
            fixed[artifact] = "".join(out_lines)
    # Every cite is judged before any file is written, so a failure leaves no half-fixed change.
    for artifact, content in fixed.items():
        try:
            artifact.write_bytes(content.encode("utf-8"))
        except OSError as exc:
            raise CannotRun(f"cannot write {artifact}: {exc}") from exc
    return report, counts, EXIT_DRIFT if needs_judging else EXIT_CLEAN


def summary(counts: Counter) -> str:
    total = sum(counts.values())
    return f"check_cite_drift: {total} cite(s): " + ", ".join(f"{s} {counts[s]}" for s in STATUSES)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("change_dir", type=Path, help="openspec/changes/<name>")
    parser.add_argument("--since", help="the commit the chain started from")
    parser.add_argument("--ref", default="HEAD", help="the merged tree to check against (default HEAD)")
    parser.add_argument("--fix", action="store_true", help="rewrite drifted cites in place")
    parser.add_argument("--list", action="store_true", help="print every cite and judge nothing")
    args = parser.parse_args(argv)
    if args.list == bool(args.since):
        parser.error("give exactly one of --since or --list")

    try:
        if args.list:
            for cite in list_cites(args.change_dir):
                print(cite)
            return EXIT_CLEAN
        top = _git(Path.cwd(), "rev-parse", "--show-toplevel")
        if top.returncode != 0:
            raise CannotRun("not inside a git repository")
        report, counts, code = check(Path(top.stdout.strip()), args.change_dir, args.since, args.ref, args.fix)
    except CannotRun as exc:
        print(f"check_cite_drift: {exc}", file=sys.stderr)
        return EXIT_CANNOT_RUN
    for row in report:
        print(row)
    print(summary(counts), file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
