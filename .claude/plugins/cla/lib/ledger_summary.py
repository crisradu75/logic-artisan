#!/usr/bin/env python3
"""Summarise ANY cla run-ledger, deriving the shape from the records themselves.

WHY THIS IS GENERIC WHERE THE OTHER TWO READERS ARE NOT.

`codify_aggregate.py` and `spec_to_pr_aggregate.py` are specific on purpose: they
know what `re_offenses` means and gate real heuristics on it. That specificity is
also why they cost what they cost, and it is why five ledgers went unread — nobody
was going to write five more of them. Measured across the fleet: `multi-lite`,
`multi-pr`, `multi-spec`, `project-review` and `right-model` hold 22 rows between
them with no reader at all, and this repo's own rule says an unread ledger is
exhaust.

So this reads any of them without knowing anything about them. Per top-level field
it reports what that field's TYPE makes reportable — a bool becomes a true/false
split, a number becomes min/mean/max, a string becomes a frequency table, a list
becomes length stats — and one level of nesting is flattened with dotted keys.
Nothing is configured, because a config file is one more thing to keep in step
with a schema, and the schema is already in the records.

WHAT IT DELIBERATELY DOES NOT DO. It proposes nothing. The two specific readers
exist to turn metrics into named edits, and a generic tool cannot do that without
knowing what a field means. This answers "what is in this ledger, and is anything
lopsided", which is exactly the question that has gone unanswered for the ledgers
nothing reads. Treat a lopsided field as a prompt to look, not as a verdict.

A NOTE ON SMALL SAMPLES, because this tool will mostly meet them. Several of these
ledgers hold single-digit row counts, where one run moves every percentage. The
output always carries `records`, and every derived figure should be read against
it; `records` under about 5 makes a distribution an anecdote. The same trap the
fleet flags exist for.

    python3 lib/ledger_summary.py --log <path> [<path> ...]
    python3 lib/ledger_summary.py --fleet --ledger lite-pr-runs.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

# How many distinct values of a string field to name before collapsing the rest.
# A field with more than this is usually free text rather than a category, and
# printing all of it buries the fields that ARE categorical.
_TOP_N = 10

_FLEET_FILE = "fleet.local.md"


def _git_toplevel() -> Path | None:
    """Repo root via git (location-independent — works from the plugin, unlike a
    `.claude`-ancestor walk). None if git is unavailable."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return None
    return None


def _runs_dir() -> Path:
    """The in-repo, git-synced ledger dir: <repo-root>/cla.io/retro/.

    Raises on a non-absolute override or an unresolvable repo root rather than
    guessing a path: the consumers (the two retro aggregators) resolve
    independently with identical logic, so a silently-wrong path here would make
    logged runs vanish from the retro with no error.
    """
    override = os.environ.get("CLAUDE_RETRO_DIR")
    if override and override.strip():  # set-but-blank/whitespace → treat as unset
        path = Path(override)
        if not path.is_absolute():
            raise ValueError(f"CLAUDE_RETRO_DIR must be an absolute path, got {override!r}")
        return path
    root = _git_toplevel()
    if root is None:
        raise RuntimeError(
            "could not resolve the repo root via `git rev-parse --show-toplevel`; "
            "set CLAUDE_RETRO_DIR to an absolute path"
        )
    return root / "cla.io" / "retro"


