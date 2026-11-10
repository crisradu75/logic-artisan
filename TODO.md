# TODO

Leftover review suggestions (PR #481, orchestration-economy rule 14).

- Rule 14 says "the verify run". Reuse rule 10's wording ("verifies the base branch once") or define the term.
- Rule 14 does not say whether "read-only" allows scratch writes. Rules 7 and 8 make that matter.
- Rule 14 says "shares the test database". Add "unless it has its own copy (rule 9)".

Leftover review suggestions (PR #482, pre-push URL match).

- pre-push URL match: when two remotes share one URL, the first by name wins. Add a comment or a test saying so.

Leftover review suggestions (PR #486, check_spec_proof fences and requirement names).

- `_FENCE_LINE` accepts any indentation, so a fence indented 4 or more spaces counts as a fence where CommonMark treats it as code; no test pins indented fences, CRLF, or an indented closer.
- `### Requirement: ##` yields the name `##` where OpenSpec's `normalizeRequirementName` gives an empty name (no practical impact).
- Scenario names (`_SCN`) do not strip a closing `#` run although OpenSpec does.

Leftover review suggestions (PR #487, Copilot guard coverage tests).

- Add a PowerShell-tool-event test for `block-unsafe-recursive-delete` through the Copilot adapter (`Remove-Item -Recurse -Force` on a link); the guard handles it but only the Bash form is tested there.
- The bash launcher test picks `bash` from PATH, which on some Windows machines is WSL's `System32\bash.exe`, not Git Bash; resolve the shell explicitly so the test does not depend on which one wins.
