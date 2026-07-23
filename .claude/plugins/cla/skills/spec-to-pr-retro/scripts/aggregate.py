"""Aggregate /spec-to-pr run records into actionable metrics.

Reads the in-repo runs JSONL (<repo-root>/cla.io/retro/spec-to-pr-runs.jsonl
by default — overridable with the CLAUDE_RETRO_DIR env var, or a full path via
--log <path>), considers the last --limit records (default 10), and emits a
single JSON object on stdout with deterministic aggregates. Conversation Claude
then reads this output and proposes specific improvements to spec-to-pr.

Schema of the output (all counts are over the analyzed window):

    {
      "runs_analyzed": int,
      "window": {"first_ts": str|None, "last_ts": str|None},
      "phase_outcomes": {<phase>: {"ok": n, "warn": n, "skip": n, "fail": n}},
      "warn_reasons": [{"reason": str, "count": int}, ...],   # top 10
      "cap_exhaustion": {                                      # rounds_used==rounds_cap, cap>1 only (cap==1 single-pass not counted)
        "review": {"hit": n, "total": n},
        "test":   {"hit": n, "total": n},
        "revise": {"hit": n, "total": n}
      },
      "round_counts": {                                        # mean rounds used
        "review": float, "test": float, "revise": float
      },
      "review_size_gate": {"small": n, "large": n},            # whitelisted
        # checklist size-gate decision per Review phase.
      "review_size_gate_unknown": {<unexpected-string>: n},    # producer drift
        # surfaced; whenever non-zero, the size-gate ratios above exclude these.
      "review_verdicts": {"READY": n, "FIX FIRST": n, "RETHINK": n},
        # whitelisted Review verdicts. A high READY rate with low Important
        # counts may indicate the checklist is weakening; a high RETHINK rate
        # may mean design conversations are starting too late.
      "review_verdicts_unknown": {<unexpected-string>: n},     # producer drift.
      "review_verified_claims": {"mean": float, "n": int},     # mean over `n`
        # records that emitted `verified_claims_count`. Disqualify the mean
        # when `n` is small relative to runs_analyzed (mostly nulls).
      "review_gate_pair_mismatches": int,                      # records where
        # size_gate=="small" had agents OR size_gate=="large" had none.
        # Non-zero = producer is emitting an inconsistent schema.
      "review_agents": {<agent-name>: {"dispatches": n}},       # large-mode
        # only; same shape and caveat as revise_agents below.
      "review_agents_unknown_types": {<type-name>: n},         # non-string
        # entries in `agents`, bucketed by type name.
      "revise_agents": {<agent-name>: {"dispatches": n}},       # how often each
        # agent was dispatched — trigger-frequency drift ("type-design-analyzer
        # fired 1/10 times — is the trigger too narrow, or too broad?"). Join
        # with `revise_findings` below for per-agent YIELD (dispatches vs found).
      "revise_agents_unknown_types": {<type-name>: n},
      "revise_findings": {<agent-name>: {"found": n, "phantom": n, "runs": n}},
        # Per-agent Revise finding yield, read from the pinned per-agent shape of
        # `routing.revise_findings_by_tier`. `found`/`phantom` summed (clamped
        # non-negative) over `runs` records that carried this agent; `found`/
        # `phantom` are trusted as producer-filtered to Critical+Important — the
        # aggregator does not re-derive severity. An agent dispatched on ~every
        # run (`revise_agents.<a>.dispatches ≈ runs_analyzed`) but with a low
        # `found`/`runs` — especially vs. the bug-hunters — is a trim-the-trigger
        # candidate. Covers only `revise_findings_records` of the window.
      "revise_findings_records": int,                          # records carrying
        # the pinned per-agent shape (the yield denominator).
      "revise_findings_legacy_records": int,                   # records whose
        # revise_findings_by_tier used a GENUINE legacy shape — every key drawn
        # from the model-tier (opus/sonnet/haiku) or severity
        # (critical/important/...) sets. Real pre-pin data, excluded from
        # `revise_findings`; non-zero just means older runs predate the schema
        # pin — not an error. (An empty {} is "no findings", counted in NO
        # bucket; drift is counted below, NOT here — so this stays a clean count
        # of true legacy records.)
      "revise_findings_malformed_records": int,                # records whose
        # revise_findings_by_tier is present but neither per-agent nor a known
        # legacy shape — a non-dict field, an unknown/misspelled key, or an
        # agent key with a non-dict value. Each also emits a stderr warning.
        # Non-zero means a CURRENT producer is emitting drift (not benign
        # history) — fix the producer, same as the other schema-integrity rows.
      "asks": [{"header": str, "choices": {<choice>: n}}],
      "version_bump_misses": int,
      "deferred_to_todo_total": int,
      "report_chars": {<phase>: {"mean": float, "n": int}},    # mean char count
        # of that phase's user-facing report, over `n` records that carried a
        # VALID `report_chars` (optional-additive — legacy runs that omit the
        # field AND current runs that emit a malformed value are both excluded
        # from `n`; check `report_chars_coerced` to tell the two apart). A
        # verbosity proxy, NOT a full token-spend measure — it covers only the
        # printed report text, not reasoning/tool output. Most phases run under
        # the one-sentence-per-transition rule (SKILL.md), so their mean should
        # sit near a small, near-constant floor; only Propose/Review/Handoff
        # carry substantial variable-length content. A climbing mean on a
        # low-narration phase (Implement/Ship/Archive) more likely signals that
        # rule being violated than genuine prose growth; a climbing mean on
        # Propose/Review/Handoff, or an outlier among ITS OWN siblings across
        # runs, is a trim-this-phase's-prose candidate.
      "report_chars_coerced": int,                             # `report_chars`
        # values present but wrong-typed (non-int, bool) this window — surfaced
        # here (not just stderr) so a piped consumer sees the noise floor; a
        # non-zero count is current-producer drift, not benign legacy history.
      "skipped_records": int                                   # malformed lines
    }

Bad records (missing required keys, non-dict, malformed JSON line, wrong
field types) are skipped with a stderr warning AND tallied in
`skipped_records` so the consumer can see the noise floor — per CLAUDE.md
"never silently swallow errors."
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


def _git_toplevel() -> Path | None:
    """Repo root via git (location-independent — works from the plugin, unlike a
    `.claude`-ancestor walk). None if git is unavailable."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return None
    return None