def _fleet_roots(path: Path) -> list[Path]:
    """Repo roots listed in the fleet file, one per `- ` bullet.

    Reading a fleet aggregate meant typing every repo's ledger path by hand, every
    time. Nothing saved the list, so the cross-repo view existed only when someone
    remembered all of them and spelled each one correctly — and a path that
    resolves to nothing contributes silently, which is exactly the sample-size
    error the fleet mode exists to fix.

    Format and location follow `cla.io/project-tokens.local.md`, the closest
    precedent: a `*.local.md` file in the repo's own tree, one item per `- `
    bullet, inline `#` comments and surrounding backticks stripped. It holds repo
    ROOTS rather than ledger paths, so one file serves both aggregators and both
    of this one's ledger kinds — each caller appends the ledger name it already
    knows.

    Raises rather than returning empty on a missing or contentless file: a fleet
    run that silently analysed nothing would print `runs_analyzed: 0`, which both
    retro skills instruct the reader to interpret as a cold start.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"no fleet file at {path}. Create it with one repo root per `- ` "
            f"bullet, e.g. `- /path/to/another-repo`, or pass explicit paths "
            f"instead of --fleet"
        )
    roots: list[Path] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line.startswith("- "):
            continue
        item = line[2:].split("#", 1)[0].strip().strip("`").strip()
        if item:
            roots.append(Path(item))
    if not roots:
        raise ValueError(
            f"{path} lists no repo roots — expected one per `- ` bullet. "
            f"Refusing rather than analysing nothing and reporting it as a cold "
            f"start"
        )
    return roots


def _flatten(rec: dict) -> dict:
    """One level of nesting, dotted. Deeper structure is summarised as a shape.

    One level rather than full recursion because the ledgers that motivated this
    nest exactly that far — `suggestions.applied`, `maintenance.trimmed` — while a
    fully recursive flatten on `spec-to-pr-runs.jsonl` produces hundreds of
    single-observation keys and buries the ones anybody reads.
    """
    flat: dict = {}
    for key, value in rec.items():
        if isinstance(value, dict):
            for sub, subvalue in value.items():
                if isinstance(subvalue, (dict, list)):
                    flat[f"{key}.{sub}"] = f"<{type(subvalue).__name__}>"
                else:
                    flat[f"{key}.{sub}"] = subvalue
        else:
            flat[key] = value
    return flat


def summarise_field(values: list) -> dict:
    """What this field's type makes reportable, and nothing beyond it.

    `present` is always emitted and always read first: every other figure here is
    over the records that CARRIED the field, not over the window. A ledger whose
    schema grew mid-history has fields present in a third of its rows, and a mean
    over those is a true statement about a subset that reads like one about the
    whole.
    """
    out: dict = {"present": len(values)}
    non_null = [v for v in values if v is not None]
    out["null"] = len(values) - len(non_null)
    if not non_null:
        return out

    # bool BEFORE int — in Python a bool IS an int, and treating it as one turns a
    # true/false split into a meaningless mean of 0.6.
    if all(isinstance(v, bool) for v in non_null):
        c = Counter(non_null)
        out["true"], out["false"] = c[True], c[False]
    elif all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in non_null):
        out["min"] = min(non_null)
        out["max"] = max(non_null)
        out["mean"] = round(statistics.mean(non_null), 2)
    elif all(isinstance(v, str) for v in non_null):
        c = Counter(non_null)
        out["distinct"] = len(c)
        out["top"] = dict(c.most_common(_TOP_N))
        if len(c) > _TOP_N:
            out["other"] = len(non_null) - sum(out["top"].values())
    elif all(isinstance(v, list) for v in non_null):
        lens = [len(v) for v in non_null]
        out["min_len"] = min(lens)
        out["max_len"] = max(lens)
        out["mean_len"] = round(statistics.mean(lens), 2)
        out["empty"] = sum(1 for n in lens if n == 0)
    else:
        # A field whose type CHANGES across records. Named as such rather than
        # coerced: mixed types are the producer-drift signal the specific readers
        # spend real code detecting, and silently picking one branch would hide it.
        out["mixed_types"] = sorted({type(v).__name__ for v in non_null})
    return out


def summarise(records: list[dict]) -> dict:
    if not records:
        # `window` is emitted here too, for the reason `codify_aggregate.aggregate`
        # records about its own skeleton: a key present on every populated result
        # and absent on the empty one makes a consumer's `.get(...)` read a clean
        # value where it should read "nothing was measured".
        return {"records": 0, "window": {"first_ts": None, "last_ts": None},
                "fields": {}}
    columns: dict[str, list] = defaultdict(list)
    for rec in records:
        for key, value in _flatten(rec).items():
            columns[key].append(value)
    timestamps = sorted(
        str(r["ts"]) for r in records if isinstance(r.get("ts"), str))
    return {
        "records": len(records),
        "window": {"first_ts": timestamps[0] if timestamps else None,
                   "last_ts": timestamps[-1] if timestamps else None},
        # Sorted by how many records carry the field, descending: a field present
        # in every row is usually the one worth reading, and a long tail of
        # once-seen keys is usually drift.
        "fields": dict(sorted(
            ((k, summarise_field(v)) for k, v in columns.items()),
            key=lambda kv: (-kv[1]["present"], kv[0]))),
    }


def _load(paths: list[Path]) -> tuple[list[dict], int, list[dict]]:
    records: list[dict] = []
    skipped = 0
    ledgers: list[dict] = []
    seen: set[Path] = set()
    for p in paths:
        try:
            key = p.resolve()
        except OSError:
            key = p
        if key in seen:
            print(f"summary: {p} given more than once — ignoring the duplicate",
                  file=sys.stderr)
            continue
        seen.add(key)
        if not p.exists():
            print(f"summary: no ledger at {p} — contributing 0 records",
                  file=sys.stderr)
            ledgers.append({"path": str(p), "found": False, "records": 0, "skipped": 0})
            continue
        n = before = len(records)
        sk = 0
        for lineno, line in enumerate(p.open(encoding="utf-8"), 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"summary: {p} line {lineno}: {e}", file=sys.stderr)
                sk += 1
                continue
            if not isinstance(rec, dict):
                print(f"summary: {p} line {lineno}: not an object", file=sys.stderr)
                sk += 1
                continue
            records.append(rec)
        n = len(records) - before
        skipped += sk
        ledgers.append({"path": str(p), "found": True, "records": n, "skipped": sk})
    return records, skipped, ledgers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Summarise any cla run-ledger, deriving the shape from the records.")
    parser.add_argument("--log", type=Path, nargs="+", default=None, metavar="PATH",
                        help="One or more ledger paths.")
    parser.add_argument("--fleet", nargs="?", const="", default=None, metavar="PATH",
                        help="Read every repo root listed in the fleet file (default: "
                             "this repo's cla.io/fleet.local.md). Requires --ledger.")
    parser.add_argument("--ledger", default=None, metavar="NAME",
                        help="Ledger filename to look for under each root's "
                             "cla.io/retro/ (used with --fleet, or alone for this repo).")
    args = parser.parse_args(argv)

    if args.fleet is not None and args.log:
        print("summary: --fleet and --log are mutually exclusive; --fleet resolves "
              "the paths for you", file=sys.stderr)
        return 1
    if args.fleet is not None and not args.ledger:
        print("summary: --fleet needs --ledger <name>, e.g. --ledger lite-pr-runs.jsonl "
              "— a repo root names a directory, not which ledger in it to read",
              file=sys.stderr)
        return 1
    if not args.log and not args.ledger:
        print("summary: give --log <path> ..., or --ledger <name> for this repo's",
              file=sys.stderr)
        return 1

    try:
        if args.fleet is not None:
            fleet_path = Path(args.fleet) if args.fleet else _runs_dir().parent / _FLEET_FILE
            paths = [r / "cla.io" / "retro" / args.ledger for r in _fleet_roots(fleet_path)]
        elif args.log:
            paths = list(args.log)
        else:
            paths = [_runs_dir() / args.ledger]
    except (ValueError, RuntimeError, FileNotFoundError, OSError) as e:
        print(f"summary: {e}", file=sys.stderr)
        return 1

    records, skipped, ledgers = _load(paths)
    result = summarise(records)
    result["skipped_records"] = skipped
    result["ledgers"] = ledgers
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
