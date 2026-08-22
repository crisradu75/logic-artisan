#!/usr/bin/env python3
"""Measure the link detector against a corpus of real OpenSpec changes.

Stdlib only, and it runs on Windows and POSIX alike.

    python3 <plugin>/skills/annotate/scripts/sweep_changes.py <root> [<root> ...]

**This is the command behind the numbers in `openspec_change.py`.** Every
threshold in that module — `UBIQUITOUS`, `IDENT_MIN`, `COMMON_SHARE`,
`LEXICAL_MIN`, `LEXICAL_CAP` — is a judgement call, and the only honest way to
set one is to run it over changes nobody wrote for it. Fitted to a single change
the detector looked excellent; swept over 355 it left 83% of promises falsely
uncovered. A threshold whose comment cites a measurement, and whose measurement
has no command, is a claim.

It also exists for the consuming repo. A repo whose proposals are prose rather
than path-heavy will land far more bullets in *not checkable*, and this is how
you find that out before trusting the coverage tab rather than after.

Prints one row per change and a summary. Nothing is written.
"""
import argparse
import glob
import io
import os
import sys

import openspec_change as OC


def measure(change_dir):
    """-> a row of counts for one change, or None if it cannot be read."""
    texts = {}
    for key, _label, path in OC.change_files(change_dir):
        try:
            texts[key] = io.open(path, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError) as e:
            # Reported, never absorbed: a change skipped in silence quietly
            # improves every percentage below it.
            print("  ! %s: %s: %s" % (os.path.basename(change_dir),
                                      type(e).__name__, e))
    if "proposal" not in texts:
        return None
    model = OC.build(change_dir, texts)
    cov = model["coverage"]
    st = cov["stats"]
    return {
        "name": os.path.basename(change_dir),
        "files": st["files"], "promises": st["promises"],
        "covered": len(cov["covered"]), "uncovered": len(cov["uncovered"]),
        "unchecked": len(cov["unchecked"]), "undone": len(cov["undone"]),
        "links": st["links"], "tasks": st["tasks"],
        "ubiquitous": len(st["ubiquitous"]),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("roots", nargs="*", default=["."],
                    help="repo roots to sweep (default: the current directory)")
    ap.add_argument("--quiet", action="store_true", help="summary only")
    a = ap.parse_args(argv)

    dirs = []
    for root in a.roots:
        dirs += [os.path.dirname(p) for p in glob.glob(
            os.path.join(root, "openspec", "changes", "**", "proposal.md"), recursive=True)]
    dirs = sorted(set(dirs))
    if not dirs:
        print("no OpenSpec changes found under: %s" % ", ".join(a.roots))
        return 1

    rows, failed = [], 0
    for d in dirs:
        try:
            row = measure(d)
        except Exception as e:                                   # noqa: BLE001
            # One malformed change must not end the sweep, but it must be
            # counted — a sweep that silently drops what it cannot parse reports
            # the health of the changes it happened to like.
            print("  ! %s: %s: %s" % (os.path.basename(d), type(e).__name__, e))
            failed += 1
            continue
        if row:
            rows.append(row)

    if not a.quiet:
        print("%-46s %5s %5s %5s %5s %5s %5s" %
              ("change", "files", "prom", "cov", "unc", "n/chk", "links"))
        for r in rows:
            print("%-46s %5d %5d %5d %5d %5d %5d"
                  % (r["name"][:46], r["files"], r["promises"], r["covered"],
                     r["uncovered"], r["unchecked"], r["links"]))

    p = sum(r["promises"] for r in rows)
    c = sum(r["covered"] for r in rows)
    u = sum(r["uncovered"] for r in rows)
    n = sum(r["unchecked"] for r in rows)
    pct = (lambda x: 100.0 * x / p if p else 0.0)
    print("\n%d changes read, %d unreadable · %d promises" % (len(rows), failed, p))
    print("  covered        %5d (%.0f%%)" % (c, pct(c)))
    print("  uncovered      %5d (%.0f%%)" % (u, pct(u)))
    print("  not checkable  %5d (%.0f%%)" % (n, pct(n)))
    nothing = sum(1 for r in rows if r["promises"] and not r["covered"])
    print("  changes with nothing covered: %d" % nothing)
    print("  changes with no promise parsed: %d"
          % sum(1 for r in rows if not r["promises"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