def _default_log_path() -> Path:
    """The in-repo, git-synced ledger: <repo-root>/cla.io/retro/spec-to-pr-runs.jsonl.

    Mirrors `spec-to-pr/scripts/log_run.py`'s resolver EXACTLY (must stay
    byte-identical or the producer and this consumer disagree on the path and
    runs vanish silently): repo root via `git rev-parse`, then `cla.io/retro`;
    CLAUDE_RETRO_DIR (absolute path) overrides the dir; raise rather than guess
    on a bad override or an unresolvable repo root.
    """
    override = os.environ.get("CLAUDE_RETRO_DIR")
    if override and override.strip():  # set-but-blank/whitespace → treat as unset
        path = Path(override)
        if not path.is_absolute():
            raise ValueError(f"CLAUDE_RETRO_DIR must be an absolute path, got {override!r}")
        return path / "spec-to-pr-runs.jsonl"
    root = _git_toplevel()
    if root is None:
        raise RuntimeError(
            "could not resolve the repo root via `git rev-parse --show-toplevel`; "
            "set CLAUDE_RETRO_DIR to an absolute path"
        )
    return root / "cla.io" / "retro" / "spec-to-pr-runs.jsonl"


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


VALID_SIZE_GATES = {"small", "large"}
VALID_VERDICTS = {"READY", "FIX FIRST", "RETHINK"}

