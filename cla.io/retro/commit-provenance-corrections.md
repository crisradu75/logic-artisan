# commit-provenance.jsonl — corrections

`cla.io/retro/commit-provenance.jsonl` is append-only by convention: every row is
written by `hooks/log-commit-provenance.py` at the moment of a commit, and nothing
revisits it. This file records the exceptions, so a reader who finds a row whose
content does not match what the hook would have written at the time has somewhere
to find out why.

**There has been exactly one.** Everything below concerns it.

## 2026-09-18 — backfilling the rows the old trailer parser zeroed

### What was wrong

Before `ab69d5e` (2026-09-06T01:21) the hook read git's `%(trailers:…)`, which
recognises only the last contiguous `Key: value` block of a message. Attribution
lines are appended at the very end, so the moment a blank line separated a
commit's `Measured-by:` lines from them — the natural way to write a long message
— git's parser saw the attribution block and nothing else, and the row recorded
`measured_by_count: 0`.

`ab69d5e` changed the parser to scan the whole message. It did not touch the rows
already written, and nothing else would have.

### Why it was worth correcting rather than noting

`codify_aggregate.py` buckets a row on `measured_by_count > 0` and emits
`commit_provenance.measurement_rate`; `codify-retro/SKILL.md` reads a rate below
0.5 as "the rule is stated in CLAUDE.md and a consistency guard and is still not
reaching commits; that is a routing problem, not a reminder problem." This
ledger sat across that line, so the next retro would have diagnosed a routing
problem the commit messages themselves refute.

Measured over the 238 rows on `main` at `fa9e072`, before against after:

```bash
git show fa9e072:cla.io/retro/commit-provenance.jsonl > /tmp/before.jsonl
head -238 cla.io/retro/commit-provenance.jsonl        > /tmp/after.jsonl
python .claude/plugins/cla/skills/codify-retro/scripts/codify_aggregate.py --provenance /tmp/before.jsonl
python .claude/plugins/cla/skills/codify-retro/scripts/codify_aggregate.py --provenance /tmp/after.jsonl
```

| | commits | measured | unmeasured | no_trailer_field | measurement_rate |
|---|---|---|---|---|---|
| before | 238 | 89 | 101 | 48 | **0.47** |
| after | 238 | 111 | 79 | 48 | **0.58** |

Both numbers are pinned to named trees on purpose. A figure quoted against "the
ledger" goes stale with the next commit, because the hook appends a row for it.

### Which rows, and how they were chosen

By measurement, not by date: a row qualified when its recorded
`measured_by_count` was 0 and the CURRENT parser, replayed over that commit's
real `%B`, returned a non-zero count. Every sha in the file resolved; none was
skipped. 22 rows qualified, out of 238:

| bucket | rows |
|---|---|
| no `measured_by_count` field — held out of the rate's denominator by design | 48 |
| recorded non-zero and agrees with the current parser | 88 |
| recorded 0 and the message genuinely measures nothing | 79 |
| **recorded 0, current parser non-zero — corrected** | **22** |
| recorded non-zero but disagrees — see below | 1 |

The cutoff was used to check the set, not to define it, and it holds: all 22
predate the fix, the latest at 2026-09-05T23:58.

### Two rows deliberately left as they are

- **`74a8f17`** (2026-09-12, after the fix) carries a `Verification:` trailer
  instead of `Measured-by:`. The hook read that correctly; the commit message is
  what was non-standard. Backfilling it would invent a reading.
- **`a6b2862`** (2026-08-26, before the fix) recorded 6 where the whole-message
  scan finds 43. It is the same parser artefact, but the row is in the `measured`
  bucket either way, so correcting it moves no reported number. Left as a
  separate decision rather than folded into this one.

### How the values were produced, and the defect in the first attempt

