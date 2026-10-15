# Tasks

## 1. The fixes

- [x] 1.1 Notes only for touched specs: `purpose_notes` takes the set of touched spec names built from the existing changed-path list, and with no base it notes every live spec and the output says so. Test a touched, an untouched, a delta-touched and a no-base case. Carry the comment `requirement: spec-proof / A checker notes a touched spec's Purpose without failing the run`.
- [x] 1.2 A hard-wrapped `**Serves:**` line draws no note; a Purpose with no blank line keeps the old reading. Test both. Same requirement comment as 1.1.
- [x] 1.3 An unpaired backtick cannot hide a sentence break in `count_sentences`; equal-length backtick runs still mask a span. Test both.
- [x] 1.4 In scenario mode a live spec with no scenario also names each scenario-less requirement; the generic line stays. Update the pinned generic-line test deliberately.
- [x] 1.5 The final print survives a cp1252 console and prints the same text on UTF-8. Test with a cp1252 stdout and a non-ASCII spec path.
- [x] 1.6 Reading a file at the base commit does not fail on a long path: a repo at a deep path with a long archive path reports no false `uncovered`; a path git confirms absent is new; any other git failure raises, as does a failed changed-path list. Test each; the first fails without the fix on Windows. measured: the deep-path proof against a clone of main under the scratchpad gave the old script 5 false PROBLEM lines and the new script 0.

## 2. Ship

- [x] 2.1 Remove exactly the fixed lines from `TODO.md`; leave the `manual:` format line and the others.
- [x] 2.2 Run `pytest plugin-tests -q -n auto --dist loadfile`, `openspec validate --specs --strict`, then `pytest plugin-tests -q` once each; the pass and skip counts match. measured: parallel 2442 passed, 8 skipped; serial 2442 passed, 8 skipped; validate 10 passed, 0 failed.