# Revise agents whose per-agent finding YIELD the retro tracks (read from
# routing.revise_findings_by_tier). The finding record normalizes agent names
# with underscores (`code_reviewer`); the dispatch list uses hyphens
# (`code-reviewer`) — normalize to hyphens so the two join. Model-tier keys
# (opus/sonnet/haiku) and severity keys (critical/important/...) from the
# field's two LEGACY shapes are deliberately NOT in this set, so a legacy-shape
# record matches no agent and is counted as `revise_findings_legacy_records`
# rather than mis-tallied as an agent.
REVISE_AGENT_NAMES = {
    "code-reviewer", "silent-failure-hunter", "type-design-analyzer",
    "pr-test-analyzer", "comment-analyzer", "plugin-dev-skill-reviewer",
}

# Keys of the field's two LEGACY shapes: model-tier ({opus: {found, phantom}})
# and severity ({critical: n, ...}). A record whose keys are ALL drawn from
# this set (and none an agent) is a genuine pre-pin legacy record — counted,
# benignly, under `revise_findings_legacy_records`. A record that matches
# neither an agent NOR this set is producer DRIFT, not benign history, and is
# counted under `revise_findings_malformed_records` with a stderr warning — so
# a current-producer bug can't hide behind the "old runs" explanation. Keys are
# compared post-`_normalize_agent`, so the severity key `phantom_rejected` is
# stored here in its normalized `phantom-rejected` form (either spelling from a
# producer matches after normalization); none collides with an agent name.
LEGACY_TIER_KEYS = {
    "opus", "sonnet", "haiku",                                 # model-tier shape
    "critical", "important", "suggestion", "phantom-rejected",  # severity shape
}


def _normalize_agent(key: str) -> str:
    return key.replace("_", "-").replace(":", "-")


def _tally_agents(agents: list, target_counter: Counter, unknown_counter: Counter,
                  phase_name: str, record_index: int) -> None:
    """Dedupe agents within one dispatch (so `["X","X"]` credits X once) and
    warn on the duplicate. Non-string entries fall into unknown_counter so
    type drift surfaces in the output, not just stderr."""
    seen = set()
    duplicates = []
    for agent in agents:
        if not isinstance(agent, str):
            unknown_counter[type(agent).__name__] += 1
            print(f"aggregate: record {record_index}: {phase_name} `agents` contains "
                  f"non-string {agent!r}, counting as unknown", file=sys.stderr)
            continue
        if agent in seen:
            duplicates.append(agent)
            continue
        seen.add(agent)
        target_counter[agent] += 1
    if duplicates:
        print(f"aggregate: record {record_index}: {phase_name} `agents` has duplicates "
              f"{duplicates!r} — counted once each", file=sys.stderr)


def _coerce_int(value: object, field: str, context: str) -> int | None:
    """Return value as int, or None with a stderr warning if it isn't numeric."""
    if isinstance(value, bool):  # bool is int in Python; reject explicitly
        print(f"aggregate: {context}: {field}={value!r} is bool, expected int", file=sys.stderr)
        return None
    if isinstance(value, int):
        return value
    print(f"aggregate: {context}: {field}={value!r} not int, skipping", file=sys.stderr)
    return None


