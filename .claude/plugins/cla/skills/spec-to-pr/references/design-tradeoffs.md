

### History behind rules SKILL.md states briefly

- `<inherits>`: GitHub issues #98, #100, #102 — one chain in which three consecutive changes dropped the same obligation, each one internally consistent and silently wrong.
- Implement post-check: Issue #111 records three ticked tasks in one chain that asserted things that were false — including a mutation test that could not have failed anything — with every mechanical check passing all three.
- Test source-affecting list: `.py` is called out because it was once missing, and in a Python repo a real source change then did not register as source-affecting at all — the run reported a clean docs-only skip having gated nothing. A closed list reproduces that defect for every language it omits.
- Autonomy gate: a phase-boundary confirmation prompt is a regression against the documented contract — past sessions have lost ~5 minutes per pause to model-side gating that the SKILL.md never authorized.
- Handoff's three named subsections: measured — a fix round returned four items under one "not applied" heading — three legitimate holds and one genuinely cheap fix nobody had done.
- Review's multi-spec skip lives in spec-to-pr, not the checklist, because it decides which checklist parts run, not how any check behaves.
