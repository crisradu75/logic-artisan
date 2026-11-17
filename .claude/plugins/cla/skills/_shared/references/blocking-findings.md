# Blocking findings: one review, then a stakes filter

A review reports everything it finds. Only a **blocking** finding is fixed in the change; every other finding is **non-blocking**. It goes to the repo-root `TODO.md` as one line, and no fix round is spent on it. A reviewer's Critical or Important label is an input to this filter, never the answer.

## A finding blocks when

- **It touches a protected area.** It could lose, corrupt or leak what a protected area covers. The protected areas are the Stakes section of `cla.io/project-facts.md`. With no Stakes section, they are money, security, personal data, honesty claims, accessibility and the user's own files.
- **It is a real correctness bug in what the change ships.** That is wrong behaviour a user would see, a break in something shipped to other repos, a requirement that is false or unprovable, or a failure of `openspec validate --strict`.

A finding that names a protected area is never non-blocking. Whoever applies the filter re-reads every non-blocking row that mentions one.

## What a protected-area fix buys

A second review round, and the by-hand mutation check ("break the fix, confirm a test fails"), run only after a **protected-area fix**: a fix that touches a protected area, or one in a guard hook. Any other fix ships with a test that fails without it, and no second round or hand-mutation. Fixing a doc is a protected-area fix only when the doc is itself a protected area.
