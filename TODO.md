# TODO

Leftover review suggestions (PR #482, pre-push URL match).

- pre-push URL match: when two remotes share one URL, the first by name wins. Add a comment or a test saying so.
  - Decision needed: `hooks/git/pre-push` is a guard hook, out of scope for a sweep; the owner OKs a comment-only edit there, or declines.

Leftover review suggestions (PR #486, check_spec_proof fences and requirement names).

- `_FENCE_LINE` accepts any indentation, so a fence indented 4 or more spaces counts as a fence where CommonMark treats it as code; no test pins indented fences, CRLF, or an indented closer.
  - Decision needed: `_fence_step`'s docstring says "at ANY indent" on purpose (a fence inside a list item); the owner decides whether the top-level 4-space case should change, or only be pinned by a test as it is.
