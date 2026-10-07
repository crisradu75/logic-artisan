## 1. Compact

- [x] 1.1 Split each long requirement into one-behaviour requirements ≤ 500 characters. measured: `npx -y @fission-ai/openspec validate change-review --type spec --strict --no-interactive` — "Specification 'change-review' is valid".
- [x] 1.2 Move every scenario verbatim. measured: every old scenario block appears byte-for-byte exactly once in the new spec, by `python3 -c "import re,subprocess as s; o=s.run(['git','show','f7b3685:openspec/specs/change-review/spec.md'],capture_output=True,text=True).stdout; n=open('openspec/specs/change-review/spec.md').read(); b=re.findall(r'(?ms)^#### Scenario: .+?(?=^#### |^### |\Z)',o); print(len(b), sum(1 for x in b if n.count(x.rstrip())==1))"` — 48 48.
- [x] 1.3 Move the reasoning, measurements and original shape text to `rationale.md`, keyed by requirement heading.
- [x] 1.4 Prove the four new scenarios. No test pins the claim-shape prose in `checklist.md`.
  manual: A specified demo state is traced to the data that would produce it: `.claude/plugins/cla/skills/review-change/references/checklist.md:91` states Shape 1's resolution and its `producible:` / `NOT PRODUCIBLE:` record forms.
  manual: A named precedent is read for what it actually enforces: `checklist.md:98` states Shape 2's resolution; it fires step (c) on "does not satisfy or does not have", wider than the spec's "does not satisfy".
  manual: Precedent strictness states its floor and its reason: `checklist.md:98` and `checklist.md:136`.
  manual: A guarantee's class sets its floor: `checklist.md:100` and `checklist.md:137`.
- [x] 1.5 `pytest plugin-tests -q -n auto --dist loadfile` passes.
