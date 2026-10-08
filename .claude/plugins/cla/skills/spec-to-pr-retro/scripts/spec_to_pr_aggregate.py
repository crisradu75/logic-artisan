"""Aggregate /spec-to-pr run records into the few metrics the retro acts on.

WHICH LEDGERS. By default, every repo root listed in `cla.io/fleet.local.md`
(one per `- ` bullet), each root's `cla.io/retro/spec-to-pr-runs.jsonl`: any one
repo's ledger is thin enough to mislead. The fleet file holds absolute paths
curated per machine, so on a machine where it is missing, lists nothing, or
lists no root that exists here, the run falls back to this repo's own ledger
and says so in `source` and on stderr. `--log PATH [PATH ...]` names ledgers
explicitly instead. The ledger directory honours CLAUDE_RETRO_DIR, and the fleet
file sits beside it, in the directory above.

Output, one JSON object on stdout:

    {
      "source": "fleet" | "log" | "local",
      "fallback": str,                    # only when source is "local": why the
                                          # fleet was not read
      "ledgers": [{"path": str, "found": bool, "records": int, "skipped": int}],
      "runs_analyzed": int,               # the last --limit records PER LEDGER
      "window": {"first_ts": str|None, "last_ts": str|None},
      "skipped_records": int,             # lines not read: not JSON, not an object,
                                          # or a field this reads has the wrong shape
      "warn_reasons": [{"reason": str, "count": int}],   # warn/fail, top 10
      "warn_reasons_unrecorded": int,     # the migration's placeholder reason,
                                          # counted apart and never ranked
      "cap_exhaustion": {"review"|"test"|"revise": {"hit": int, "total": int}},
                                          # total: that phase ran with a cap above 1;
                                          # hit: it used the whole cap
      "revise_findings": {<agent>: {"found": int, "phantom": int, "runs": int}},
                                          # from routing.revise_findings_by_tier;
                                          # found is Critical+Important
      "asks": [{"header": str, "choices": {<choice>: int}}],
      "findings_by_round_reversal": {...} # see `reversal_check`
    }

Every metric but the reversal check covers the --limit window. The reversal
check reads every record of every ledger, because its condition is a cumulative
count, not a recent rate.

`--nudge` prints one line or nothing: this repo's ledger only, last 5 records.
spec-to-pr's Handoff runs it after appending its record.

Records are checked when written (`lib/log_run.py`), so this reader keeps no
drift buckets. A line it cannot read is skipped, named on stderr, and counted.
Standalone and stdlib-only: it imports nothing from the plugin.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path


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

    A copy of `lib/log_run.py`'s, the writer of the file this reads; the two
    resolve independently, so a silently-wrong path here would make logged runs
    vanish from the retro with no error. `test_ledger_dir_agrees.py` runs both.
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


# The fleet list lives beside the other `*.local.md` overlays in the repo's
# own tree, never in the plugin: which repos exist is a fact about the
# machine, and the plugin ships procedure.
_FLEET_FILE = "fleet.local.md"


def _fleet_roots(path: Path) -> list[Path]:
    """Repo roots listed in the fleet file, one per `- ` bullet.

    A copy of `lib/ledger_summary.py`'s, kept in step by hand. Format follows
    `cla.io/project-tokens.local.md`: one item per `- ` bullet, inline `#`
    comments and surrounding backticks stripped. It holds repo ROOTS rather than
    ledger paths, so one file serves both readers.

    Raises on a missing or contentless file; this reader's default run catches
    that and falls back to the local ledger, saying why.
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


def _default_log_path() -> Path:
    """This loop's ledger inside the dir the writer resolves."""
    return _runs_dir() / "spec-to-pr-runs.jsonl"


# Phase names and statuses this reads by value. `lib/log_run.py` defines what a
# record may hold; `tests/consistency/test_run_record_values_agree.py` keeps
# these inside it.
CAPPED_PHASES = ("Review", "Test", "Revise")
NUDGE_PHASES = ("Revise", "Test")
FINDINGS_PHASE = "Revise"
REASON_STATUSES = ("warn", "fail")
# The placeholder `migrate_run_records.py` writes as the reason of a warn/fail
# phase whose record kept none. Ranked with real reasons it would top the list.
UNRECORDED_REASON = "reason not recorded (migrated record)"

# The `--pr-rounds` reversal condition in spec-to-pr's Revise reference.
REVERSAL_MIN_CHANGES = 8
REVERSAL_MIN_CHAINS = 2
CHAIN_PROXY = ("ledger + the date in `ts`: a record carries no chain id, so one "
               "chain spanning several days counts as several chains, and two "
               "chains run on one day in one repo count as one")

NUDGE_RUNS = 5
NUDGE_CAP_HITS = 3
NUDGE_SAME_REASON = 2


def _is_int(value: object) -> bool:
    return type(value) is int  # bool is an int subclass and is not a count


