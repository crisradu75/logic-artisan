# Blocking findings: one review, then a stakes filter

A review reports everything it finds. Only a **blocking** finding is fixed in the change; every other finding is **non-blocking**. It goes to the repo-root `TODO.md` as one line, and no fix round is spent on it. A reviewer's Critical or Important label is an input to this filter, never the answer.

## A finding blocks when it meets any one of three conditions

- **It touches a protected area.** It could lose, corrupt or leak what a protected area covers. What is protected is defined once, in "What is protected" below.
- **It is a real correctness bug in what the change ships.** That is wrong behaviour a user would see, a break in something shipped to other repos, a requirement that is false or unprovable, or a failure of `openspec validate --strict`.
- **It leaves something unbuildable or unproven.** A requirement cannot be built as written, or a check or test cannot catch what it claims to catch (it cannot fail when it should).

A finding that names a protected area is never non-blocking. Whoever applies the filter re-reads every non-blocking row that mentions one.

**A brief to an agent that reads no files carries this file's text**, pasted at dispatch time and never copied by hand into the brief: the three conditions, "What is protected", and the repo's Stakes section (or, with none, the line "no Stakes section: the default list applies"). It never says "nothing is protected".

## What is protected

This is the one definition. Every other file points here and does not restate it. The exception is three clauses that are copied into, or read in, other repos and cannot follow a pointer: the seeded `config.yaml` rule, the review-sizing block of `model-routing.md` and the quality floor of `economy-rules-file.md`. A test holds each to this file's default list and floor.

- **The repo's list:** the `- Protected areas:` line of the Stakes section of `cla.io/project-facts.md`, which `/cla:cla-setup` writes. A line of `none` adds nothing beyond the floor.
- **The default list**, used when the repo has no Stakes section: money, personal data, accessibility, the user's own files, and anything shipped to other repos. It is the set of options `/cla:cla-setup` offers for that line.
- **The floor, always protected whatever the Stakes list says:** security, safety of writes to a user's files, and honesty claims (a statement the product or docs make that is false).

## What a fix buys

Two triggers, kept distinct.

- **The by-hand mutation check** ("break the fix, confirm a test fails") runs for every fix of a blocking finding, and for any guard-hook rewrite.
- **A second review round** runs only after a **protected-area fix**: a fix that touches a protected area, or one in a guard hook. Fixing a doc is a protected-area fix only when the doc is itself a protected area.
