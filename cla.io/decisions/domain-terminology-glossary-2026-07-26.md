# Add a living domain-terminology discipline to CLA

**Topic (given):** Adapt idea #1 from a comparison against the peer project `mattpocock/skills`
— its `grill-with-docs` + `CONTEXT.md` pattern (a living domain-glossary doc, updated inline
during interview sessions, consumed by multiple skills as shared vocabulary) — into CLA.

**Grounding done before asking questions:** read `cla.io/`'s current structure (no glossary/ADR
concept exists today), `sync-context`'s "shared-fact tie-break rule" (a fact belongs in
`project-facts.md` only if it's a mechanical/repo-global fact — domain vocabulary doesn't
qualify), `project-review`'s existing two-source pattern (`project-facts.md` +
`project-context.md` overlay), and — critically — the peer repo `interoga-ro`'s *existing*
`docs/glossary.md` + `docs/persona/*.md`, which turned out to be a different artifact in kind
(dense external/regulatory reference knowledge, not internal code-naming disambiguation). That
finding reshaped the scope mid-session: this is a **new, narrow, `cla.io/`-housed companion
file**, not a replacement for or restructuring of an existing repo's own glossary docs.

## Questions asked and decisions

| # | Question | Chosen option | Rationale |
|---|---|---|---|
| 1 | Where does the new file live, and what's it called | `cla.io/terminology.md` — separate from any existing `docs/glossary.md` | Narrow internal/product naming disambiguation, not external reference knowledge; `cla.io/` is where CLA's own process-produced state already lives |
| 2 | Who owns the file's format/reconciliation logic | `sync-context` | Centralizes format/dedup/lazy-creation rules in one place, same role it already plays for `project-facts.md` |
| 3 | Who performs the actual writes | Consuming skills write inline, directly, in-session (not by invoking `sync-context` as a sub-skill) | Preserves the "capture as it happens, don't batch" mechanic that's the whole point of the feature |
| 4 | Hard or soft dependency for readers | Soft — one-line pointer, degrades gracefully if absent | Matches CLA's existing empty-stub-safe overlay convention everywhere else (e.g. `project-facts.md` fallback-to-overlay) |
| 5 | Initial implementation scope | Wire the soft pointer into all current consumers now (`sync-context`, `shape-decision`, `project-review`, `spec-to-pr`, `lite-pr`) | Full benefit from day one; cheap one-sentence-per-skill addition following the already-established `project-facts.md` pointer pattern |

## Explicitly deferred / out of scope

- Pairing this with a lightweight ADR discipline (`docs/adr/`, gated on hard-to-reverse +
  surprising + real-trade-off) — separate follow-up decision (idea #2 from the original
  comparison), not bundled here.
- Multi-context support (a `CONTEXT-MAP.md`-equivalent for monorepos with multiple domains) —
  single-file v1 only; revisit only if a consuming repo genuinely needs it.
- Any repo's own pre-existing external/regulatory glossary (e.g. `interoga-ro`'s
  `docs/glossary.md`) is untouched by this change — different artifact, different purpose.

## Why this matters / next step

CLA currently has no mechanism for keeping internal product/code vocabulary consistent across
a session — agents re-derive or drift on naming every run. This closes that gap the same way
`project-facts.md` closed the "agent re-derives build commands every run" gap, using the same
soft-dependency, fallback-safe philosophy already proven out elsewhere in the plugin.

Feeds into a `/cla:lite-pr` (or `/cla:spec-to-pr`) run to implement the five-skill change shaped
here: `sync-context` (owns format), `shape-decision` (creates/updates inline), `project-review`,
`spec-to-pr`, `lite-pr` (soft-read pointer).

---

# Idea #2 — ADR pairing: skipped

**Topic (given):** Pair the terminology discipline with a lightweight ADR practice
(`docs/adr/NNNN-*.md`), gated on hard-to-reverse + surprising + real-trade-off, adapted from the
peer repo.

**Outcome: skipped, not adopted.** Grounding this against `interoga-ro`'s own
`docs/architecture/tech-stack.md` and `scrapping.md` showed the repo already has a working,
more-mature alternative: `cla.io/decisions/` outputs get **manually promoted** to topic-organized
`docs/architecture/*.md` files once they become load-bearing (`tech-stack.md` literally states
"previously held in an ephemeral `cla.io/decisions/` file; this document supersedes it"), with a
`Status:` line, in-place correction notes, and cross-references to the OpenSpec change that
implements each decision. That pattern fits better than one-file-per-decision ADRs would (it keeps
related decisions like the 7 platform-stack picks in one browsable table instead of fragmenting
them across 7 files).

A follow-up idea surfaced during grounding — **formalize the `cla.io/decisions/` →
`docs/architecture/*.md` promotion step itself**, since today it's done by hand with no CLA skill
support — was offered and declined. Not pursued further this session; revisit only if the manual
promotion step becomes a recurring friction point worth automating.

---

# Idea #3 — a `/diagnose` skill: postponed

**Topic (given):** Add a disciplined bug-diagnosis loop (reproduce → minimize → hypothesise →
instrument → fix → regression-test), adapted from the peer repo's `diagnose` skill.

**Outcome: postponed, not skipped.** Grounding confirmed a real gap (unlike idea #2) — `diagnose`
exists in CLA today only as a bare, undefined verb inside `lite-pr`/`spec-to-pr`'s Test-phase
failure handling, and `feedback` explicitly refuses the job with no real downstream hand-off. This
one is worth doing, just not right now. Shaping was interrupted mid-Q1 (standalone skill vs.
escalation vs. both). Full writeup, the peer repo's 6-phase mechanics, and the open questions to
pick back up are in `TODO.md` at the repo root (new file, added this session) rather than
repeated here.

---

# Idea #4 — Agent Brief durability discipline for `tasks.md`: postponed

**Topic (given):** Adopt the peer repo's `triage/AGENT-BRIEF.md` durability discipline (behavioral
not procedural, no file-path/line-number references, testable acceptance criteria, explicit
out-of-scope) for how CLA's `multi-spec`/`spec-to-pr` guide `tasks.md` authoring.

**Outcome: postponed, not skipped.** Grounding confirmed a real, already-structural gap — not
speculative — and a real constraint on where the fix can live (the actual `tasks.md`-writing tool,
`openspec-propose`, is a vendored skill hard-excluded from CLA edits; the fix has to be CLA's own
orchestration around it, not the vendored skill itself). Shaping was interrupted mid-Q1 (enforce
at authoring-time / review-time / both). Full writeup, the confirmed staleness-risk evidence from
`multi-spec`'s own SKILL.md, and the open questions to pick back up are in `TODO.md` at the repo
root rather than repeated here.

## Session summary

Of the 4 ideas from the original `mattpocock/skills` comparison: **#1 adopted and shaped in full**
(5 questions answered, ready for `/cla:lite-pr`); **#2 skipped** (this repo's own
`docs/architecture/*.md` pattern already does the job, better-fitted than the peer repo's ADRs);
**#3 and #4 postponed** to `TODO.md`, each a confirmed real gap worth doing later, with grounding
and open questions preserved so neither needs to be re-derived from scratch.
