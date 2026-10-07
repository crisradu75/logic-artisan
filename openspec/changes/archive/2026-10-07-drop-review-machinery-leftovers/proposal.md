## Why

Review of crisradu75/logic-artisan#312 found two live requirements still describing what that PR removed.

## What Changes

- change-review: the review report no longer carries a claim-shape sweep row.
- orchestration: multi-pr enforces the shared-state edge itself when it merges. The spec no longer
  says the edge is delivered through `--inherits`; no step delivers it.
