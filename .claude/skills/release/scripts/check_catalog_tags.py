#!/usr/bin/env python3
"""Refuse while a marketplace catalog's `ref` names a tag the remote does not have.

WHY THIS EXISTS. Both catalogs (`.claude-plugin/marketplace.json` for Claude Code,
`.github/plugin/marketplace.json` for the Copilot CLI) are read by consumers from
the default branch, and each pins the plugin to a `cla--v<version>` tag. The
release commit that moves those refs reaches the default branch by a merge, and
the tag is a separate push. When the merge came first, every consuming repo's
`marketplace update` fetched a ref that did not exist until the tag push: 2.0.0
sat merged and untagged until the owner pushed the tag by hand, and 2.4.0 did the
same.

`/release` now closes that window by order: it tags the release PR's head commit,
where the manifest and the catalog already agree, pushes the tag, and only then
merges the PR with a merge commit, so the tagged commit itself lands on the
default branch. This check is what proves each step held:

    precondition   `/release` refuses to start while an EARLIER release's ref is
                   still dangling, so one missed tag push cannot be buried under
                   the next version;
    postcondition  `/release` merges nothing until, on the release branch, the
                   new ref resolves on the remote, and reports nothing as done
                   until it still does on the default branch. Run it there with
                   `--expect cla--v<new>`: without it, a working tree that still
                   holds the OLD ref passes on the old tag while the new one
                   never left the local clone.

WHAT IT READS. The catalogs in the working tree at `--root` (default: the repo
this script sits in, whatever the cwd). `/release` runs it on the default
branch, up to date with `origin`, where the working tree is what consumers read,
and on the release branch, where it is what they will read once it merges. The
remote is asked once, with `git ls-remote --tags`; a tag that exists only in the
local clone is MISSING, because a consumer cannot fetch it.

EXIT CONTRACT, three-valued on purpose:

    0  every catalog ref names a tag the remote has (and, with `--expect`, every
       ref is that tag)
    1  one or more refs name a tag the remote lacks, or (with `--expect`) a ref
       is not the expected tag or the expected tag is not on the remote; every
       one is named
    2  could not check: a catalog is missing, unreadable or names no ref, or the
       remote could not be asked (unreachable, refused, timed out)

Exit 2 is never a pass. A remote that does not answer has confirmed nothing, and
a check that read no ref has checked nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_MISSING = 1
EXIT_CANNOT_RUN = 2

REMOTE_TIMEOUT = 60

# Repo-relative paths of the catalogs consumers read, in report order.
CATALOGS = (
    ".claude-plugin/marketplace.json",
    ".github/plugin/marketplace.json",
)


class Unchecked(Exception):
    """The check could not run; never a pass."""


def catalog_refs(root: Path) -> list[tuple[str, str, str]]:
    """`(catalog, plugin name, ref)` for every plugin entry that pins a ref.

    Raises Unchecked when a catalog is missing or unreadable, or when a catalog
    pins no ref at all: an empty list would otherwise read as "nothing dangling".
    """
    found: list[tuple[str, str, str]] = []
    for rel in CATALOGS:
        path = root / rel
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise Unchecked(f"{rel}: not found under {root}") from None
        except (OSError, ValueError) as exc:
            raise Unchecked(f"{rel}: could not be read as JSON: {exc}") from None
        plugins = data.get("plugins") if isinstance(data, dict) else None
        refs = [
            (rel, str(p.get("name", "?")), p["source"]["ref"])
            for p in plugins or []
            if isinstance(p, dict)
            and isinstance(p.get("source"), dict)
            and isinstance(p["source"].get("ref"), str)
            and p["source"]["ref"]
        ]
        if not refs:
            raise Unchecked(f"{rel}: no plugin entry pins a `source.ref`; nothing to check")
        found.extend(refs)
    return found


def remote_tags(root: Path, remote: str) -> set[str]:
    """Tag names the remote advertises. Raises Unchecked when it cannot be asked."""
    env = dict(os.environ)
    # A remote that wants a password would wait on a prompt nobody answers.
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        r = subprocess.run(
            ["git", "ls-remote", "--tags", remote],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=REMOTE_TIMEOUT,
        )
    except FileNotFoundError:
        raise Unchecked("the git binary was not found") from None
    except subprocess.TimeoutExpired:
        raise Unchecked(
            f"`git ls-remote --tags {remote}` did not finish in {REMOTE_TIMEOUT}s"
        ) from None
    except OSError as exc:
        raise Unchecked(f"git could not be started: {exc}") from None
    if r.returncode != 0:
        err = (r.stderr.strip().splitlines() or ["no error text"])[0]
        raise Unchecked(f"`git ls-remote --tags {remote}` exited {r.returncode}: {err}")
    tags: set[str] = set()
    for line in r.stdout.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2 or not parts[1].startswith("refs/tags/"):
            continue
        name = parts[1][len("refs/tags/"):]
        # An annotated tag is listed twice: the tag object and its peeled commit.
        tags.add(name[: -len("^{}")] if name.endswith("^{}") else name)
    return tags


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[4]),
        help="repo root holding the catalogs (default: the repo this script is in)",
    )
    parser.add_argument("--remote", default="origin", help="remote to ask (default: origin)")
    parser.add_argument(
        "--expect",
        metavar="TAG",
        help="also require every catalog ref to be TAG, and TAG to be on the remote "
             "(the release's postcondition: `--expect cla--v<new>`)",
    )
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    try:
        refs = catalog_refs(root)
        tags = remote_tags(root, args.remote)
    except Unchecked as exc:
        print(f"check_catalog_tags: NOT CHECKED: {exc}")
        print("A check that could not run is not a pass; no release is done until it exits 0.",
              file=sys.stderr)
        return EXIT_CANNOT_RUN

    if args.expect is not None:
        stale = [(rel, name, ref) for rel, name, ref in refs if ref != args.expect]
        expect_missing = args.expect not in tags
        if stale or expect_missing:
            print(f"check_catalog_tags: the release `{args.expect}` is not published")
            for rel, name, ref in stale:
                print(f"{rel}: plugin `{name}` pins `{ref}`, not `{args.expect}` "
                      "(is this tree up to date with the merged release?)")
            if expect_missing:
                print(f"`{args.expect}` is missing on {args.remote}")
            print(
                "\nPull the default branch so the catalogs hold the released ref, push "
                "the tag if it is missing (never move a published tag), then re-run.",
                file=sys.stderr,
            )
            return EXIT_MISSING

    missing = [(rel, name, ref) for rel, name, ref in refs if ref not in tags]
    if missing:
        print(f"check_catalog_tags: {len(missing)} of {len(refs)} catalog ref(s) "
              f"name a tag {args.remote} does not have")
        for rel, name, ref in missing:
            print(f"{rel}: plugin `{name}` pins `{ref}`, missing on {args.remote}")
        print(
            "\nEvery consuming repo's `marketplace update` fails on such a ref. Push the "
            "tag from the merged release commit (never move a published tag), then "
            "re-run this check.",
            file=sys.stderr,
        )
        return EXIT_MISSING

    print(f"check_catalog_tags: {len(refs)} catalog ref(s), every tag present on {args.remote}")
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
