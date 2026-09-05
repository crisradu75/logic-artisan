"""Aggregate /codify-learnings run records into actionable metrics.

Reads the in-repo runs JSONL (<repo-root>/cla.io/retro/codify-runs.jsonl by
default — overridable with the CLAUDE_RETRO_DIR env var, or one or more
full paths via --log <path> [<path> ...]), considers the last --limit records PER
LEDGER (default 10), and emits a
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
      "effectiveness": {"prevented": int, "re_offended": int,
                        "not_exercised": int},   # optional — Step 2.5's tally
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
      "effectiveness": {"prevented": int, "re_offended": int,
                        "not_exercised": int, "prevention_rate": float|None,
                        "records": int},
        # THE OUTCOME METRIC. Every other block here counts what the loop WROTE;
        # this one counts whether what it wrote HELD. `prevention_rate` is
        # prevented / (prevented + re_offended) — the share of artifacts that were
        # actually exercised and did their job.
        #
        # `not_exercised` is deliberately OUT of the denominator. An artifact the
        # session never came near is evidence of nothing, and counting it would let
        # the rate climb by growing the checklist — rewarding exactly the bloat
        # Step 2.6 exists to fight.
        #
        # `None`, not 0.0, when nothing was exercised, and this diverges from
        # `apply_rate` above ON PURPOSE — do not "fix" it to match. Low means bad
        # for this rate, so a 0.0 placeholder is an empty sample wearing a failing
        # grade, and the SKILL.md heuristic gating on `< 0.5` would fire on a window
        # that measured nothing at all.
        #
        # `records` is how many records carried a usable `effectiveness` block, so a
        # rate drawn from 2 of 30 runs cannot be read as one drawn from 30.
        #
        # POOLED IN FLEET MODE, unlike the per-repo fields below, and here is the
        # argument rather than an assertion: these count EVENTS (a rule was
        # exercised and held, or failed), not the size of one repo's files, so
        # adding them across repos is meaningful where adding file sizes is not.
        # The weighting is real and must be read with it — a repo contributing 21
        # runs dominates one contributing 5. So this answers "across the fleet's
        # sessions", NEVER "in a typical repo". For the latter, run one ledger.
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
      "shape_drift_fields": {<field>: int},          # container-shape drift by
        # field: a value whose TYPE cost the metrics a field they read. Read this
        # BEFORE any metric below — non-zero means some metric ran on fewer
        # records than `runs_analyzed` reports.
      "shape_drift_records": int,                    # records with any such drift
      "log_path": str,                               # single-ledger runs ONLY —
        # omitted when several ledgers were read, so a fleet result cannot be
        # attributed to one repo. Keys off what was READ, after dedupe.
      "per_repo_fields_suppressed": true,           # fleet runs only —
        # the per-repo maintenance/output_chars fields above describe ONE
        # repo's files and are nulled rather than pooled.
      "log_paths": [str, ...],                       # every ledger read (deduped)
      "ledgers": [{"path": str, "found": bool, "records": int, "skipped": int}],
        # per-ledger provenance. A path that did not resolve shows found:false
        # with records:0, so a fleet aggregate drawn from four repos cannot be
        # mistaken for one drawn from five.
      "skipped_records": int,                      # malformed JSONL lines
      "commit_provenance": {                       # ONLY when --provenance is given
        "commits": int, "measured": int, "unmeasured": int,
        "no_trailer_field": int, "measurement_rate": float|None,
        "by_skill": {<skill or "none">: int},
        "skipped_records": int, "ledgers": [...],
      },
        # Adoption of the `Measured-by:` rule, counted by a hook rather than
        # self-reported. Read `no_trailer_field` beside the rate: those rows
        # predate the field and are OUT of its denominator, because charging the
        # rule for commits made before it was recorded would make the rate fall
        # the further back you look. See `aggregate_provenance` for why this
        # lives in the codify loop.
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

# Step 2.5's three buckets, in the order the skill classifies them. Named once so
# the probe and the sum cannot come to disagree about which fields make a block
# usable — they answered that question separately, and a field added to one and
# not the other would go uncounted while the rate still printed.
_EFFECTIVENESS_FIELDS = ("prevented", "re_offended", "not_exercised")


def _usable_int(value: object) -> bool:
    """Whether `_coerce_int` would accept this value, WITHOUT emitting its warning.

    Deliberately not a call to `_coerce_int`: the probe runs before the sum over the
    same block, so reusing the coercing form would warn twice about one bad value.
    `_coerce_int` is pinned across both aggregators by `check_script_drift.py` and
    cannot grow a quiet mode, so the acceptance rule is mirrored here instead —
    `bool` rejected explicitly, because in Python it is an `int`.
    """
    return isinstance(value, int) and not isinstance(value, bool)


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


def _load_records(log_path: Path, limit: int,
                  explicit: bool = False) -> tuple[list[dict], int]:
    if not log_path.exists():
        # Distinguish a genuine cold start from a misconfigured path: name where
        # we looked so a wrong CLAUDE_RETRO_DIR / repo root is not mistaken for
        # "no runs yet". The retro still reports runs_analyzed:0 either way.
        # Name the provenance correctly. An explicit `--log` path that does not
        # exist is a typo in the argument, not a misconfigured repo root, and
        # telling the caller to check CLAUDE_RETRO_DIR sends them to the wrong file.
        if explicit:
            print(f"aggregate: no ledger at {log_path} (given explicitly via --log); "
                  f"contributing 0 runs. Check the path.", file=sys.stderr)
        else:
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
                acc: Counter, drifted: set[str]) -> int:
    """Add the record's counts into `acc`. Returns the number of present-but-
    malformed fields coerced away, so the caller can surface the noise floor in
    structured output (`coerced_fields`), not just on stderr."""
    block = rec.get(key)
    if block is None:
        return 0
    if not isinstance(block, dict):
        print(f"aggregate: record {ri}: `{key}` is {type(block).__name__}, expected "
              f"object — skipping", file=sys.stderr)
        # Container-shape drift, not a coerced count: it drops the whole block,
        # so `apply_rate` loses both numerator and denominator while
        # `runs_analyzed` still counts the record as read.
        drifted.add(key)
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



def _window(timestamps: list[str]) -> dict:
    """The analyzed window's ends, chronologically rather than as collected.

    Records arrive concatenated in `--log` argument order, so taking the first and
    last of that concatenation produced a window that ENDED BEFORE IT STARTED
    whenever a newer ledger was listed first — printed with exit 0.

    The sort is lexical. These are ISO-8601 strings and the corpus mixes `Z` with
    explicit offsets, so two instants on the same day in different zones can order
    wrongly; that is bounded inside a day, where argument order was unbounded.

    Pinned across both aggregators by `check_script_drift.py`, and the reason it is
    pinned is this function's own history: the sort landed in one sibling, the
    other kept inverting, and nothing caught it but a reviewer.
    """
    if not timestamps:
        return {"first_ts": None, "last_ts": None}
    ordered = sorted(timestamps)
    return {"first_ts": ordered[0], "last_ts": ordered[-1]}


def _load_ledgers(log_paths: list[Path], limit: int,
                  explicit: bool) -> tuple[list[dict], int, list[dict]]:
    """Read every named ledger into one record list, with per-ledger provenance.

    Deduplicates by resolved path: a fleet invocation is assembled by a model from
    a repo list, often via a glob or brace expansion, so the same ledger arriving
    twice is a real shape — and it silently doubled every count.

    Returns the provenance rows as well as the records, because the whole reason
    to read several ledgers is sample size: a mistyped path contributed nothing
    while still being echoed back, so a four-repo aggregate could claim five on the
    one stream nothing reads after the fact.

    Pinned across both aggregators by `check_script_drift.py`.
    """
    records: list[dict] = []
    skipped = 0
    ledgers: list[dict] = []
    seen: set[Path] = set()
    for p in log_paths:
        try:
            key = p.resolve()
        except OSError:
            key = p
        if key in seen:
            print(f"aggregate: {p} given more than once — ignoring the duplicate",
                  file=sys.stderr)
            continue
        seen.add(key)
        existed = p.exists()
        recs, sk = _load_records(p, limit, explicit=explicit)
        records.extend(recs)
        skipped += sk
        ledgers.append({"path": str(p), "found": existed,
                        "records": len(recs), "skipped": sk})
    return records, skipped, ledgers

def aggregate_provenance(records: list[dict]) -> dict:
    """Adoption numbers for the `Measured-by:` rule, from the commit-provenance hook.

    Why this reader exists at all. `hooks/log-commit-provenance.py` writes one row
    per commit and its own comment says why: "a rule stated in a skill has no
    adoption number until something counts it ... whether the rule is being
    followed is answerable only from a ledger", and it "leaves adjudication to the
    retro". No retro read it. The rows accumulated at zero cost in attention and
    answered nothing, which by this repo's rule makes a ledger exhaust.

    It belongs to THIS loop rather than a new one because the question it answers
    is the effectiveness question: the measurement-naming rule is one of the
    lessons the loop escalated (to CLAUDE.md and a consistency guard), and whether
    commits honour it is exactly "did that lesson hold?". The difference from the
    `effectiveness` block above is what makes it worth having — that one is a model
    grading its own session, this one is a hook counting commits.

    `no_trailer_field` is kept OUT of the rate's denominator and reported beside
    it. Those rows predate the field, and folding them into `unmeasured` would
    charge the rule for commits made before it was recorded — a rate that falls
    the further back you look, purely from schema history.
    """
    measured = unmeasured = no_field = 0
    by_skill: Counter = Counter()
    for ri, rec in enumerate(records):
        raw = rec.get("measured_by_count")
        if raw is None:
            no_field += 1
        else:
            n = _coerce_int(raw, "measured_by_count", f"provenance record {ri}")
            if n is None:
                no_field += 1
            elif n > 0:
                measured += 1
            else:
                unmeasured += 1
        skill = rec.get("skill")
        by_skill[skill if isinstance(skill, str) else "none"] += 1
    scored = measured + unmeasured
    return {
        "commits": len(records),
        "measured": measured,
        "unmeasured": unmeasured,
        "no_trailer_field": no_field,
        # None, not 0.0, on an empty sample — same reason as `prevention_rate`.
        "measurement_rate": round(measured / scored, 2) if scored else None,
        "by_skill": dict(by_skill.most_common()),
    }


def aggregate(records: list[dict]) -> dict:
    if not records:
        # Emitted here too: omitting them made a consumer's
        # `.get("shape_drift_records", 0)` read a clean zero on a missing or empty
        # ledger — an absence wearing a measurement's clothes.
        return {"runs_analyzed": 0, "shape_drift_fields": {}, "shape_drift_records": 0}

    sugg: Counter = Counter()
    mem: Counter = Counter()
    eff: Counter = Counter()
    # How many records carried a usable `effectiveness` block. Without it a rate
    # drawn from 2 records reads identically to one drawn from 30.
    eff_records = 0
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
                                      ("proposed", "applied", "rejected"), ri, sugg,
                                      drifted_fields)
        coerced_fields += _sum_counts(rec, "memory", ("proposed", "applied"), ri, mem,
                                      drifted_fields)
        # Probed BEFORE summing, and with `_usable_int` rather than `_coerce_int`:
        # `_sum_counts` reports how many fields COERCED AWAY, not whether the block
        # contributed anything, and calling the coercing form here would warn about
        # the same bad value twice. A record whose every count is malformed must not
        # inflate `records` into claiming a sample it did not contribute to.
        eff_block = rec.get("effectiveness")
        if isinstance(eff_block, dict) and any(
            _usable_int(eff_block.get(f)) for f in _EFFECTIVENESS_FIELDS
        ):
            eff_records += 1
        coerced_fields += _sum_counts(rec, "effectiveness", _EFFECTIVENESS_FIELDS,
                                      ri, eff, drifted_fields)

        re_offs = rec.get("re_offenses")
        if re_offs is not None and not isinstance(re_offs, list):
            print(f"aggregate: record {ri}: `re_offenses` is {type(re_offs).__name__}, "
                  f"expected list — skipping", file=sys.stderr)
            drifted_fields.add("re_offenses")
            re_offs = []
        for item in re_offs or []:
            if not isinstance(item, dict):
                print(f"aggregate: record {ri}: re_offense entry not a dict, skipping",
                      file=sys.stderr)
                drifted_fields.add("re_offenses")
                continue
            lesson = item.get("lesson")
            if isinstance(lesson, str):
                re_offenses[lesson] += 1
            else:
                print(f"aggregate: record {ri}: re_offense `lesson`={lesson!r} not a "
                      f"string, skipping", file=sys.stderr)
                drifted_fields.add("re_offenses")
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
                drifted_fields.add("re_offenses")

        rej = rec.get("rejected_lessons")
        if rej is not None and not isinstance(rej, list):
            print(f"aggregate: record {ri}: `rejected_lessons` is {type(rej).__name__}, "
                  f"expected list — skipping", file=sys.stderr)
            drifted_fields.add("rejected_lessons")
            rej = []
        for lesson in rej or []:
            if isinstance(lesson, str):
                rejected_lessons[lesson] += 1
            else:
                print(f"aggregate: record {ri}: rejected_lessons entry {lesson!r} not a "
                      f"string, skipping", file=sys.stderr)
                drifted_fields.add("rejected_lessons")

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

        # `ts` is validated HERE, inside the record loop, so it joins the same
        # per-record set as every other field. Tallying it in the later timestamps
        # loop instead double-counted a record that drifted in both places, and
        # `shape_drift_records` could then exceed `runs_analyzed` — a per-record
        # counter larger than the record count, which makes the field unreadable
        # against the very sentence both SKILL.md files use to explain it.
        ts_value = rec.get("ts")
        if ts_value is not None and not isinstance(ts_value, str):
            print(f"aggregate: record {ri}: `ts`={ts_value!r} not a string — excluded "
                  f"from window", file=sys.stderr)
            drifted_fields.add("ts")

        if drifted_fields:
            shape_drift_records += 1
            # Derived from the per-record set rather than incremented at each call
            # site, so the per-field tally and the per-record count cannot disagree
            # and a field drifting twice in one record counts once.
            for field in drifted_fields:
                shape_drift[field] += 1

    proposed = sugg.get("proposed", 0)
    mem_proposed = mem.get("proposed", 0)
    # Exercised = held + failed. `not_exercised` stays out: a rule the session never
    # came near says nothing about whether the rule works, and letting it into the
    # denominator would raise the rate for merely owning a longer checklist.
    prevented = eff.get("prevented", 0)
    re_offended = eff.get("re_offended", 0)
    exercised = prevented + re_offended
    timestamps: list[str] = []
    for ri, rec in enumerate(records):
        ts = rec.get("ts")
        if isinstance(ts, str):
            timestamps.append(ts)
        # No warning or tally here — a non-string `ts` is reported by the record
        # loop above, which is where the per-record drift set lives. This loop only
        # collects, so it cannot double-count what that one already counted.
    return {
        "runs_analyzed": len(records),
        "window": _window(timestamps),
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
        "effectiveness": {
            "prevented": prevented,
            "re_offended": re_offended,
            "not_exercised": eff.get("not_exercised", 0),
            # None, not 0.0, on an empty sample — see the output schema above. Low
            # means bad here, so 0.0 would report "every rule failed" for a window
            # in which nothing was measured at all.
            "prevention_rate": round(prevented / exercised, 2) if exercised else None,
            "records": eff_records,
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
                             "Several paths aggregate across repos, which matters "
                             "because any single repo's sample is thin enough to mislead.")
    parser.add_argument("--limit", type=int, default=10,
                        help="Analyze the last N records PER LEDGER (default 10, 0 = all).")
    parser.add_argument("--provenance", type=Path, nargs="+", default=None, metavar="PATH",
                        help="One or more commit-provenance JSONL paths. Adds a "
                             "`commit_provenance` block reporting how many commits "
                             "carried a `Measured-by:` trailer — the adoption number "
                             "for that rule, which nothing else counts. Independent of "
                             "--log and never sliced by --limit: adoption is a property "
                             "of the whole history, not of the last N commits.")
    args = parser.parse_args()

    try:
        log_paths = args.log or [_default_log_path()]
    except (ValueError, RuntimeError) as e:
        print(f"aggregate: {e}", file=sys.stderr)
        return 1

    records, skipped, ledgers = _load_ledgers(log_paths, args.limit,
                                              explicit=args.log is not None)

    result = aggregate(records)
    # `"maintenance" in result` is load-bearing, not defensive noise. `aggregate()`
    # returns a THREE-KEY skeleton when no record survived, and this block consumed
    # a key that skeleton does not carry — so a fleet run whose every path was
    # mistyped crashed with KeyError instead of reporting the empty result. That is
    # exactly the case the `ledgers` array was added to make visible, and the same
    # change extended the empty return with the drift keys while missing this one.
    if len(ledgers) > 1 and "maintenance" in result:
        # These describe ONE repo's files — the size of its failure-modes
        # checklist, the length of its live log, the size of its last report.
        # Concatenated across repos, `_latest` becomes "whichever ledger was
        # listed last" and `_trend` interleaves unrelated repos into one
        # sequence. `codify-retro/SKILL.md` gates directly on these, so a
        # fleet run would otherwise produce a confident checklist-bloat verdict
        # from an arbitrary repo's numbers. Suppressed rather than reordered:
        # no ordering makes one series out of several repos' file sizes.
        result["maintenance"]["failure_modes_bullets_latest"] = None
        result["maintenance"]["failure_modes_bullets_trend"] = []
        result["maintenance"]["live_log_entries_latest"] = None
        result["output_chars"] = {"latest": None, "trend": [], "mean": 0.0}
        # `effectiveness` is deliberately NOT suppressed here, and this note exists so
        # nobody adds it for symmetry. The fields above measure ONE repo's files, which
        # do not add up across repos. `effectiveness` counts events — a rule was
        # exercised and held, or failed — and events do add up. What a reader must
        # carry instead is the weighting: the pooled rate is dominated by whichever
        # repo contributed the most runs, so it describes the fleet's sessions and not
        # a typical repo.
        result["per_repo_fields_suppressed"] = True
    result["skipped_records"] = skipped
    # `log_path` stays a bare string in the single-ledger case, which is every
    # caller that exists today. A multi-ledger run OMITS it rather than naming
    # one of several: a consumer still reading it then fails loudly instead of
    # attributing a fleet-wide aggregate to one repo.
    # Branch on what was actually READ, not on what was asked for. These two
    # disagree after a dedupe: `--log a a` left `log_paths` at length 2 and omitted
    # `log_path` — the documented "this is a fleet result" signal — for a run that
    # read exactly one ledger, while `log_paths` in the output correctly showed one.
    if len(ledgers) == 1:
        result["log_path"] = ledgers[0]["path"]
    result["log_paths"] = [entry["path"] for entry in ledgers]
    result["ledgers"] = ledgers

    if args.provenance:
        # limit=0 deliberately: `--limit` slices run ledgers, and adoption of a
        # commit-message rule is a property of the whole history. Slicing it to the
        # last N would report a rate for a window the caller chose for a different
        # ledger entirely.
        prov_records, prov_skipped, prov_ledgers = _load_ledgers(
            args.provenance, 0, explicit=True)
        block = aggregate_provenance(prov_records)
        block["skipped_records"] = prov_skipped
        block["ledgers"] = prov_ledgers
        result["commit_provenance"] = block
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
