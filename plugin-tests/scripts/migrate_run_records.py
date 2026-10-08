#!/usr/bin/env python3
"""Rewrite old-shape `spec-to-pr-runs.jsonl` records into the shape `log_run.py` now enforces.

One-off, run once per repo (in that repo's own PR):

    python3 plugin-tests/scripts/migrate_run_records.py <ledger> [--dry-run] [--history-from <tracked-ledger>]

Before `log_run.py` checked shapes, a model writing the record from memory produced
several shapes the retro could not read. Every form below was found in a real
ledger; each is mapped mechanically, never guessed:

  * `phases` as an object, `{"review": "ok", ...}` or `{"review": {"status": ...}}`
    -> a list of `{name, status, ...}` in the same order. Per-phase fields a reader
    uses are lifted from the record's own side block (`review`, `test`, `revise`,
    ...; `rounds` read as `rounds_used`) and `rounds_cap` from its `caps`. A lifted
    value that would not pass the shape check is left where it was.
  * a phase keyed `phase` instead of `name`, or named in lower case -> `name`,
    capitalised the way the reader expects.
  * status `partial` -> `warn`; a `warn`/`fail` with no reason gets the side block's
    `warn_reason`, else `NO_REASON`, which the retro counts apart from real reasons.
  * `date` (or, failing that, `started`) -> `ts` at `T00:00:00Z`; a date-only `ts`
    the same way. A `ts` that is no date at all is replaced the same way and kept
    as `ts_unmapped`. With no date in the record at all, the author time of the
    commit that appended the line (`git log -L`) — the run's Handoff commits it, so
    that is when the run ended.
  * `change_name` -> `change`.
  * `asks` as `{"count": n, "choices": [...]}` or a bare count -> a list of
    `{header, choice}`, with "(not recorded)" for what the record did not keep.
  * Revise `agents`: the `pr-review-toolkit:` prefix is stripped to the bare id;
    an entry that is still no canonical agent (a retired name, `orchestrator-inline`
    lifted from a round-2 list) moves to `agents_unmapped` on the phase.
  * `routing.revise_findings_by_tier`: a canonical agent whose value counts by
    severity only, `{"critical": n, "important": n, "suggestion": n}` with zeros
    omitted, becomes `{"found": critical + important, "phantom": 0}` — the record
    omits every zero count, so an absent `phantom` is a zero, not an unknown; one
    that also carries `phantom` is ambiguous (counted within those, or beside
    them?) and is not mapped. Every other entry that is not a canonical agent with
    `found`/`phantom` (model-tier or top-level severity keys, retired agent names)
    moves to `routing.revise_findings_unmapped`; `code_reviewer`-style keys are
    re-spelled. When nothing is left the key is dropped: absent reads as no data,
    while `{}` would read as a Revise that found nothing.
  * an `ok` Review whose `size_gate` is outside small/large, or `large` with no
    agents listed (the two cannot both be true) -> moved to `size_gate_unmapped`
    on that phase. A warn Review keeps the pair: that is how a run records agents
    it could not dispatch.

ONE GAP IS LEFT, on purpose. The writer requires `rounds_used`/`rounds_cap` on a
Test or Revise phase that ran; a record written before that rule carried no pair,
and this script does not invent round counts. Such a record is migrated and keeps
that gap — `remaining_problems` excludes it and nothing else.

Every other field is kept. A record that already passes is not touched, so a second
run changes nothing. A record that still fails after mapping is reported with the
check's reason and left exactly as it was.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_LIB = Path(__file__).resolve().parents[2] / ".claude" / "plugins" / "cla" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))
import log_run  # noqa: E402

LEDGER = "spec-to-pr-runs.jsonl"
SHAPE = log_run.SHAPES[LEDGER]
PHASE_SHAPE = SHAPE[1]["phases"][1]
AGENT_FINDINGS_SHAPE = SHAPE[2]["routing"][2]["revise_findings_by_tier"][1]
NOT_RECORDED = "(not recorded)"
# The retro's aggregator holds a copy of this string to count it apart from real
# reasons; a consistency test keeps the two equal.
NO_REASON = "reason not recorded (migrated record)"
TOOLKIT_PREFIX = "pr-review-toolkit:"
_SEVERITY_ONLY = {"critical", "important", "suggestion"}
# See "ONE GAP IS LEFT" above. Matched against the writer's own refusal clause, so a
# reworded clause stops matching and the record reports as unmappable — loud, not lax.
_HISTORY_GAP = re.compile(r"^`rounds_used` and `rounds_cap` are required on a (Test|Revise) "
                          r"phase that was not skipped \((ok|warn|fail)\)$")
_CANONICAL = {name.lower(): name for name in log_run.SPEC_TO_PR_PHASES}
_CAP_KEY = {"Review": "review_rounds", "Test": "test_rounds", "Revise": "pr_rounds"}
_LIFT = ("rounds_used", "rounds_cap", "size_gate", "verdict", "verified_claims_count",
         "agents", "version_bumped", "findings_by_round", "report_chars", "reason")


def remaining_problems(rec: dict) -> list[str]:
    """The writer's refusals for `rec`, less the one gap history may keep."""
    return [p for p in log_run.shape_problems(rec, SHAPE) if not _HISTORY_GAP.match(p)]


