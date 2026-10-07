## 1. Split

- [x] 1.1 Move each requirement block verbatim into its capability's `spec.md`, original order kept. measured: every old block appears byte-for-byte in exactly one new spec, by `python3 -c "import re,glob,subprocess as s; o=s.run(['git','show','ea17c5d:openspec/specs/cla-plugin/spec.md'],capture_output=True,text=True).stdout; b=re.split(r'(?m)^(?=### Requirement: )',o)[1:]; n=''.join(open(f).read() for f in glob.glob('openspec/specs/*/spec.md')); print(len(b), sum(1 for x in b if n.count(x.rstrip())==1))"` — 77 77.
- [x] 1.2 Give each capability a Purpose paragraph and delete `openspec/specs/cla-plugin/`.
- [x] 1.3 `openspec validate --specs` passes for all six. measured: 6 passed, 0 failed. `--strict` fails on the over-long requirements, as it did on `cla-plugin` before the split; #293 step 2 fixes that.

## 2. References

- [x] 2.1 Repoint every `scenario: cla-plugin / <heading>` marker. measured: `test_every_scenario_marker_names_a_live_scenario` in `plugin-tests/tests/consistency/test_scenario_proof_format.py` passes over all 16.
- [x] 2.2 Repoint five docstring pointers, `test_the_old_manual_format_is_gone` (now with a live-spec floor), and the four shipped files.
- [x] 2.3 `pytest plugin-tests -q -n auto --dist loadfile` passes.
