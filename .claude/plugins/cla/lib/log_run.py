#!/usr/bin/env python3
"""Append one JSON line to a project run-ledger under `cla.io/retro/`.

ONE writer, invoked with the ledger filename as an argument:

    python ${CLAUDE_PLUGIN_ROOT}/lib/log_run.py spec-to-pr-runs.jsonl < record.json

There used to be five near-identical copies of this file (one per skill), kept
in step by a dedicated drift check. The copies existed because a skill cannot
import another skill's helper — a consuming repo may install and invoke each
one independently. Living at the plugin root instead of under
`skills/<name>/scripts/` sidesteps that entirely: nothing imports it, the
skills invoke it as a program.

One ledger remains, and this writer refuses any other name: `spec-to-pr-runs`,
read by `/cla:spec-to-pr-retro`. Every other ledger a skill once wrote, the
codify one included, was retired because nothing read it; `/cla:cla-setup` lists
the retired files a repo still holds and offers to delete them. No record count is quoted
here on purpose: it goes stale on the next append, and a stale number in a
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

SHAPES. `SHAPES` below is the one definition of what a `spec-to-pr-runs` record
looks like — required keys AND value shapes, because the
defect that motivated it (`phases` written as an object instead of a list) keeps
the key present and only a value check sees it. Producers are prose a model
follows, and in long sessions it wrote records from memory: `date` for `ts`, a
dict for `phases`. A refused record prints ONE line naming EVERY field that is
off, joined by `; `, and nothing is written — every problem at once, because the
caller has one retry and a check that named only the first would spend it on a
record still wrong in a field it had not been told about. A ledger name not in
`SHAPES` is refused: a ledger with no shape is one nothing reads, and a typo'd
name would otherwise start a new file the reader never opens.

A caller MUST NOT halt if this script fails — a missing log line is infinitely
preferable to a halted workflow at the end of a successful run. On a shape
refusal the caller rebuilds the record from its reference example, fixing every
field named, and retries once; on any other failure, or a second refusal, it
notes the line and continues.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------------- #
# Record shapes
# --------------------------------------------------------------------------- #
# A shape is one of four tuples:
#   ("leaf", test, what)              test(value) -> bool; `what` goes in the refusal
#   ("list", item_shape)
#   ("map", value_shape, rule)        an object with free keys, every value one shape;
#                                     rule(obj) -> list of refusals over the keys
#   ("obj", required, optional, rule) dicts of key -> shape; rule(obj) -> list of refusals
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
TEXT = _leaf(lambda v: isinstance(v, str) and v.strip() != "", "a non-empty string")
TS = _leaf(lambda v: _iso(v, date_ok=False),
           'an ISO-8601 date-time with a zone, e.g. "2026-05-28T14:32:11Z"')
FLAG = _leaf(lambda v: isinstance(v, str) and len(v) > 2 and v.startswith("--")
             and "=" not in v and not any(c.isspace() for c in v),
             'a flag name as typed, without its value, e.g. "--inherits"')

SPEC_TO_PR_PHASES = ("Precheck", "Propose", "Review", "Implement", "Test", "Ship",
                     "Revise", "Archive", "Handoff")
STATUSES = ("ok", "warn", "skip", "fail")
# The keys of `revise_findings_by_tier`: the bare id for the five pr-review-toolkit
# agents — not the `pr-review-toolkit:` form passed to `Agent` — and the prefixed one
# for the skill reviewer, which has no bare form. One spelling per agent, so the
# retro's per-agent yield never splits one agent across two keys.
REVISE_AGENTS = ("code-reviewer", "silent-failure-hunter", "pr-test-analyzer",
                 "comment-analyzer", "type-design-analyzer", "plugin-dev:skill-reviewer")
# Phases that loop, and so must say how many rounds they used out of how many,
# whenever they ran. Review loops too but is single-pass by default, and its pair
# stays optional.
ROUNDS_REQUIRED_ON = ("Test", "Revise")


def _phase_rule(phase: dict) -> list[str]:
    """Cross-field checks on one phase. Runs only once `name` and `status`
    conform, so both are known values here; every optional field is read
    defensively, because its own shape problem is reported separately."""
    name, status = phase["name"], phase["status"]
    problems = []
    if status in ("warn", "fail") and "reason" not in phase:
        problems.append(f"`reason` is required on a {status} phase ({name})")
    if ("rounds_used" in phase) != ("rounds_cap" in phase):
        problems.append(f"`rounds_used` and `rounds_cap` go together ({name})")
    elif "rounds_used" not in phase and name in ROUNDS_REQUIRED_ON and status != "skip":
        problems.append(f"`rounds_used` and `rounds_cap` are required on a {name} phase "
                        f"that was not skipped ({status})")
    return problems


def _findings_rule(by_agent: dict) -> list[str]:
    """One refusal for every off-list key, so a record with three retired agent
    names gets one clause, not three copies of the allowed list."""
    bad = [agent for agent in by_agent if agent not in REVISE_AGENTS]
    if not bad:
        return []
    shown = ", ".join(repr(b) for b in bad)
    allowed = ", ".join(REVISE_AGENTS)
    if len(bad) == 1:
        return [f"`routing.revise_findings_by_tier` key {shown} must be one of {allowed}"]
    return [f"`routing.revise_findings_by_tier` keys {shown} must each be one of {allowed}"]


# Only the fields `spec_to_pr_aggregate.py` reads, plus `mode`, which identifies the
# run. Fields an older record carries beyond these are kept and never read.
_PHASE = _obj(
    {"name": _one_of(*SPEC_TO_PR_PHASES), "status": _one_of(*STATUSES)},
    {"reason": TEXT, "rounds_used": COUNT, "rounds_cap": COUNT,
     "findings_by_round": ("list", _obj({"round": COUNT, "found": COUNT}))},
    _phase_rule,
)

SHAPES: dict[str, tuple] = {
    "spec-to-pr-runs.jsonl": _obj(
        {"ts": TS, "change": TEXT,
         "mode": _one_of("description", "explore-result", "existing-change"),
         "phases": ("list", _PHASE)},
        {"flags": ("list", FLAG),
         "escalated_to_diagnose": COUNT,
         "asks": ("list", _obj({"header": TEXT, "choice": TEXT})),
         "routing": _obj(optional={
             "revise_findings_by_tier": ("map", _obj({"found": COUNT, "phantom": COUNT}),
                                         _findings_rule)})},
    ),
}


def _shown(value: object) -> str:
    text = json.dumps(value)
    return text if len(text) <= 40 else text[:37] + "..."


def shape_problems(value: object, shape: tuple, path: str = "") -> list[str]:
    """Every way `value` departs from `shape`, each as one clause naming the
    field; empty when it conforms."""
    kind = shape[0]
    here = f"`{path}`" if path else "the record"
    if kind == "leaf":
        return [] if shape[1](value) else [f"{here} must be {shape[2]}, got {_shown(value)}"]
    if kind == "list":
        if not isinstance(value, list):
            return [f"{here} must be a list, got {_shown(value)}"]
        return [problem for i, item in enumerate(value)
                for problem in shape_problems(item, shape[1], f"{path}[{i}]")]
    if not isinstance(value, dict):
        return [f"{here} must be an object, got {_shown(value)}"]
    if kind == "map":  # free keys, one value shape, then a rule over the keys
        problems = [problem for key, item in value.items()
                    for problem in shape_problems(item, shape[1], f"{path}.{key}")]
        return problems + shape[2](value)
    _, required, optional, rule = shape
    prefix = path + "." if path else ""
    problems = [f"`{prefix}{key}` is required" for key in required if key not in value]
    required_ok = not problems
    for key, sub in {**required, **optional}.items():
        if key in value:
            found = shape_problems(value[key], sub, prefix + key)
            problems += found
            if found and key in required:
                required_ok = False
    # A rule reads the required keys as known values, so it runs only once they
    # all conform; the optional fields it reads are its own to guard.
    if rule and required_ok:
        problems += rule(value)
    return problems


def shape_problem(value: object, shape: tuple) -> str | None:
    """`shape_problems` as the one refusal line, `; `-joined, or None."""
    return "; ".join(shape_problems(value, shape)) or None


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
    guessing a path: the reader, the spec-to-pr aggregator, resolves independently
    with identical logic, so a silently-wrong path here would make logged runs
    vanish from the retro with no error.
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
    # Only a named ledger, so never a path: `../../etc/thing.jsonl` would write
    # outside the ledger dir, and the caller is a model assembling a command line.
    if ledger not in SHAPES:
        print(f"log_run: {ledger!r} is not a ledger; the only ledger is "
              + ", ".join(sorted(SHAPES)), file=sys.stderr)
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