def _field_ok(key: str, value: object) -> bool:
    shape = PHASE_SHAPE[2].get(key) or PHASE_SHAPE[1].get(key)
    return shape is not None and log_run.shape_problem(value, shape) is None


def _side_fields(side: dict, name: str) -> dict:
    """The reader-facing fields a dict-era side block carried for this phase."""
    out = {k: side[k] for k in _LIFT if k in side}
    if "rounds_used" not in out and "rounds" in side:
        out["rounds_used"] = side["rounds"]
    if "reason" not in out and "warn_reason" in side:
        out["reason"] = side["warn_reason"]
    if name == "Revise" and "agents" not in out:
        merged: list = []
        for key in ("agents_round1", "agents_round2", "agents_dispatched"):
            if isinstance(side.get(key), list):
                merged += [a for a in side[key] if a not in merged]
        if merged:
            out["agents"] = merged
    return out


def _phase_list(rec: dict, notes: list[str]) -> list | None:
    phases = rec.get("phases")
    caps = rec.get("caps") if isinstance(rec.get("caps"), dict) else {}
    if isinstance(phases, dict):
        entries = []
        for key, value in phases.items():
            if isinstance(value, dict):
                entry = {"name": key, **{k: v for k, v in value.items() if k != "name"}}
            else:
                entry = {"name": key, "status": value}
            entries.append(entry)
        notes.append("phases object -> list")
        from_dict = True
    elif isinstance(phases, list):
        entries = [dict(p) if isinstance(p, dict) else p for p in phases]
        from_dict = False
    else:
        return None
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        if "name" not in entry and "phase" in entry:
            entry = entries[i] = {"name": entry["phase"],
                                  **{k: v for k, v in entry.items() if k != "phase"}}
            notes.append("phase key -> name")
        name = entry.get("name")
        if isinstance(name, str) and name not in _CANONICAL.values() and name.lower() in _CANONICAL:
            entry["name"] = _CANONICAL[name.lower()]
            notes.append("phase names capitalised")
        name = entry.get("name")
        side = rec.get(name.lower()) if isinstance(name, str) else None
        if from_dict:
            lifted = _side_fields(side, name) if isinstance(side, dict) else {}
            cap = caps.get(_CAP_KEY.get(name, ""))
            has_used = "rounds_used" in entry or "rounds_used" in lifted
            if (has_used and "rounds_cap" not in entry and "rounds_cap" not in lifted
                    and _field_ok("rounds_cap", cap)):
                lifted["rounds_cap"] = cap
            if "rounds_used" in lifted and "rounds_cap" not in entry and "rounds_cap" not in lifted:
                del lifted["rounds_used"]  # still in the side block, where it came from
            for key, value in lifted.items():
                if key not in entry and _field_ok(key, value):
                    entry[key] = value
            if ("rounds_used" in entry) != ("rounds_cap" in entry):
                # Half a pair cannot be read; the half the record carried is kept
                # beside the phase rather than dropped.
                for key in ("rounds_used", "rounds_cap"):
                    if key in entry:
                        entry[key + "_unmapped"] = entry.pop(key)
        if entry.get("status") == "partial":
            entry["status"] = "warn"
            entry.setdefault("reason", "partial (migrated record)")
            notes.append(f"{name} status partial -> warn")
        if entry.get("status") in ("warn", "fail") and "reason" not in entry:
            entry["reason"] = NO_REASON
            notes.append(f"{name} {entry['status']} given a reason")
        # After the status is final: only an `ok` Review must agree with itself.
        if name == "Review" and "size_gate" in entry and (
                entry["size_gate"] not in log_run.SIZE_GATES
                or (entry.get("status") == "ok"
                    and (entry["size_gate"] == "large") != bool(entry.get("agents")))):
            entry["size_gate_unmapped"] = entry.pop("size_gate")
            notes.append("Review size_gate moved aside")
        if name == "Revise":
            _revise_agents(entry, notes)
    return entries


