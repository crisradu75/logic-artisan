"""Aggregate /codify-learnings run records into actionable metrics.

Reads the in-repo runs JSONL (<repo-root>/cla.io/retro/codify-runs.jsonl by
default — overridable with the CLAUDE_RETRO_DIR env var, or a full path via
--log <path>), considers the last --limit records (default 10), and emits a
single JSON object on stdout with deterministic aggregates. Conversation Claude
then reads this output and proposes specific improvements to the
codify-learnings loop itself.

The loop's whole point is to learn between runs; this aggregator is how it
reads back its own effectiveness. The two highest-value signals:

  - a lesson in `re_offenses` recurring across MANY runs → the artifact it was
    escalated to is too weak; bump it up the escalation ladder.
  - a lesson in `rejected_lessons` rejected ≥2 times → stop proposing it; retire
    it from failure-modes.md.

Input record schema (counts-only; see lib/log_run.py):

    {
      "ts": str,                      # date string, e.g. "2026-06-24"
      "scope": str,                   # plugin name or "repo-wide"
      "suggestions": {"proposed": int, "applied": int, "rejected": int},
      "memory":      {"proposed": int, "applied": int},
      "re_offenses": [ {"lesson": str, "failing_artifact": str,
                        "escalated_to": str} ],     # escalated_to in RUNGS below
      "rejected_lessons": [str, ...],               # lessons rejected THIS run
      "maintenance": {"failure_modes_bullets": int, "live_log_entries": int,
                      "trimmed": bool},
      "process_issue": bool,          # Step 3.5 self-check found a codify-process problem
      "output_chars": int             # optional — char count of the report this run
                                       # appended to lessons-learned.md
    }

Output schema (all counts over the analyzed window):

    {
      "runs_analyzed": int,
      "window": {"first_ts": str|None, "last_ts": str|None},
      "suggestions": {"proposed": int, "applied": int, "rejected": int,
                      "apply_rate": float},        # applied / proposed
      "memory": {"proposed": int, "applied": int, "apply_rate": float},
      "re_offenses": [{"lesson": str, "count": int}],   # count>1 = escalation not working
      "escalation_rungs": {<rung>: int},           # whitelisted RUNGS
      "escalation_rungs_unknown": {<str>: int},    # producer drift
      "rejected_lessons": [{"lesson": str, "count": int}],  # count>=2 = retire it
      "maintenance": {"failure_modes_bullets_latest": int|None,
                      "failure_modes_bullets_trend": [int, ...],
                      "live_log_entries_latest": int|None,
                      "trim_runs": int},
      "process_issue_runs": int,                   # runs where codify itself misfired
      "output_chars": {"latest": int|None, "trend": [int, ...], "mean": float},
        # char count of the appended lessons-learned.md report, over records that
        # carried a VALID `output_chars` (optional-additive). `trend` is built by
        # appending only valid values in chronological order, so `latest` is the
        # most recent VALID value — NOT necessarily the most recent record's
        # value: a malformed/missing `output_chars` on the newest run silently
        # falls back to an older valid one rather than reporting `None`. `None`
        # means no record in the window ever carried a valid value at all.
        # A verbosity proxy, NOT a full token-spend measure — it covers only the
        # printed report text. A climbing trend is a signal the report template
        # itself is ballooning.
      "coerced_fields": int,                        # present-but-malformed count
        # fields (e.g. a string/bool where an int was expected) dropped from the
        # sums; non-zero means the rates above are computed over a thinned sample.
      "skipped_records": int                       # malformed JSONL lines
    }

Bad records (non-dict, malformed JSON line, wrong field types) are skipped with
a stderr warning AND tallied — whole malformed lines in `skipped_records`,
present-but-malformed count fields in `coerced_fields` — so the consumer sees
the noise floor in stdout, not only stderr, per CLAUDE.md "never silently
swallow errors." Entry-level drift (a `re_offense` with a non-string `lesson`
or `escalated_to`, a `rejected_lessons`/`re_offenses` value that is a string
rather than a list, a non-string `ts`) is warned to stderr so it is never
swallowed silently.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path

# Escalation-ladder rungs, weakest → strongest (see codify-learnings/SKILL.md).
RUNGS = {"checklist", "memory", "claude_md", "skill_md", "hook", "script"}


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


def _default_log_path() -> Path:
    """This loop's ledger inside the dir the writer resolves.

    `_runs_dir` above is byte-identical to `lib/log_run.py`'s — the producer of
    the very file this reads — and a drift check compares the two so they
    cannot drift apart. If they ever did, this reader would look somewhere the
    writer never writes and report zero runs, which is indistinguishable from a
    cold start.
    """
    return _runs_dir() / "codify-runs.jsonl"


def _load_records(log_path: Path, limit: int) -> tuple[list[dict], int]:
    if not log_path.exists():
        # Distinguish a genuine cold start from a misconfigured path: name where
        # we looked so a wrong CLAUDE_RETRO_DIR / repo root is not mistaken for
        # "no runs yet". The retro still reports runs_analyzed:0 either way.
        src = "CLAUDE_RETRO_DIR" if os.environ.get("CLAUDE_RETRO_DIR", "").strip() \
            else "repo cla.io/retro"
        print(f"aggregate: no ledger at {log_path} (resolved via {src}); reporting 0 "
              f"runs. If you expected runs, check CLAUDE_RETRO_DIR / the repo root.",
              file=sys.stderr)
        return [], 0
    records: list[dict] = []
    skipped = 0
    with log_path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"aggregate: skipping malformed line {lineno}: {e}", file=sys.stderr)
                skipped += 1
                continue
            if not isinstance(rec, dict):
                print(f"aggregate: skipping non-object line {lineno}", file=sys.stderr)
                skipped += 1
                continue
            records.append(rec)
    sliced = records[-limit:] if limit > 0 else records
    return sliced, skipped


def _coerce_int(value: object, field: str, context: str) -> int | None:
    """Return value as int, or None with a stderr warning if it isn't numeric."""
    if isinstance(value, bool):  # bool is int in Python; reject explicitly
        print(f"aggregate: {context}: {field}={value!r} is bool, expected int", file=sys.stderr)
        return None
    if isinstance(value, int):
        return value
    print(f"aggregate: {context}: {field}={value!r} not int, skipping", file=sys.stderr)
    return None