def aggregate(records: list[dict]) -> dict:
    if not records:
        return {"runs_analyzed": 0}

    phase_outcomes: dict[str, Counter] = defaultdict(Counter)
    warn_reasons: Counter = Counter()
    cap_hit = {"review": 0, "test": 0, "revise": 0}
    cap_total = {"review": 0, "test": 0, "revise": 0}
    rounds_used: dict[str, list[int]] = {"review": [], "test": [], "revise": []}
    revise_agent_dispatches: Counter = Counter()
    revise_agent_unknown: Counter = Counter()
    review_size_gate: Counter = Counter()
    review_size_gate_unknown: Counter = Counter()
    review_verdicts: Counter = Counter()
    review_verdicts_unknown: Counter = Counter()
    review_verified_claims: list[int] = []
    review_agent_dispatches: Counter = Counter()
    review_agent_unknown: Counter = Counter()
    review_gate_pair_mismatches = 0
    asks: dict[str, Counter] = defaultdict(Counter)
    version_bump_misses = 0
    deferred_total = 0
    report_chars: dict[str, list[int]] = defaultdict(list)
    report_chars_coerced = 0
    revise_findings: dict[str, dict[str, int]] = defaultdict(
        lambda: {"found": 0, "phantom": 0, "runs": 0})
    revise_findings_records = 0
    revise_findings_legacy_records = 0
    revise_findings_malformed_records = 0

    for ri, rec in enumerate(records):
        phases = rec.get("phases")
        if not isinstance(phases, list):
            print(f"aggregate: record {ri}: missing or non-list `phases`", file=sys.stderr)
            phases = []
        for phase in phases:
            if not isinstance(phase, dict):
                print(f"aggregate: record {ri}: non-dict phase entry, skipping", file=sys.stderr)
                continue
            name = phase.get("name", "?")
            status = phase.get("status", "?")
            phase_outcomes[name][status] += 1
            if status in ("warn", "fail") and phase.get("reason"):
                warn_reasons[phase["reason"]] += 1
            if "report_chars" in phase:
                rc = _coerce_int(phase["report_chars"], "report_chars", f"record {ri} phase {name}")
                if rc is not None:
                    if rc < 0:
                        print(f"aggregate: record {ri}: {name} `report_chars`={rc} is "
                              f"negative, clamped to 0", file=sys.stderr)
                        rc = 0
                    report_chars[name].append(rc)
                else:
                    report_chars_coerced += 1
            phase_key = name.lower() if isinstance(name, str) else "?"
            if phase_key in cap_total and "rounds_used" in phase:
                used = _coerce_int(phase["rounds_used"], "rounds_used", f"record {ri} phase {name}")
                cap = _coerce_int(phase.get("rounds_cap"), "rounds_cap", f"record {ri} phase {name}")
                if used is not None:
                    cap_total[phase_key] += 1
                    rounds_used[phase_key].append(used)
                    # cap==1 reached is trivially true for a single-pass phase (e.g. Review,
                    # default cap 1) — not meaningful exhaustion. Only count a hit when there was
                    # room to loop (cap>1), so Review never false-alarms the ≥30%-exhaustion rule.
                    if cap is not None and cap > 1 and used == cap:
                        cap_hit[phase_key] += 1
            if name == "Review":
                size_gate = phase.get("size_gate")
                if isinstance(size_gate, str):
                    if size_gate in VALID_SIZE_GATES:
                        review_size_gate[size_gate] += 1
                    else:
                        review_size_gate_unknown[size_gate] += 1
                        print(f"aggregate: record {ri}: Review `size_gate`={size_gate!r} "
                              f"not in {sorted(VALID_SIZE_GATES)}", file=sys.stderr)
                verdict = phase.get("verdict")
                if isinstance(verdict, str):
                    if verdict in VALID_VERDICTS:
                        review_verdicts[verdict] += 1
                    else:
                        review_verdicts_unknown[verdict] += 1
                        print(f"aggregate: record {ri}: Review `verdict`={verdict!r} "
                              f"not in {sorted(VALID_VERDICTS)}", file=sys.stderr)
                if "verified_claims_count" in phase:
                    vcc = _coerce_int(phase["verified_claims_count"],
                                      "verified_claims_count", f"record {ri} Review")
                    if vcc is not None:
                        review_verified_claims.append(vcc)
                agents = phase.get("agents", [])
                if not isinstance(agents, list):
                    print(f"aggregate: record {ri}: Review `agents` not list, skipping",
                          file=sys.stderr)
                    agents = []
                else:
                    _tally_agents(agents, review_agent_dispatches, review_agent_unknown,
                                  "Review", ri)
                # Pair-check: small mode should have no agents; large mode requires them.
                if size_gate in VALID_SIZE_GATES:
                    has_agents = bool([a for a in agents if isinstance(a, str)])
                    if (size_gate == "large") != has_agents:
                        review_gate_pair_mismatches += 1
                        print(f"aggregate: record {ri}: Review size_gate={size_gate!r} "
                              f"contradicts agents={agents!r}", file=sys.stderr)
            if name == "Revise":
                agents = phase.get("agents", [])
                if not isinstance(agents, list):
                    print(f"aggregate: record {ri}: Revise `agents` not list, skipping",
                          file=sys.stderr)
                else:
                    _tally_agents(agents, revise_agent_dispatches, revise_agent_unknown,
                                  "Revise", ri)
            if name == "Ship" and phase.get("version_bumped") is False:
                version_bump_misses += 1
        for ai, ask in enumerate(rec.get("asks", []) or []):
            if isinstance(ask, dict):
                asks[ask.get("header", "?")][ask.get("choice", "?")] += 1
            else:
                print(f"aggregate: record {ri}: ask {ai} not a dict, skipping", file=sys.stderr)
        deferred = _coerce_int(rec.get("deferred_to_todo", 0), "deferred_to_todo", f"record {ri}")
        deferred_total += deferred or 0

        # Per-agent Revise finding yield (routing.revise_findings_by_tier). The
        # field has THREE shapes across history — pinned per-agent
        # ({code_reviewer: {found, phantom}, ...}), legacy model-tier
        # ({opus: {found, phantom}, ...}), and legacy severity ({critical: n,
        # ...}). Only the per-agent shape feeds the yield metric; a genuine
        # legacy shape is counted (benignly) under `_legacy_records`. Anything
        # else — a non-dict field, an empty {}, an unknown/misspelled key, or an
        # agent key with a non-dict value — is NOT benign history: it is
        # producer DRIFT on a current record and must not hide behind the "old
        # runs" explanation, so it warns to stderr and lands in
        # `_malformed_records`. This mirrors the module's contract (docstring:
        # "wrong field types are skipped with a stderr warning") — the field is
        # never dropped silently. `_absent` (field not present at all) is the
        # one legitimate "no data" case: Revise logged no findings block, count
        # nothing.
        routing = rec.get("routing")
        if isinstance(routing, dict) and "revise_findings_by_tier" in routing:
            rfbt = routing["revise_findings_by_tier"]
            if not isinstance(rfbt, dict):
                print(f"aggregate: record {ri}: revise_findings_by_tier is "
                      f"{type(rfbt).__name__}, expected dict — counted malformed",
                      file=sys.stderr)
                revise_findings_malformed_records += 1
            elif not rfbt:
                # Empty {} = a Revise round that logged no findings. Neither
                # per-agent data nor a legacy shape — count it as nothing, so it
                # never inflates the legacy denominator the yield gate reads.
                pass
            else:
                seen: set[str] = set()
                matched = False
                had_drift = False  # an unrecognized key, or an agent key gone wrong
                for k, v in rfbt.items():
                    if not isinstance(k, str):
                        print(f"aggregate: record {ri}: revise_findings_by_tier "
                              f"key {k!r} not a string — ignored", file=sys.stderr)
                        had_drift = True
                        continue
                    agent = _normalize_agent(k)
                    if agent in REVISE_AGENT_NAMES:
                        if not isinstance(v, dict):
                            print(f"aggregate: record {ri}: agent {agent!r} value is "
                                  f"{type(v).__name__}, expected dict — ignored",
                                  file=sys.stderr)
                            had_drift = True
                            continue
                        if agent in seen:
                            print(f"aggregate: record {ri}: agent {agent!r} keyed twice "
                                  f"(spelling drift) — counted once", file=sys.stderr)
                            continue
                        seen.add(agent)
                        found = _coerce_int(v.get("found", 0), "found", f"record {ri} {agent}")
                        phantom = _coerce_int(v.get("phantom", 0), "phantom", f"record {ri} {agent}")
                        # Counts, never negative — clamp a stray sign so a bad
                        # value can't drag an agent's cumulative yield below its
                        # true total.
                        revise_findings[agent]["found"] += max(0, found or 0)
                        revise_findings[agent]["phantom"] += max(0, phantom or 0)
                        revise_findings[agent]["runs"] += 1
                        matched = True
                    elif agent not in LEGACY_TIER_KEYS:
                        had_drift = True  # not an agent, not a known legacy key
                if matched:
                    if had_drift:
                        print(f"aggregate: record {ri}: revise_findings_by_tier mixes "
                              f"known agents with unrecognized keys — stray keys ignored",
                              file=sys.stderr)
                    revise_findings_records += 1
                elif had_drift:
                    print(f"aggregate: record {ri}: revise_findings_by_tier matched no "
                          f"known agent and carried unrecognized keys — producer drift, "
                          f"counted malformed", file=sys.stderr)
                    revise_findings_malformed_records += 1
                else:
                    revise_findings_legacy_records += 1

    timestamps = [r.get("ts") for r in records if isinstance(r.get("ts"), str)]
    return {
        "runs_analyzed": len(records),
        "window": {"first_ts": timestamps[0] if timestamps else None,
                   "last_ts":  timestamps[-1] if timestamps else None},
        "phase_outcomes": {name: dict(counter) for name, counter in phase_outcomes.items()},
        "warn_reasons": [{"reason": r, "count": c} for r, c in warn_reasons.most_common(10)],
        "cap_exhaustion": {k: {"hit": cap_hit[k], "total": cap_total[k]} for k in cap_hit},
        "round_counts": {k: round(statistics.mean(v), 2) if v else 0.0
                         for k, v in rounds_used.items()},
        "review_size_gate": dict(review_size_gate),
        "review_size_gate_unknown": dict(review_size_gate_unknown),
        "review_verdicts": dict(review_verdicts),
        "review_verdicts_unknown": dict(review_verdicts_unknown),
        "review_verified_claims": {
            "mean": round(statistics.mean(review_verified_claims), 2) if review_verified_claims else 0.0,
            "n": len(review_verified_claims),
        },
        "review_gate_pair_mismatches": review_gate_pair_mismatches,
        "review_agents":
            {agent: {"dispatches": n} for agent, n in review_agent_dispatches.most_common()},
        "review_agents_unknown_types": dict(review_agent_unknown),
        "revise_agents":
            {agent: {"dispatches": n} for agent, n in revise_agent_dispatches.most_common()},
        "revise_agents_unknown_types": dict(revise_agent_unknown),
        "revise_findings":
            {agent: dict(counts) for agent, counts in sorted(revise_findings.items())},
        "revise_findings_records": revise_findings_records,
        "revise_findings_legacy_records": revise_findings_legacy_records,
        "revise_findings_malformed_records": revise_findings_malformed_records,
        "asks": [{"header": h, "choices": dict(c)} for h, c in asks.items()],
        "version_bump_misses": version_bump_misses,
        "deferred_to_todo_total": deferred_total,
        "report_chars": {name: {"mean": round(statistics.mean(v), 1), "n": len(v)}
                         for name, v in report_chars.items()},
        "report_chars_coerced": report_chars_coerced,
    }


def main() -> int:
    # Force UTF-8 stdout so non-ASCII content in logged strings (e.g. an em-dash in
    # an ask-choice label) prints correctly on Windows (default cp1252) instead of
    # mojibaking to U+FFFD when the output is captured. ensure_ascii=False below
    # emits real chars, so the stream must be UTF-8.
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=None,
                        help="Path to runs JSONL (default: project's log).")
    parser.add_argument("--limit", type=int, default=10,
                        help="Analyze the last N records (default 10, 0 = all).")
    args = parser.parse_args()

    try:
        log_path = args.log or _default_log_path()
    except (ValueError, RuntimeError) as e:
        print(f"aggregate: {e}", file=sys.stderr)
        return 1
    records, skipped = _load_records(log_path, args.limit)
    result = aggregate(records)
    result["skipped_records"] = skipped
    result["log_path"] = str(log_path)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
