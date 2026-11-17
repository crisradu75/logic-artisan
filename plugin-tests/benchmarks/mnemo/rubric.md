# Rubric

The judge scores each version of the two changes (`add-check-scripts`, `add-mnemo-improve`) on the
dimensions below. The wording of the critical outcomes is copied word for word from
`judge-prompt.md`; change one only with the owner's approval, because every baseline score depends
on it.

## Critical outcomes

Each is scored covered, raised as an open question, or missing.

a. a commit that could not be pushed (cloud VM reclaimed) is not silently lost;
b. a pull/rebase conflict during save never loses or discards the owner's uncommitted note changes (incl. stashed changes);
c. a hung save/hook is time-bounded;
d. a failed check commits nothing;
e. a secret-scan hit blocks the commit and does not fall back to inbox/;
f. the improve loop's scoring does not change or consume the query log it learns from;
g. a test question added for a fix is not scored against a base where the fix doesn't exist yet;
h. a commit left unpushed on a clean tree is retried by a later save.

Outcome h was added by the owner on 2026-11-17, after the baseline run; it was not in the judge
prompt that run used. All three baseline versions miss it. Each reports "committed, not pushed"
(exit 3), but a later `save` on a clean tree exits 0 without pushing (baseline `note-saving` spec;
A `note-save`; B `note-save`), so an unpushed commit is retried only when a later save has new
changes. The baseline is scored "missing" on h for all three from that reading, not from a judge.

## Scoring dimensions

1. **Faithfulness**, 1-5: every decision in scope is represented correctly; list each decision
   missed or contradicted.
2. **Invention**, 1-5 (5 = little and harmless): content no decision asked for. Count roughly, give
   3 examples each, and classify each as valuable, neutral or harmful.
3. **Gap handling**: where the decisions are silent on something the change truly needs, does the
   version invent an answer silently, invent and flag it, or ask the owner, and is that the right
   call?
4. **Critical outcomes**: a to h above.
5. **Reviewability**, 1-5: could the owner read and approve each change in about 15 minutes, with
   `wc -w` per file.
6. **Implementability**, 1-5: could a competent implementer build it without guessing on anything
   that matters for one user.

The pass rule uses three measures from these: critical outcomes covered (dimension 4), invented
items (dimension 2, the rough count), and words (dimension 5, total `wc -w` over both changes).
See `README.md`.