def _unreadable(rec: object) -> str | None:
    """The first field this reader uses that has the wrong shape, or None.

    Only the fields read below are checked; the writer owns the full shape.
    """
    if not isinstance(rec, dict):
        return "not a JSON object"
    for key in ("ts", "change"):
        if not isinstance(rec.get(key), str):
            return f"`{key}`"
    phases = rec.get("phases")
    if not isinstance(phases, list):
        return "`phases`"
    for phase in phases:
        if not (isinstance(phase, dict) and isinstance(phase.get("name"), str)
                and isinstance(phase.get("status"), str)):
            return "`phases` entry"
        if "reason" in phase and not isinstance(phase["reason"], str):
            return "`reason`"
        for key in ("rounds_used", "rounds_cap"):
            if key in phase and not _is_int(phase[key]):
                return f"`{key}`"
        rounds = phase.get("findings_by_round", [])
        if not (isinstance(rounds, list) and all(
                isinstance(r, dict) and _is_int(r.get("round")) and _is_int(r.get("found"))
                for r in rounds)):
            return "`findings_by_round`"
    asks = rec.get("asks", [])
    if not (isinstance(asks, list) and all(
            isinstance(a, dict) and isinstance(a.get("header"), str)
            and isinstance(a.get("choice"), str) for a in asks)):
        return "`asks`"
    routing = rec.get("routing", {})
    if not isinstance(routing, dict):
        return "`routing`"
    by_agent = routing.get("revise_findings_by_tier", {})
    if not (isinstance(by_agent, dict) and all(
            isinstance(v, dict) and _is_int(v.get("found")) and _is_int(v.get("phantom"))
            for v in by_agent.values())):
        return "`routing.revise_findings_by_tier`"
    return None


def _load(path: Path) -> tuple[list[dict], int]:
    """Every readable record in one ledger, in file order, and the skip count."""
    records: list[dict] = []
    skipped = 0
    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                problem = f"not JSON ({e.msg})"
            else:
                problem = _unreadable(rec)
            if problem:
                print(f"aggregate: {path} line {lineno} skipped: {problem}", file=sys.stderr)
                skipped += 1
                continue
            records.append(rec)
    return records, skipped


def _cap_hit(phase: dict) -> bool:
    """A phase that used its whole cap, with room to loop. A cap of 1 reached is
    a single pass, not exhaustion."""
    cap = phase.get("rounds_cap", 0)
    return cap > 1 and phase.get("rounds_used") == cap


def _reasons(rec: dict) -> list[str]:
    return [p["reason"] for p in rec["phases"]
            if p["status"] in REASON_STATUSES and p.get("reason")]


def aggregate(records: list[dict]) -> dict:
    """The window metrics over the records given."""
    warn_reasons: Counter = Counter()
    unrecorded = 0
    caps = {name: {"hit": 0, "total": 0} for name in CAPPED_PHASES}
    findings: dict[str, dict[str, int]] = defaultdict(
        lambda: {"found": 0, "phantom": 0, "runs": 0})
    asks: dict[str, Counter] = defaultdict(Counter)
    for rec in records:
        for reason in _reasons(rec):
            if reason == UNRECORDED_REASON:
                unrecorded += 1
            else:
                warn_reasons[reason] += 1
        for phase in rec["phases"]:
            if phase["name"] in caps and phase.get("rounds_cap", 0) > 1:
                caps[phase["name"]]["total"] += 1
                caps[phase["name"]]["hit"] += _cap_hit(phase)
        by_agent = rec.get("routing", {}).get("revise_findings_by_tier", {})
        for agent, counts in by_agent.items():
            findings[agent]["found"] += counts["found"]
            findings[agent]["phantom"] += counts["phantom"]
            findings[agent]["runs"] += 1
        for ask in rec.get("asks", []):
            asks[ask["header"]][ask["choice"]] += 1
    stamps = sorted(rec["ts"] for rec in records)
    return {
        "runs_analyzed": len(records),
        "window": {"first_ts": stamps[0] if stamps else None,
                   "last_ts": stamps[-1] if stamps else None},
        "warn_reasons": [{"reason": r, "count": c} for r, c in warn_reasons.most_common(10)],
        "warn_reasons_unrecorded": unrecorded,
        "cap_exhaustion": {name.lower(): counts for name, counts in caps.items()},
        "revise_findings": {agent: dict(c) for agent, c in sorted(findings.items())},
        "asks": [{"header": h, "choices": dict(c)} for h, c in asks.items()],
    }


