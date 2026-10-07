# Scope asks — investigation-first and mid-flow scope split

The two design-decision asks `/cla:spec-to-pr` may raise. Neither is a "confirm to proceed" pause.

## Investigation-first changes

If a change's first task group is "reverse-engineer / investigate an unknown binary format" (or otherwise produces *facts the rest of the change depends on*), do that investigation in `/opsx:explore` mode and re-derive the proposal/design/tasks from confirmed facts **before** running `/cla:spec-to-pr`. An autonomous run over unconfirmed format assumptions forces mid-flight design rewrites: Implement discovers the model is wrong, pauses, and the design/spec/tasks have to be re-edited while the workflow is mid-stream.

**Ask-not-halt format.** If you detect this shape in existing-change mode, surface it to the user via `AskUserQuestion` with **three explicit paths** rather than a free-text halt-and-explain:

- **(a) Pause — validate first in `/opsx:explore`.** Stop `/cla:spec-to-pr`; user runs the investigation task in explore mode (or points at the required artifact); rerun `/cla:spec-to-pr` once the facts are settled.
- **(b) Proceed autonomously — trust current assumptions.** Treat the existing reverse-engineering as authoritative; defer the cross-validation task(s) to TODO.md; run Review→Handoff now. Accept the risk that a hidden assumption may force a follow-up PR.
- **(c) User has the artifact — point at it.** User provides the path/file the investigation needs (e.g. an alternate save, a sibling install path); run the investigation task in this session before Implement.

Do NOT free-text the question — the three-paths shape forces a clear choice and the deferral semantics are unambiguous.

## Mid-flow scope-split ask

- **Mid-flow scope-split ask** (Review authorized; same shape as the investigation-first detector). When Review audit finds the artifact is materially stale or its scope is materially inconsistent with the proposal — symptoms include missing-symbol claims against current code, wrong dict-keys in TypedDict definitions, Literal-value drift (e.g., a `Literal["fired","not_fired","unknown"]` shipped before suffixed statuses were added by a sibling change), a BREAKING semantic dependency on an un-shipped sibling, or task groups that span clearly separable concerns better shipped as multiple PRs — one `AskUserQuestion` with explicit-paths is allowed mid-flow to scope-down before Implement. This is NOT a "confirm to proceed" pause; it is a design-decision gate (same kind as investigation-first). The trigger is *content-based* (drift / inconsistency / separable-concerns), not size-based — a 30-task-group proposal that's internally coherent and matches current code does NOT need a scope-split ask. Phrase the ask as 3–4 explicit paths (tight scope / medium scope / full scope / halt) like the investigation-first detector. **Under a `/cla:multi-pr` caller** this ask fires only when the change cannot be implemented as written — case (f) of the closed blocker list in `${CLAUDE_PLUGIN_ROOT}/skills/multi-pr/SKILL.md`. Any other scope finding becomes a GitHub issue and the run continues.
