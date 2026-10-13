"""Recheck a change's `path:line` cites after earlier changes in a chain merged.

A `/cla:multi-pr` batch is written against one commit. By the time a later change
runs, earlier merges may have moved or removed the lines its `tasks.md` and
`design.md` cite. This reads each cite whose file changed between the chain's
start commit and the ref, looks up the cited text at the start commit, and finds
it again at the ref:

    ok          the cited lines are still at the cited place
    drifted     the same lines are now elsewhere, at exactly one place
    gone        the lines, or the whole file, no longer exist at the ref
    ambiguous   the lines now occur at more than one place

A cite counts only when its path is repo-relative and the file existed at the
start commit; a cite of a file the change itself creates is not checked. A cite
whose lines are all blank, or that runs past the end of the start-commit file, is
not checked either. A bare filename (`client.ts:40`) is not matched to a path.

`--fix` rewrites each drifted cite in place to its new line numbers. It never
touches gone or ambiguous cites: those need a person or a review to judge.

Output, one tab-separated line per checked cite that is not `ok`:
    <status>  <artifact>:<artifact line>  <cite>  [<new cite>]

Exit 0: nothing left to judge (every cite ok, or drifted and fixed with --fix).
Exit 1: a gone or ambiguous cite, or a drifted one without --fix.
Exit 2: the check could not run (not a git repo, an unknown commit, no artifacts).

    python3 check_cite_drift.py --since <sha> [--ref <ref>] [--fix] <change-dir>
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ARTIFACTS = ("tasks.md", "design.md")
EXIT_CLEAN, EXIT_DRIFT, EXIT_CANNOT_RUN = 0, 1, 2

# A repo-relative path with at least one directory and a file extension, then
# `:N` or `:N-M`. The lookbehind keeps it from starting inside a longer token.
CITE = re.compile(r"(?<![\w./-])((?:[\w.-]+/)+[\w.-]+\.[A-Za-z0-9]+):(\d+)(?:-(\d+))?(?!\d)")


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
    shown = _git(repo, "show", f"{ref}:{path}")
    if shown.returncode != 0:
        return None
    return [line.rstrip() for line in shown.stdout.splitlines()]


def _find(block: list[str], lines: list[str]) -> list[int]:
    """Every 1-based line where `block` starts in `lines`."""
    size = len(block)
    return [i + 1 for i in range(len(lines) - size + 1) if lines[i:i + size] == block]


def judge(old: list[str] | None, new: list[str] | None, start: int, end: int) -> tuple[str, int | None]:
    """(status, new start line) for one cite of lines start..end."""
    if old is None or end > len(old) or start < 1 or end < start:
        return "unchecked", None
    block = old[start - 1:end]
    if not any(line.strip() for line in block):
        return "unchecked", None
    if new is None:
        return "gone", None
    places = _find(block, new)
    if start in places:
        return "ok", start
    if len(places) == 1:
        return "drifted", places[0]
    return ("ambiguous" if places else "gone"), None


def check(repo: Path, change_dir: Path, since: str, ref: str, fix: bool) -> tuple[list[str], int]:
    for commit in (since, ref):
        if _git(repo, "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}").returncode != 0:
            raise CannotRun(f"unknown commit: {commit}")
    diff = _git(repo, "diff", "--name-only", since, ref)
    if diff.returncode != 0:
        raise CannotRun(f"git diff {since} {ref} failed")
    changed = set(diff.stdout.splitlines())
    artifacts = [change_dir / name for name in ARTIFACTS if (change_dir / name).is_file()]
    if not artifacts:
        raise CannotRun(f"no {' or '.join(ARTIFACTS)} in {change_dir}")

    report: list[str] = []
    needs_judging = False
    cache: dict[tuple[str, str], list[str] | None] = {}
    for artifact in artifacts:
        text = artifact.read_text(encoding="utf-8")
        out_lines = []
        for number, line in enumerate(text.splitlines(keepends=True), start=1):
            def replace(match: re.Match[str]) -> str:
                nonlocal needs_judging
                path, start = match.group(1), int(match.group(2))
                end = int(match.group(3)) if match.group(3) else start
                if path not in changed:
                    return match.group(0)
                for key in ((since, path), (ref, path)):
                    if key not in cache:
                        cache[key] = _file_at(repo, *key)
                status, moved = judge(cache[(since, path)], cache[(ref, path)], start, end)
                if status in ("ok", "unchecked"):
                    return match.group(0)
                new_cite = ""
                if status == "drifted" and moved is not None:
                    new_cite = f"{path}:{moved}" + (f"-{moved + end - start}" if match.group(3) else "")
                report.append("\t".join(filter(None, (status, f"{artifact.name}:{number}", match.group(0), new_cite))))
                if status == "drifted" and fix:
                    return new_cite
                needs_judging = True
                return match.group(0)

            out_lines.append(CITE.sub(replace, line))
        if fix:
            fixed = "".join(out_lines)
            if fixed != text:
                artifact.write_text(fixed, encoding="utf-8")
    return report, EXIT_DRIFT if needs_judging else EXIT_CLEAN


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("change_dir", type=Path, help="openspec/changes/<name>")
    parser.add_argument("--since", required=True, help="the commit the chain started from")
    parser.add_argument("--ref", default="HEAD", help="the merged tree to check against (default HEAD)")
    parser.add_argument("--fix", action="store_true", help="rewrite drifted cites in place")
    args = parser.parse_args(argv)

    top = _git(Path.cwd(), "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        print("check_cite_drift: not inside a git repository", file=sys.stderr)
        return EXIT_CANNOT_RUN
    try:
        report, code = check(Path(top.stdout.strip()), args.change_dir, args.since, args.ref, args.fix)
    except CannotRun as exc:
        print(f"check_cite_drift: {exc}", file=sys.stderr)
        return EXIT_CANNOT_RUN
    for row in report:
        print(row)
    print(f"check_cite_drift: {len(report)} cite(s) not ok", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
