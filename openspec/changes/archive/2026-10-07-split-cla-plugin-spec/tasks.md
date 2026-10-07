## 1. Split

- [x] 1.1 Move each requirement block verbatim into its capability's `spec.md`, original order kept. measured: 77 requirements and 284 scenarios before and after, from `grep -c '^### Requirement:'` and `grep -c '^#### Scenario:'` over the old file and the six new ones.
- [x] 1.2 Give each capability a Purpose paragraph and delete `openspec/specs/cla-plugin/`.
- [x] 1.3 `openspec validate --specs` passes for all six. measured: 6 passed, 0 failed.

## 2. References

- [x] 2.1 Repoint every `scenario: cla-plugin / <heading>` marker. measured: 16 of 16 resolve to a scenario in their new capability (resolver script in the PR).
- [x] 2.2 Repoint docstring pointers, `test_the_old_manual_format_is_gone`, and the four shipped files.
- [x] 2.3 `pytest plugin-tests -q -n auto --dist loadfile` passes.
