## 1. Compact

- [x] 1.1 Split each long requirement into one-behaviour requirements ≤ 500 characters. measured: `npx -y @fission-ai/openspec validate change-review --type spec --strict --no-interactive` — "Specification 'change-review' is valid".
- [x] 1.2 Move every scenario verbatim. measured: every old scenario block appears byte-for-byte exactly once in the new spec, by `python3 -c "import re,subprocess as s; o=s.run(['git','show','f7b3685:openspec/specs/change-review/spec.md'],capture_output=True,text=True).stdout; n=open('openspec/specs/change-review/spec.md').read(); b=re.findall(r'(?ms)^#### Scenario: .+?(?=^#### |^### |\Z)',o); print(len(b), sum(1 for x in b if n.count(x.rstrip())==1))"` — 48 48.
- [x] 1.3 Move the reasoning, measurements and original shape text to `rationale.md`, keyed by requirement heading.
- [x] 1.4 Prove the new scenario.
  manual: A named precedent is read for what it actually enforces: `.claude/plugins/cla/skills/review-change/references/checklist.md` states Shape 2 with this trigger, resolution and floor; no test pins checklist prose for the other shapes either.
- [x] 1.5 `pytest plugin-tests -q -n auto --dist loadfile` passes.
