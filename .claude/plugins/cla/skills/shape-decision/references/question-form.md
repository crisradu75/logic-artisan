# Question form

How each shape-decision question looks and how its answer is read.

## Layout

Write each question as plain markdown in this shape:

```
[Q{n}]

**{Question text}**
Unlocks: {the decision this answer settles}

1. **{Option}**
   - Pros: ...
   - Cons: ...

2. **{Option}**
   - Pros: ...
   - Cons: ...

3. **{Option}**
   - Pros: ...
   - Cons: ...
```

- **Number**: `n` is the question's number, which axis citations use. No total, no count of open axes.
- **Unlocks line**: the decision the answer settles.
- **Options**: two or more, numbered, each with a short bold label, Pros and Cons, listed from the smallest change to the largest.

## The recommended option

Mark exactly one option, whichever the reasoning below picks, as `[Recommended] **{Option}** — {one-line rationale}`.

Never recommend a shortcut or heuristic that leaves the stated need half met. When a simpler option fully meets the stated need, recommend it, unless the larger option removes a named cost that is present now; the rationale then names that cost. An earlier answer or a written repo rule that excludes an option is a fact, not a cost to weigh. Cost is a con to list; the user can always choose either path.

When a cleaner option becomes possible mid-session (for example, a capability an earlier answer unlocked), offer it even if it was not in the original set.

## Why not `AskUserQuestion`

Do not use the `AskUserQuestion` tool. Its four-option cap and short label slots cannot carry the Pros, Cons and recommendation rationale this form needs.

## Reading answers

An answer may be a bare number, a number with a change ("2, but also do X"), or free prose. Record the user's actual intent: a caveat attached to an option is carried into later questions and into the Decision Summary, not only the number. If an answer is genuinely ambiguous, ask one short clarifying follow-up before moving on.

A revision of an earlier answer may be loose ("actually, for Q2…", "go back on the one about X"); no fixed syntax is required.