def reversal_check(records: list[tuple[str, dict]]) -> dict:
    """Revise's `--pr-rounds` reversal condition, computed outright.

    A change counts when its Revise `findings_by_round` holds a round >= 2, and
    surfaces when such a round found at least one Critical or Important. Changes
    are distinct (ledger, change) pairs, so a re-run change counts once. `records`
    is (ledger, record) over every record read.
    """
    changes: set[tuple[str, str]] = set()
    surfaced: set[tuple[str, str]] = set()
    chains: set[tuple[str, str]] = set()
    for ledger, rec in records:
        later = [r for p in rec["phases"] if p["name"] == FINDINGS_PHASE
                 for r in p.get("findings_by_round", []) if r["round"] >= 2]
        if not later:
            continue
        key = (ledger, rec["change"])
        changes.add(key)
        chains.add((ledger, rec["ts"][:10]))
        if any(r["found"] >= 1 for r in later):
            surfaced.add(key)
    return {
        "changes_with_round_2": len(changes),
        "min_changes": REVERSAL_MIN_CHANGES,
        "surfaced_critical_or_important": len(surfaced),
        "chains": len(chains),
        "min_chains": REVERSAL_MIN_CHAINS,
        "chain_proxy": CHAIN_PROXY,
        "condition_met": (len(changes) >= REVERSAL_MIN_CHANGES
                          and len(chains) >= REVERSAL_MIN_CHAINS
                          and 2 * len(surfaced) > len(changes)),
    }


def nudge(records: list[dict]) -> str | None:
    """One line suggesting the retro, or None, over the last NUDGE_RUNS records."""
    recent = records[-NUDGE_RUNS:]
    why = []
    for name in NUDGE_PHASES:
        hits = sum(any(p["name"] == name and _cap_hit(p) for p in rec["phases"])
                   for rec in recent)
        if hits >= NUDGE_CAP_HITS:
            why.append(f"{name} hit its round cap in {hits} of the last {len(recent)} runs")
    seen = Counter(r for rec in recent for r in set(_reasons(rec)) if r != UNRECORDED_REASON)
    for reason, count in seen.most_common():
        if count >= NUDGE_SAME_REASON:
            short = reason if len(reason) <= 80 else reason[:77] + "..."
            why.append(f'warn reason "{short}" recurred in {count} of the last {len(recent)} runs')
    if not why:
        return None
    return f"Retro nudge: {'; '.join(why)} - consider /cla:spec-to-pr-retro."


def _ledger_paths(explicit: list[Path] | None) -> tuple[list[Path], str, str | None]:
    """(paths, source, fallback reason). Raises when the repo root cannot be
    resolved."""
    if explicit:
        return explicit, "log", None
    local = _default_log_path()
    fleet_file = _runs_dir().parent / _FLEET_FILE
    try:
        roots = _fleet_roots(fleet_file)
    except FileNotFoundError:
        return [local], "local", f"no fleet file at {fleet_file}"
    except ValueError:
        return [local], "local", f"{fleet_file} lists no repo root"
    if not any(root.is_dir() for root in roots):
        return [local], "local", (f"{fleet_file} lists no repo root that exists on "
                                  f"this machine (its paths are per-machine)")
    return [root / "cla.io" / "retro" / local.name for root in roots], "fleet", None


def main() -> int:
    try:  # UTF-8 stdout, so a non-ASCII ask label survives a cp1252 console
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--log", type=Path, nargs="+", metavar="PATH",
                       help="read these ledgers instead of the fleet")
    group.add_argument("--nudge", action="store_true",
                       help="print one retro-nudge line or nothing, from this "
                            "repo's last 5 records; never fails")
    parser.add_argument("--limit", type=int, default=10,
                        help="window: the last N records PER LEDGER (default 10, 0 = all)")
    args = parser.parse_args()

    if args.nudge:
        try:
            path = _default_log_path()
            line = nudge(_load(path)[0]) if path.exists() else None
        except (OSError, ValueError, RuntimeError) as e:
            print(f"aggregate: no nudge ({e})", file=sys.stderr)
            return 0
        if line:
            print(line)
        return 0

    try:
        paths, source, fallback = _ledger_paths(args.log)
    except (ValueError, RuntimeError) as e:
        print(f"aggregate: {e}", file=sys.stderr)
        return 1
    if fallback:
        print(f"aggregate: reading this repo's ledger only — {fallback}", file=sys.stderr)

    ledgers: list[dict] = []
    window: list[dict] = []
    everything: list[tuple[str, dict]] = []
    skipped = 0
    seen: set[Path] = set()
    for path in paths:
        key = path.resolve()
        if key in seen:  # one ledger named twice would double every count
            continue
        seen.add(key)
        records, bad = _load(path) if path.exists() else ([], 0)
        if not path.exists():
            print(f"aggregate: no ledger at {path}; contributing 0 runs", file=sys.stderr)
        skipped += bad
        everything += [(str(path), rec) for rec in records]
        window += records[-args.limit:] if args.limit > 0 else records
        ledgers.append({"path": str(path), "found": path.exists(),
                        "records": len(records), "skipped": bad})

    result: dict = {"source": source}
    if fallback:
        result["fallback"] = fallback
    result["ledgers"] = ledgers
    result.update(aggregate(window))
    result["skipped_records"] = skipped
    result["findings_by_round_reversal"] = reversal_check(everything)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
