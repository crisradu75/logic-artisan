#!/usr/bin/env python3
"""Append one JSON line to a project run-ledger under `cla.io/retro/`.

ONE writer, shared by every skill that keeps a ledger, invoked with the ledger
filename as an argument:

    python ${CLAUDE_PLUGIN_ROOT}/lib/log_run.py spec-to-pr-runs.jsonl < record.json

There used to be five near-identical copies of this file (one per skill), kept
in step by a dedicated drift check. The copies existed because a skill cannot
import another skill's helper — a consuming repo may install and invoke each
one independently. Living at the plugin root instead of under
`skills/<name>/scripts/` sidesteps that entirely: nothing imports it, the
skills invoke it as a program.

Three of those five per-skill WRITERS were deleted rather than migrated
(`multi-pr`, `multi-spec`, `multi-lite`); the ledger FILES they left behind still
exist across the fleet. Every ledger now has a reader: `spec-to-pr-runs` and
`codify-runs` by their own retro skills, and any other by `lib/ledger_summary.py`,
which derives a summary from the records rather than being written per ledger. No record count is
quoted here on purpose: it goes stale on the next append, and a stale number in a
docstring reads as fact.

Reads a JSON object from stdin (the run record the caller assembled from its
own outcomes) and appends it as a single line to:

    <repo-root>/cla.io/retro/<ledger>

The repo root comes from `git rev-parse --show-toplevel`, so the ledger sits
alongside the skills and syncs across machines via git rather than living in a
machine-local `~/.claude/projects/<hash>/`. CLAUDE_RETRO_DIR overrides it
(absolute path); used by tests and non-standard layouts. A repo that expects
concurrent appends from two machines should set `merge=union` on
`cla.io/retro/*.jsonl` in its own `.gitattributes`; without it the two appends
conflict on merge. This repo does NOT set it — the claim that it did was carried
in this docstring for some time and was simply false.

Appends are a single `write()` of one line in "ab" mode. POSIX writes below
PIPE_BUF (typically 4 KiB, comfortably above a counts-only run record) are
atomic, so concurrent runs from parallel sessions cannot interleave bytes
within a line. Windows offers the same effective guarantee for small writes to
local files. This avoids the read-modify-rewrite pattern, which is both O(N)
per append and silently race-unsafe (two readers see the same N, both rewrite,
one append is lost).

The record is COUNTS-ONLY (no prose) — prose lives in the skill's own report.
The 4 KiB ceiling below is what enforces that in practice.

SHAPES. `SHAPES` below is the one definition of what a `spec-to-pr-runs` and a
`codify-runs` record look like — required keys AND value shapes, because the
defect that motivated it (`phases` written as an object instead of a list) keeps
the key present and only a value check sees it. Producers are prose a model
follows, and in long sessions it wrote records from memory: `date` for `ts`, a
dict for `phases`. A refused record prints ONE line naming the field and
nothing is written. Any other ledger name gets only the name and size checks.

A caller MUST NOT halt if this script fails — a missing log line is infinitely
preferable to a halted workflow at the end of a successful run. On a shape
refusal the caller fixes the field named and retries once; on any other
failure, or a second refusal, it notes the line and continues.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# A ledger name is a bare filename, never a path. Without this an argument like
# `../../etc/thing.jsonl` would write outside the ledger dir — the caller is a
# model assembling a command line, so the check is not hypothetical.
_LEDGER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.jsonl$")


# --------------------------------------------------------------------------- #
# Record shapes
# --------------------------------------------------------------------------- #
# A shape is one of four tuples:
#   ("leaf", test, what)              test(value) -> bool; `what` goes in the refusal
#   ("list", item_shape)
#   ("map", value_shape, rule)        an object with free keys, every value one shape
#   ("obj", required, optional, rule) dicts of key -> shape; rule(obj) -> refusal|None
# Keys not named are allowed and kept: a shape says what readers rely on, not
# everything a producer may add.

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$")


def _iso(value: object, *, date_ok: bool) -> bool:
    """An ISO-8601 date-time with a zone (or, when `date_ok`, a bare date) that
    also names a real instant — the pattern alone accepts month 13."""
    if not isinstance(value, str):
        return False
    if not (_DATETIME_RE.match(value) or (date_ok and _DATE_RE.match(value))):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _leaf(test, what: str) -> tuple:
    return ("leaf", test, what)


def _one_of(*values: str) -> tuple:
    return _leaf(lambda v: v in values, "one of " + ", ".join(f'"{v}"' for v in values))


def _obj(required: dict | None = None, optional: dict | None = None, rule=None) -> tuple:
    return ("obj", required or {}, optional or {}, rule)


COUNT = _leaf(lambda v: type(v) is int and v >= 0, "a non-negative integer")
BOOL = _leaf(lambda v: type(v) is bool, "true or false")
TEXT = _leaf(lambda v: isinstance(v, str) and v.strip() != "", "a non-empty string")
TS = _leaf(lambda v: _iso(v, date_ok=False),
           'an ISO-8601 date-time with a zone, e.g. "2026-05-28T14:32:11Z"')
TS_OR_DATE = _leaf(lambda v: _iso(v, date_ok=True),
                   'an ISO-8601 date or date-time, e.g. "2026-05-28"')
COUNT_OR_NULL = _leaf(lambda v: v is None or (type(v) is int and v >= 0),
                      "a non-negative integer or null")

SPEC_TO_PR_PHASES = ("Precheck", "Propose", "Review", "Implement", "Test", "Ship",
                     "Revise", "Archive", "Handoff")
REVISE_AGENTS = ("code-reviewer", "silent-failure-hunter", "pr-test-analyzer",
                 "comment-analyzer", "type-design-analyzer", "plugin-dev:skill-reviewer")
RUNGS = ("checklist", "memory", "claude_md", "skill_md", "hook", "script")


def _phase_rule(phase: dict) -> str | None:
    name = phase["name"]
    if phase["status"] in ("warn", "fail") and "reason" not in phase:
        return f"`reason` is required on a {phase['status']} phase ({name})"
    if ("rounds_used" in phase) != ("rounds_cap" in phase):
        return f"`rounds_used` and `rounds_cap` go together ({name})"
    if name == "Review" and "size_gate" in phase:
        if (phase["size_gate"] == "large") != bool(phase.get("agents")):
            return ("`agents` must list the Review agents that ran in large mode, "
                    "and be omitted or [] in small mode (Review)")
    return None


def _findings_rule(by_agent: dict) -> str | None:
    for agent in by_agent:
        if agent not in REVISE_AGENTS:
            return (f"`routing.revise_findings_by_tier` key {agent!r} must be one of "
                    + ", ".join(REVISE_AGENTS))
    return None


_PHASE = _obj(
    {"name": _one_of(*SPEC_TO_PR_PHASES), "status": _one_of("ok", "warn", "skip", "fail")},
    {"reason": TEXT, "rounds_used": COUNT, "rounds_cap": COUNT, "report_chars": COUNT,
     "size_gate": _one_of("small", "large"),
     "verdict": _one_of("READY", "FIX FIRST", "RETHINK"),
     "verified_claims_count": COUNT,
     "agents": ("list", TEXT),
     "version_bumped": BOOL,
     "findings_by_round": ("list", _obj(
         {"round": COUNT, "found": COUNT, "sibling_instance": COUNT_OR_NULL}))},
    _phase_rule,
)

SHAPES: dict[str, tuple] = {
    "spec-to-pr-runs.jsonl": _obj(
        {"ts": TS, "change": TEXT,
         "mode": _one_of("description", "explore-result", "existing-change"),
         "phases": ("list", _PHASE)},
        {"args": _obj(optional={"review_rounds": COUNT, "test_rounds": COUNT,
                                "pr_rounds": COUNT, "auto": BOOL}),
         "asks": ("list", _obj({"header": TEXT, "choice": TEXT})),
         "deferred_to_todo": COUNT,
         "routing": _obj(optional={
             "revise_findings_by_tier": ("map", _obj({"found": COUNT, "phantom": COUNT}),
                                         _findings_rule)})},
    ),
    "codify-runs.jsonl": _obj(
        {"ts": TS_OR_DATE, "scope": TEXT,
         "suggestions": _obj({"proposed": COUNT, "applied": COUNT, "rejected": COUNT}),
         "memory": _obj({"proposed": COUNT, "applied": COUNT}),
         "re_offenses": ("list", _obj({"lesson": TEXT, "escalated_to": _one_of(*RUNGS)},
                                      {"failing_artifact": TEXT})),
         "rejected_lessons": ("list", TEXT),
         "maintenance": _obj({"failure_modes_bullets": COUNT, "live_log_entries": COUNT,
                              "trimmed": BOOL}),
         "process_issue": BOOL},
        {"effectiveness": _obj({"prevented": COUNT, "re_offended": COUNT,
                                "not_exercised": COUNT}),
         "output_chars": COUNT},
    ),
}


def _shown(value: object) -> str:
    text = json.dumps(value)
    return text if len(text) <= 40 else text[:37] + "..."


def shape_problem(value: object, shape: tuple, path: str = "") -> str | None:
    """The first way `value` departs from `shape`, as one line naming the field,
    or None when it conforms."""
    kind = shape[0]
    here = f"`{path}`" if path else "the record"
    if kind == "leaf":
        return None if shape[1](value) else f"{here} must be {shape[2]}, got {_shown(value)}"
    if kind == "list":
        if not isinstance(value, list):
            return f"{here} must be a list, got {_shown(value)}"
        for i, item in enumerate(value):
            problem = shape_problem(item, shape[1], f"{path}[{i}]")
            if problem:
                return problem
        return None
    if not isinstance(value, dict):
        return f"{here} must be an object, got {_shown(value)}"
    if kind == "map":  # free keys, one value shape, then a rule over the keys
        for key, item in value.items():
            problem = shape_problem(item, shape[1], f"{path}.{key}")
            if problem:
                return problem
        return shape[2](value)
    _, required, optional, rule = shape
    for key in required:
        if key not in value:
            return f"`{path + '.' if path else ''}{key}` is required"
    for key, sub in {**required, **optional}.items():
        if key in value:
            problem = shape_problem(value[key], sub, f"{path + '.' if path else ''}{key}")
            if problem:
                return problem
    return rule(value) if rule else None


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


def _pin_streams_utf8() -> None:
    """Force UTF-8 on stdout/stderr regardless of the ambient locale."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    _pin_streams_utf8()
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("log_run: usage: log_run.py <ledger-name>.jsonl < record.json", file=sys.stderr)
        return 1
    ledger = args[0]
    if not _LEDGER_RE.match(ledger):
        print(
            f"log_run: {ledger!r} is not a bare `<name>.jsonl` filename; a ledger "
            "argument must not contain a path separator",
            file=sys.stderr,
        )
        return 1

    # Read BYTES and decode explicitly, rather than letting the text wrapper
    # apply the platform locale.
    try:
        raw = sys.stdin.buffer.read().decode("utf-8")
    except UnicodeDecodeError as e:
        print(f"log_run: stdin is not valid UTF-8: {e}", file=sys.stderr)
        return 1
    try:
        record = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"log_run: invalid JSON on stdin: {e}", file=sys.stderr)
        return 1
    if not isinstance(record, dict):
        print("log_run: top-level JSON must be an object", file=sys.stderr)
        return 1
    if ledger in SHAPES:
        problem = shape_problem(record, SHAPES[ledger])
        if problem:
            print(f"log_run: {ledger} record refused: {problem}", file=sys.stderr)
            return 1

    try:
        log_path = _runs_dir() / ledger
    except (ValueError, RuntimeError) as e:
        print(f"log_run: {e}", file=sys.stderr)
        return 1
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"log_run: cannot create {log_path.parent}: {e}", file=sys.stderr)
        return 1

    line = json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n"
    encoded = line.encode("utf-8")
    if len(encoded) >= 4096:
        # Above PIPE_BUF; concurrent appends could interleave. A counts-only
        # record is well under this threshold — if it isn't, the producer is
        # logging prose (forbidden).
        print(
            f"log_run: record is {len(encoded)} bytes — exceeds 4 KiB atomic-write "
            f"ceiling. Producer is logging prose; trim to counts only.",
            file=sys.stderr,
        )
        return 1

    try:
        with log_path.open("ab") as fh:
            fh.write(encoded)
    except OSError as e:
        print(f"log_run: write failed at {log_path}: {e}", file=sys.stderr)
        return 1

    print(str(log_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
