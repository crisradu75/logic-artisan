# Blocking findings: one review, then a stakes filter

A review reports everything it finds. Only a **blocking** finding is fixed in the change; every other finding is **non-blocking**. It goes to the repo-root `TODO.md` as one line, and no fix round is spent on it. A reviewer's Critical or Important label is an input to this filter, never the answer.

## A finding blocks when it meets any one of three conditions

- **It touches a protected area.** It could lose, corrupt or leak what a protected area covers. The protected areas are the Stakes section of `cla.io/project-facts.md`, plus the floor below. With no Stakes section, they are the floor plus money, personal data, accessibility and the user's own files.
- **It is a real correctness bug in what the change ships.** That is wrong behaviour a user would see, a break in something shipped to other repos, a requirement that is false or unprovable, or a failure of `openspec validate --strict`.
- **It leaves something unbuildable or unproven.** A requirement cannot be built as written, or a check or test cannot catch what it claims to catch (it cannot fail when it should).

**The floor, always protected whatever the Stakes list says:** security, safety of writes to a user's files, and honesty claims (a statement the product or docs make that is false).

A finding that names a protected area is never non-blocking. Whoever applies the filter re-reads every non-blocking row that mentions one.

**A brief that applies this filter carries this file's text** (the three conditions, the floor and the default list), because the agent or reader may not open the file. When the repo has no Stakes section, the brief says the default list applies; it never says "nothing is protected".

## What a fix buys

Two triggers, kept distinct.

- **The by-hand mutation check** ("break the fix, confirm a test fails") runs for every fix of a blocking finding, and for any guard-hook rewrite.
- **A second review round** runs only after a **protected-area fix**: a fix that touches a protected area, or one in a guard hook. Fixing a doc is a protected-area fix only when the doc is itself a protected area.
