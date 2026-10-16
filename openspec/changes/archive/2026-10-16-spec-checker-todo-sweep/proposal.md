# Proposal

## Why

`TODO.md` holds review suggestions on `check_spec_proof.py` from three merged changes. Each was
re-read against `main`; the ones that reproduce are fixed here. The `manual:` line needs a format
change: it names a heading, not a spec, so one line covers a same-named changed requirement in every
spec of a touched change.

## What Changes

- **`manual:` line.** `manual: <spec> / <heading>: <reason>` covers one spec. The tasks rule in
  `openspec/config.yaml` and `RULES` in the seed script say so, word for word; the old wording goes to
  `RETIRED`. The checker still accepts `manual: <heading>: <reason>` with its old meaning (every spec
  of the change) and prints a `NOTE` suggesting the new form, so no consumer's run starts failing.
- **Purpose notes and sentences.** A Serves line whose first line already ends a sentence is not read
  as wrapped. `_mask_code_spans` keeps dropping every backtick when one is unpaired (a stray cannot be
  told from a span's), and the over-count is documented. The weak `count_sentences` case is replaced.
- **Failure paths.** `_git` returns stderr and `_base_text` quotes it. A closed pipe on the final
  print exits 2. `_console_safe` falls back to ASCII with `backslashreplace`. The deep-path test skips
  with a reason off Windows.
- **Spec map.** A link counts only if it renders: not escaped, not an image, not in an indented code
  block, with code spans paired as the page pairs them. A reference definition counts only when its
  label is used. A map is a `.md` file, so a glob that also matches a binary no longer exits 2. A
  setext heading reading as "Spec map" exits 2 like an ATX near miss. A link must name an exact-case,
  tracked or untracked-unignored file. A fence inside a block quote is a fence.
- **Removed specs (owner decision).** A spec a change in progress removes counts as gone for the map
  rule: dropping its map link passes, and a kept link is reported.

Dropped: the docs-task `RETIRED` item. The docs task wording is unchanged since the change that
added it; the only wording change since is the configurable-value rule, already in `RETIRED`.

## Capabilities

### Modified Capabilities

- `spec-proof`: two requirements reworded, one added (8 of 8).
- `spec-map`: one requirement added (4 of 8).

## Impact

`check_spec_proof.py`, `openspec/config.yaml`, the seed script, `test-quality.md`, tests under
`plugin-tests/`, `TODO.md`. Out of scope: the three fence-tracker corners (kept in `TODO.md`), and the
review checklist, `spec-to-pr/SKILL.md` and `DEVELOPER-GUIDE.md`, which another session owns and which
still show the old form, still accepted.
