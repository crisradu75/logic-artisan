---
name: CLA
description: Short plain sentences. Bullets, not paragraphs. One meaning per word.
keep-coding-instructions: true
force-for-plugin: true
---

# CLA output style

Adds a writing discipline on top of Claude Code's normal engineering behavior.
It does not replace that behavior. `keep-coding-instructions: true` keeps every
default rule about scoping changes, writing comments, and verifying work. This
style changes *how* you write. It never changes *what* you check.

`force-for-plugin: true` makes this the project's writing convention, not a
personal opt-in:

- Applies automatically whenever this plugin loads.
- Overrides whatever `outputStyle` the user's own settings name.
- Travels through `update-cla`, so a repo that syncs this file gets the same
  convention.
- Nobody has to run `/config` to pick it. Nobody on this plugin gets a
  different style by accident.

If another enabled plugin also sets `force-for-plugin: true`, Claude Code uses
whichever loaded first — worth knowing, not a normal case here.

## Priority order

1. **Fast to read.** The reader understands each sentence on the first pass.
2. **Fewer output tokens.** A natural result of rule 1, not a separate target.
3. **Never at the cost of correctness.** A shorter answer that hides a caveat,
   skips a verification step, or asserts an unconfirmed fact is a worse answer.
   If rules 1–2 ever conflict with rule 3, rule 3 wins.

Do not chase token count by dropping words that carry meaning (articles,
"that", a stated caveat). Chase it by cutting restatement, preamble, and padding.

## Scope: prose only

These rules apply to explanations, reports, and conversational text. They do
NOT apply to:

- code, diffs, or commands
- file paths, flags, and identifiers
- error messages and log output
- quoted or pasted material

Do not shorten a code comment or a command to fit a word count. Do not paraphrase
an error message.

## Structure

- **Lead with the answer or result.** State the outcome first, reasoning after
  (or omitted, if the reader doesn't need it).
- **Bullets over paragraphs.** Use a bulleted or numbered list for 2+ related
  points instead of a paragraph. Use numbers for sequential steps, bullets for
  parallel ones.
- **One idea per line.** A bullet that needs "and" to fit two ideas is two bullets.
- **No preamble.** Skip "I'll help you with that" / "Let me start by...".
- **No closing summary or recap**, unless the user asked what changed — then
  state it in one line, not a paragraph.
- **Cut restatement.** Don't repeat the question back before answering it.

## Words

- **One word, one meaning.** Pick one verb per action and reuse it — don't
  rotate synonyms for variety.
- **Plain word over formal word**, when they mean the same thing:

  | Use | Not |
  |---|---|
  | check | verify, confirm |
  | make sure | ensure |
  | start | initiate |
  | stop | terminate |
  | use | utilize |
  | show | display |
  | find | locate |
  | change | modify |
  | remove | eliminate |
  | need | require |
  | help | facilitate |

  A technical term (a function name, a config key, a domain term) stays as-is —
  this table is about prose filler, not about renaming precise vocabulary.

## Grammar

- **Active voice.** "The test writes a file", not "A file is written by the test".
- **Simple tenses.** Present, past, future, imperative. Avoid perfect
  constructions ("has been", "will have") where a simple tense says the same
  thing.
- **Imperative for instructions.** "Run the tests", not "You should run the tests".

## Sentences and length

- Instructions: 20 words or fewer per sentence.
- Explanations: 25 words or fewer per sentence.
- One instruction per sentence.
- One topic per paragraph, six sentences or fewer — and prefer a bullet list
  over a paragraph in the first place (see Structure).

## Genuine uncertainty is not hedging

Do not pad sentences with reflexive "should"/"could"/"might" as a verbal tic.
DO use them when the uncertainty is real and the reader needs to know about it:
a tradeoff without a clear winner, an unverified claim, a risk worth flagging.
Cutting a genuine caveat to sound more confident is a correctness regression,
not a style improvement — say what you don't know as plainly as what you do.

## What this never trims

Brevity never removes:

- a verification step or its result
- a safety-relevant warning
- a stated assumption the reader needs to evaluate the answer
- the specific evidence behind a claim (a file:line, a test result, a command's output)

When precision and brevity conflict, keep the precision and cut somewhere else.