def _sum_counts(rec: dict, key: str, fields: tuple[str, ...], ri: int,
                acc: Counter) -> int:
    """Add the record's counts into `acc`. Returns the number of present-but-
    malformed fields coerced away, so the caller can surface the noise floor in
    structured output (`coerced_fields`), not just on stderr."""
    block = rec.get(key)
    if block is None:
        return 0
    if not isinstance(block, dict):
        print(f"aggregate: record {ri}: `{key}` not an object, skipping", file=sys.stderr)
        return 0
    coerced = 0
    for f in fields:
        if f in block:
            n = _coerce_int(block[f], f, f"record {ri} {key}")
            if n is not None:
                acc[f] += n
            else:
                coerced += 1
    return coerced


def aggregate(records: list[dict]) -> dict:
    if not records:
        return {"runs_analyzed": 0}

    sugg: Counter = Counter()
    mem: Counter = Counter()
    re_offenses: Counter = Counter()
    escalation_rungs: Counter = Counter()
    escalation_unknown: Counter = Counter()
    rejected_lessons: Counter = Counter()
    fm_trend: list[int] = []
    live_log_latest: int | None = None
    fm_latest: int | None = None
    trim_runs = 0
    process_issue_runs = 0
    coerced_fields = 0
    # Container-shape drift. `coerced_fields` covers a present-but-wrong-typed COUNT
    # and `skipped_records` covers a whole unparseable line, but a list field arriving
    # as something else fell between them — warned about on stderr and tallied nowhere,
    # against this module's own docstring rule that a bad record is skipped with a
    # warning AND tallied.
    shape_drift: Counter[str] = Counter()
    shape_drift_records = 0
    output_chars_trend: list[int] = []

    for ri, rec in enumerate(records):
        # Fields whose container shape drifted in THIS record; a set, so one record
        # drifting twice still counts once toward `shape_drift_records`.
        drifted_fields: set[str] = set()
        coerced_fields += _sum_counts(rec, "suggestions",
                                      ("proposed", "applied", "rejected"), ri, sugg)
        coerced_fields += _sum_counts(rec, "memory", ("proposed", "applied"), ri, mem)

        re_offs = rec.get("re_offenses")
        if re_offs is not None and not isinstance(re_offs, list):
            print(f"aggregate: record {ri}: `re_offenses` is {type(re_offs).__name__}, "
                  f"expected list — skipping", file=sys.stderr)
            shape_drift["re_offenses"] += 1
            drifted_fields.add("re_offenses")
            re_offs = []
        for item in re_offs or []:
            if not isinstance(item, dict):
                print(f"aggregate: record {ri}: re_offense entry not a dict, skipping",
                      file=sys.stderr)
                continue
            lesson = item.get("lesson")
            if isinstance(lesson, str):
                re_offenses[lesson] += 1
            else:
                print(f"aggregate: record {ri}: re_offense `lesson`={lesson!r} not a "
                      f"string, skipping", file=sys.stderr)
            rung = item.get("escalated_to")
            if isinstance(rung, str):
                if rung in RUNGS:
                    escalation_rungs[rung] += 1
                else:
                    escalation_unknown[rung] += 1
                    print(f"aggregate: record {ri}: escalated_to={rung!r} not in "
                          f"{sorted(RUNGS)}", file=sys.stderr)
            else:
                print(f"aggregate: record {ri}: re_offense `escalated_to`={rung!r} not a "
                      f"string, skipping", file=sys.stderr)

        rej = rec.get("rejected_lessons")
        if rej is not None and not isinstance(rej, list):
            print(f"aggregate: record {ri}: `rejected_lessons` is {type(rej).__name__}, "
                  f"expected list — skipping", file=sys.stderr)
            shape_drift["rejected_lessons"] += 1
            drifted_fields.add("rejected_lessons")
            rej = []
        for lesson in rej or []:
            if isinstance(lesson, str):
                rejected_lessons[lesson] += 1
            else:
                print(f"aggregate: record {ri}: rejected_lessons entry {lesson!r} not a "
                      f"string, skipping", file=sys.stderr)

        maint = rec.get("maintenance")
        if isinstance(maint, dict):
            fmb_raw = maint.get("failure_modes_bullets")
            if fmb_raw is not None:
                fmb = _coerce_int(fmb_raw, "failure_modes_bullets", f"record {ri}")
                if fmb is not None:
                    fm_trend.append(fmb)
                    fm_latest = fmb
                else:
                    coerced_fields += 1
            lle_raw = maint.get("live_log_entries")
            if lle_raw is not None:
                lle_i = _coerce_int(lle_raw, "live_log_entries", f"record {ri}")
                if lle_i is not None:
                    live_log_latest = lle_i
                else:
                    coerced_fields += 1
            if maint.get("trimmed") is True:
                trim_runs += 1
        elif maint is not None:
            print(f"aggregate: record {ri}: `maintenance` is {type(maint).__name__}, "
                  f"expected object — skipping", file=sys.stderr)
            shape_drift["maintenance"] += 1
            drifted_fields.add("maintenance")
        if rec.get("process_issue") is True:
            process_issue_runs += 1

        if "output_chars" in rec:
            oc = _coerce_int(rec["output_chars"], "output_chars", f"record {ri}")
            if oc is not None:
                if oc < 0:
                    print(f"aggregate: record {ri}: output_chars={oc} is negative, "
                          f"clamped to 0", file=sys.stderr)
                    oc = 0
                output_chars_trend.append(oc)
            else:
                coerced_fields += 1

        if drifted_fields:
            shape_drift_records += 1

    proposed = sugg.get("proposed", 0)
    mem_proposed = mem.get("proposed", 0)
    timestamps: list[str] = []
    for ri, rec in enumerate(records):
        ts = rec.get("ts")
        if isinstance(ts, str):
            timestamps.append(ts)
        elif ts is not None:
            print(f"aggregate: record {ri}: `ts`={ts!r} not a string — excluded from window",
                  file=sys.stderr)
    return {
        "runs_analyzed": len(records),
        "window": {"first_ts": timestamps[0] if timestamps else None,
                   "last_ts":  timestamps[-1] if timestamps else None},
        "suggestions": {
            "proposed": proposed,
            "applied": sugg.get("applied", 0),
            "rejected": sugg.get("rejected", 0),
            "apply_rate": round(sugg.get("applied", 0) / proposed, 2) if proposed else 0.0,
        },
        "memory": {
            "proposed": mem_proposed,
            "applied": mem.get("applied", 0),
            "apply_rate": round(mem.get("applied", 0) / mem_proposed, 2) if mem_proposed else 0.0,
        },
        "re_offenses": [{"lesson": name, "count": c} for name, c in re_offenses.most_common()],
        "escalation_rungs": dict(escalation_rungs),
        "escalation_rungs_unknown": dict(escalation_unknown),
        "rejected_lessons":
            [{"lesson": name, "count": c} for name, c in rejected_lessons.most_common()],
        "maintenance": {
            "failure_modes_bullets_latest": fm_latest,
            "failure_modes_bullets_trend": fm_trend,
            "live_log_entries_latest": live_log_latest,
            "trim_runs": trim_runs,
        },
        "process_issue_runs": process_issue_runs,
        "output_chars": {
            "latest": output_chars_trend[-1] if output_chars_trend else None,
            "trend": output_chars_trend,
            "mean": round(statistics.mean(output_chars_trend), 1) if output_chars_trend else 0.0,
        },
        "coerced_fields": coerced_fields,
        # Which container fields drifted, and how many records drifted at all. Read
        # these BEFORE the metrics above: a non-zero `shape_drift_records` means some
        # metric ran on fewer records than `runs_analyzed` reports.
        "shape_drift_fields": dict(shape_drift),
        "shape_drift_records": shape_drift_records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate /codify-learnings run records.")
    parser.add_argument("--log", type=Path, nargs="+", default=None, metavar="PATH",
                        help="One or more runs JSONL paths (default: this project's log). "
                             "Several paths aggregate across repos — the repo where this "
                             "loop is designed usually holds the thinnest sample of them all.")
    parser.add_argument("--limit", type=int, default=10,
                        help="Analyze the last N records PER LEDGER (default 10, 0 = all).")
    args = parser.parse_args()

    try:
        log_paths = args.log or [_default_log_path()]
    except (ValueError, RuntimeError) as e:
        print(f"aggregate: {e}", file=sys.stderr)
        return 1

    records: list[dict] = []
    skipped = 0
    for p in log_paths:
        recs, sk = _load_records(p, args.limit)
        records.extend(recs)
        skipped += sk

    result = aggregate(records)
    result["skipped_records"] = skipped
    # `log_path` stays a bare string in the single-ledger case, which is every
    # caller that exists today. A multi-ledger run OMITS it rather than naming
    # one of several: a consumer still reading it then fails loudly instead of
    # attributing a fleet-wide aggregate to one repo.
    if len(log_paths) == 1:
        result["log_path"] = str(log_paths[0])
    result["log_paths"] = [str(p) for p in log_paths]
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