def _revise_agents(entry: dict, notes: list[str]) -> None:
    """Revise `agents` by canonical id: prefix stripped, anything else set aside."""
    agents = entry.get("agents")
    if not isinstance(agents, list):
        return
    kept: list = []
    aside: list = []
    stripped = 0
    for agent in agents:
        bare = agent
        if isinstance(agent, str) and agent.startswith(TOOLKIT_PREFIX):
            bare = agent[len(TOOLKIT_PREFIX):]
        if isinstance(bare, str) and bare in log_run.REVISE_AGENTS:
            stripped += bare != agent
            if bare not in kept:
                kept.append(bare)
        else:
            aside.append(agent)
    if kept == agents:
        return
    if stripped:
        notes.append(f"Revise agents: {TOOLKIT_PREFIX} prefix stripped")
    if aside:
        entry["agents_unmapped"] = aside
        notes.append(f"Revise agents: {len(aside)} non-agent entries moved aside")
    if kept or not aside:
        entry["agents"] = kept
    else:
        del entry["agents"]  # nothing canonical was dispatched on record: no data, not none


def _asks(value: object) -> list | None:
    if isinstance(value, list):
        return value
    if type(value) is int and value >= 0:
        return [{"header": NOT_RECORDED, "choice": NOT_RECORDED}] * value
    if isinstance(value, dict):
        choices = value.get("choices", [])
        count = value.get("count", len(choices) if isinstance(choices, list) else 0)
        if not isinstance(choices, list) or type(count) is not int or count < len(choices):
            return None
        asks = [{"header": NOT_RECORDED, "choice": c} for c in choices]
        return asks + [{"header": NOT_RECORDED, "choice": NOT_RECORDED}] * (count - len(choices))
    return None


def _findings(routing: dict, notes: list[str]) -> dict:
    by_tier = routing.get("revise_findings_by_tier")
    if not isinstance(by_tier, dict):
        return routing
    kept, moved = {}, {}
    severity_mapped = 0
    for key, value in by_tier.items():
        agent = key.replace("_", "-") if isinstance(key, str) else key
        if agent in log_run.REVISE_AGENTS and agent not in kept:
            if log_run.shape_problem(value, AGENT_FINDINGS_SHAPE) is None:
                kept[agent] = value
                continue
            counts = _severity_counts(value)
            if counts is not None:
                kept[agent] = counts
                severity_mapped += 1
                continue
        moved[key] = value
    if not moved and not severity_mapped and list(kept) == list(by_tier):
        return routing
    out = {}
    for key, value in routing.items():
        if key != "revise_findings_by_tier":
            out[key] = value
        elif kept:
            out[key] = kept
    if moved:
        out["revise_findings_unmapped"] = moved
        notes.append(f"revise_findings_by_tier: {len(moved)} non-agent entries moved aside")
        if not kept:
            notes.append("revise_findings_by_tier dropped (nothing left)")
    if severity_mapped:
        notes.append(f"revise_findings_by_tier: {severity_mapped} severity counts -> found")
    if not moved and not severity_mapped:
        notes.append("revise_findings_by_tier keys re-spelled")
    return out


def _severity_counts(value: object) -> dict | None:
    """`{"critical": n, "important": n, "suggestion": n}`, zeros omitted, as
    `{found, phantom}`; None for anything else, including a `phantom` key."""
    if not isinstance(value, dict) or not set(value) <= _SEVERITY_ONLY:
        return None
    if not all(type(n) is int and n >= 0 for n in value.values()):
        return None
    return {"found": value.get("critical", 0) + value.get("important", 0), "phantom": 0}


def _date_ts(value: object) -> str | None:
    if isinstance(value, str) and len(value) == 10 and log_run._iso(value, date_ok=True):
        return value + "T00:00:00Z"
    return None


def migrate(rec: dict, first_seen=None) -> tuple[dict, list[str]]:
    """The record in the enforced shape, and what changed. A record already in
    shape comes back as is, with no notes. `first_seen()` gives the time the line
    entered git, asked only when the record carries no date of its own."""
    if not remaining_problems(rec):
        return rec, []
    notes: list[str] = []
    ts, ts_from = None, None
    if not (isinstance(rec.get("ts"), str) and log_run._iso(rec["ts"], date_ok=False)):
        for key in ("ts", "date", "started"):
            ts = _date_ts(rec.get(key))
            if ts:
                ts_from = key
                break
        if ts is None and "ts" not in rec and first_seen is not None:
            ts = first_seen()
            ts_from = "git history" if ts else None
    out: dict = {}
    # The derived `ts` takes the place of the key it replaces: an existing `ts`
    # (date-only or junk), else the `date` it came from, else the front.
    if ts and "ts" not in rec and ts_from != "date":
        out["ts"] = ts
    for key, value in rec.items():
        if key == "ts" and ts:
            out["ts"] = ts
            if ts_from != "ts":  # junk, not a date: kept beside, never lost
                out["ts_unmapped"] = value
                notes.append("unreadable ts moved aside")
        elif key == "date" and ts_from == "date":
            out["ts"] = ts
        elif key == "change_name" and "change" not in rec:
            out["change"] = value
            notes.append("change_name -> change")
        elif key == "phases":
            mapped = _phase_list(rec, notes)
            out[key] = value if mapped is None else mapped
        elif key == "asks":
            mapped = _asks(value)
            if mapped is not value and mapped is not None:
                notes.append("asks -> list")
            out[key] = value if mapped is None else mapped
        elif key == "routing" and isinstance(value, dict):
            out[key] = _findings(value, notes)
        else:
            out[key] = value
    if ts_from:
        notes.insert(0, f"ts from {ts_from}" + f" ({ts})")
    return out, list(dict.fromkeys(notes))