The first pass stored `_measured_by()`'s raw return. **That is the extraction,
not the record.** `main()` shapes it three ways before a row reaches the file —
`_MAX_TRAILERS` (10), `_MAX_TRAILER_CHARS` (160), and a shedding loop against
`_MAX_LINE_BYTES` (2048) — and those caps predate every row corrected here, so
the first pass wrote rows no version of the hook could have produced. Two rows
broke a cap outright — the worst, `a55f4d9`, held 20 values in a 3484-byte line
(terminator included) where the writer emits 10 in 1657 — and 49 values across
the set were longer than 160 characters, the longest 397.

That matters beyond tidiness, but by less than the first version of this
record claimed, and the difference is worth stating precisely because the wrong
version was repeated. `_already_recorded_fh` seeks to the last 4096 bytes and
parses `lines[-1]` alone, justified by "a row is capped at `_MAX_LINE_BYTES`, so
4 KiB always contains a whole last line". What breaks that is a row past the
**4096-byte window**, at the tail: `json.loads` fails, the dedupe reads "not
recorded", and the next commit is appended twice. A row past the **2048-byte
cap** but under the window still parses.

So none of the bad rows could have broken the dedupe even at the tail — the worst
was 3484 bytes. The cap is the margin that keeps the window's assumption out of
reach, and violating it is a real defect in those terms; it is not the failure
itself.

The correction drives the writer instead of imitating it: `main()` is run once
per target sha against a scratch ledger, with `_git` substituted to answer for
that sha and `_head_moved_by_commit` forced true, and the `measured_by` list is
read back out of the row `main()` itself produced. `measured_by_count` is exact
and uncapped in the writer too, so it did not move.

`plugin-tests/tests/consistency/test_provenance_rows_fit_the_writer_caps.py`
now guards the file against exactly this: no row exceeds any of the three caps,
and the dedupe window still clears a maximal row. It deliberately does NOT claim
every row is one today's writer could emit. 161 of its rows use compact JSON
separators an earlier version of the hook wrote and this one does not — count
them with `grep -c '{"ts":"'` against `grep -c '{"ts": "'`, since the total moves
with every commit and a ratio would not keep. That is also why a corrected row
can measure 1635 bytes on disk while the writer's own serialisation of the same
record measures 1657.

The full suite was green while the oversize rows sat in the file, because every
test that knew about the caps drove the writer, and the writer was never the
thing that was wrong.

### What was verified

- 238 rows before and after; the sha sequence unchanged and in order; every line
  parses as one JSON object; the file still ends with a line terminator.
- Line by line against `git show fa9e072:…`: on the 22 changed rows the key order
  is unchanged and every field other than `measured_by`/`measured_by_count` is
  byte-identical; no other row differs.
- No row in the file exceeds any of the three caps. Byte counts here include
  the line terminator, normalised to the `\n` the writer budgets against, so
  they are comparable with `_MAX_LINE_BYTES`; a CRLF checkout adds one byte per
  row on disk.
- The one duplicate sha (`22c3d48`, recorded once per branch) predates this and
  was not introduced by it.

## The fleet was NOT corrected

Other repos on this machine carry the same ledger written by the same old parser.
Measured read-only, with the same replay, and **nothing outside this repo was
modified**:

| repo | rows | stale rows | rate recorded → replayed |
|---|---|---|---|
| claude-plugins | 79 | 42 | 0.0 → 0.53 |
| market-distiller-mcp | 21 | 7 | 0.0 → 0.33 |
| interoga-ro | 167 | 0 | 0.29 → 0.29 |
| agentic-air, future-champs, verto-ai | — | — | no ledger |

49 stale rows outside this repo. A fleet aggregate over the four ledgers as
recorded reads 137 measured of 458 scored, `measurement_rate` 0.30; with all 71
stale rows corrected it would read 208 of 458, 0.45 — still under the threshold,
but from a different cause. The two repos reading 0.0 have every row at zero,
which is what an older pinned plugin release looks like: correcting their history
would not stop them writing more stale rows until they take a release carrying
`ab69d5e`.
