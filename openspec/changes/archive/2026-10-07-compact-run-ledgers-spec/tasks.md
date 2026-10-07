## 1. Compact

- [x] 1.1 Split each requirement into one-behaviour requirements ≤ 500 characters. measured: `npx -y @fission-ai/openspec validate run-ledgers --type spec --strict --no-interactive` — "Specification 'run-ledgers' is valid".
- [x] 1.2 Move every scenario verbatim. measured: every old scenario block appears byte-for-byte exactly once in the new spec, by `python3 -c "import re,subprocess as s; o=s.run(['git','show','68f70ad:openspec/specs/run-ledgers/spec.md'],capture_output=True,text=True).stdout; n=open('openspec/specs/run-ledgers/spec.md').read(); b=re.findall(r'(?ms)^#### Scenario: .+?(?=^#### |^### |\Z)',o); print(len(b), sum(1 for x in b if n.count(x.rstrip())==1))"` — 13 13.
- [x] 1.3 Move the reasoning and measurements to `rationale.md`, keyed by requirement heading.
- [x] 1.4 `pytest plugin-tests -q -n auto --dist loadfile` passes.