class _History:
    """When each line of a tracked ledger first appeared, from git.

    `git log -L` and not `git blame`: blame names the LAST commit to touch a line,
    and ledger lines do get rewritten — one interoga-ro record's blame is a docs
    commit three weeks after its run. The oldest commit in the line's -L history is
    the one that appended it. A line is only looked up when it is byte-identical to
    that line at HEAD, so a working copy that has drifted from HEAD cannot borrow
    another record's time.
    """

    def __init__(self, path: Path, current: list[str]) -> None:
        self.path = path
        self.current = current
        self.head: list[str] | None = None

    def _git(self, *args: str) -> str | None:
        try:
            out = subprocess.run(["git", *args], cwd=self.path.parent, capture_output=True,
                                 text=True, encoding="utf-8", errors="replace", timeout=60)
        except (OSError, subprocess.SubprocessError):
            return None
        return out.stdout if out.returncode == 0 else None

    def first_seen(self, line_no: int) -> str | None:
        if self.head is None:
            self.head = (self._git("show", f"HEAD:./{self.path.name}") or "").splitlines()
        if (line_no > len(self.head) or line_no > len(self.current)
                or self.head[line_no - 1].strip() != self.current[line_no - 1].strip()):
            return None
        log = self._git("log", f"-L{line_no},{line_no}:./{self.path.name}",
                        "--format=%at", "--no-patch")
        stamps = [t for t in (log or "").split() if t.isdigit()]
        if not stamps:
            return None
        when = datetime.fromtimestamp(int(stamps[-1]), tz=timezone.utc)
        return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def run(ledger: Path, dry_run: bool, history_from: Path | None) -> int:
    lines = ledger.read_text(encoding="utf-8").splitlines(keepends=True)
    history = _History(history_from or ledger, lines)
    out_lines, migrated, unmapped, valid, gaps = [], 0, 0, 0, 0
    for no, line in enumerate(lines, 1):
        if not line.strip():
            out_lines.append(line)
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"line {no}: cannot map: not JSON ({e})")
            unmapped += 1
            out_lines.append(line)
            continue
        if not isinstance(rec, dict):
            print(f"line {no}: cannot map: not a JSON object")
            unmapped += 1
            out_lines.append(line)
            continue
        if not remaining_problems(rec):
            valid += 1
            gaps += log_run.shape_problem(rec, SHAPE) is not None
            out_lines.append(line)
            continue
        new, notes = migrate(rec, lambda: history.first_seen(no))
        problems = remaining_problems(new)
        label = rec.get("change") or rec.get("change_name") or "?"
        if problems:
            print(f"line {no} ({label}): cannot map: " + "; ".join(problems))
            unmapped += 1
            out_lines.append(line)
            continue
        print(f"line {no} ({label}): " + "; ".join(notes))
        migrated += 1
        gaps += log_run.shape_problem(new, SHAPE) is not None
        ending = "\n" if line.endswith("\n") else ""
        out_lines.append(json.dumps(new, separators=(",", ":"), ensure_ascii=False) + ending)
    print(f"{ledger}: {len(lines)} lines, {valid} already in shape, {migrated} migrated, "
          f"{unmapped} cannot map, {gaps} keep the rounds-pair gap"
          + (" (dry run, nothing written)" if dry_run else ""))
    if migrated and not dry_run:
        tmp = ledger.with_name(ledger.name + ".migrating")
        tmp.write_text("".join(out_lines), encoding="utf-8", newline="")
        os.replace(tmp, ledger)
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("ledger", type=Path, help="a spec-to-pr-runs.jsonl file")
    parser.add_argument("--dry-run", action="store_true", help="report, write nothing")
    parser.add_argument("--history-from", type=Path, default=None, metavar="PATH",
                        help="the tracked ledger to read commit times from, when LEDGER "
                             "is a copy of it (default: LEDGER itself)")
    args = parser.parse_args(argv)
    if not args.ledger.is_file():
        print(f"migrate: no file at {args.ledger}", file=sys.stderr)
        return 1
    return run(args.ledger, args.dry_run, args.history_from)


if __name__ == "__main__":
    sys.exit(main())
