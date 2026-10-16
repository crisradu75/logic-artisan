# Tasks

## 1. The `manual:` line names its spec

- [x] 1.1 The tasks rule in `openspec/config.yaml` and `RULES` ask for `manual: <spec> / <heading>: <reason>`, word for word; the old rule line joins `RETIRED`. Done when the rules-match test passes and a seed run on a config with the old line prints it under `-`.
- [x] 1.2 `manual: <spec> / <heading>: <reason>` covers that spec's changed requirement only, in requirement and scenario mode. Test carries `requirement: spec-proof / A checker reports requirements with no proof` and `requirement: spec-proof / A manual line names its spec, and the older form still counts`.
- [x] 1.3 The old `manual: <heading>: <reason>` still covers the heading in every spec of its change, and an old-form line in a change in progress prints one `NOTE manual:` naming the new form, exit code unchanged. Same markers as 1.2.
- [x] 1.4 A new-form line naming a missing spec, or a heading that spec lacks, is `dangling`. A `(prompt half)` line and a `waiting:` line parse the same way.

## 2. Purpose notes, sentences and failure paths

- [x] 2.1 A Serves line whose first line already ends a sentence is not read as wrapped. Test a Purpose of Serves line, sentence, blank line, more text, and a wrapped Serves line. Test carries `requirement: spec-proof / A checker notes a touched spec's Purpose without failing the run`.
- [x] 2.2 `_mask_code_spans` states the over-count of an unpaired backtick in its docstring; the `count_sentences` case "Run ``a ` b. c`` now." becomes "Run ``a. b`` now.", which the old single-backtick pattern counts as 2. Same marker as 2.1.
- [x] 2.3 `_git` returns stderr, every caller and fake in the tests follows, and `_base_text` quotes it. Test the message holds git's stderr.
- [x] 2.4 A closed pipe on the final print exits 2 and an unknown stdout encoding falls back to ASCII with `backslashreplace`. Test both.
- [x] 2.5 The deep-path test skips with a reason off Windows.

## 3. Spec map

- [x] 3.1 A link counts only if it renders: not escaped, not an image, not in an indented code block, not inside a code span paired as the page pairs it. Test each. Test carries `requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere`.
- [x] 3.2 A reference definition counts only when a `[text][label]`, `[label][]` or `[label]` uses its label. Test a used and an unused one. Same marker as 3.1.
- [x] 3.3 A declared glob reads `.md` files only; one that matches only a binary file reports the declared path as matching no Markdown file. Test a glob over a PNG and a map. Same marker as 3.1.
- [x] 3.4 A setext heading whose words read as "Spec map" (`Spec maps`, `Spec-map`) exits 2 naming the line when no map is declared, as the exact setext form already did. Test carries `requirement: spec-map / A line that looks like the spec map heading is never silently ignored`.
- [x] 3.5 A map link into `openspec/specs/` must name a file in the exact-case tracked or untracked-unignored list; an ignored file or a wrong-case path is reported. Test both. Same marker as 3.1.
- [x] 3.6 A fence inside a block quote opens and closes as a fence, and ends where the quote ends. Test a quoted example holding a link. Same marker as 3.1.
- [x] 3.7 A spec a change in progress removes whole needs no map link, and a link to it is reported. Test dropping and keeping the link. Test carries `requirement: spec-map / A spec a change in progress removes is gone for the map rule`.

## 4. Ship

- [x] 4.1 Remove exactly the fixed lines from `TODO.md`: the `manual:` line, the six spec checker fixes, the first docs-task line and the map lines but the fence-corner bullet. Done when `git diff TODO.md` shows only removals.
- [x] 4.2 Run `check_spec_proof.py --root` read-only on a clone of main and on copies of six real repos before the first edit and on the final commit. Done when the diff shows only added `NOTE` lines, and no `PROBLEM` line changes kind, file or line or exit code. measured: before and after outputs identical on all seven targets (none of them holds an older `manual:` line in a change in progress); on a synthetic change holding one older line and one new-form line, the older script reported the new-form line as dangling and this one adds a `NOTE manual` line for the older.
- [x] 4.3 Run `pytest plugin-tests -q -n auto --dist loadfile` and `openspec validate --specs --strict` once each on the final commit. measured: 2658 passed, 8 skipped (parallel); openspec validate --specs --strict 12 passed, 0 failed.
- [x] 4.4 docs and spec map: `test-quality.md` (the `manual:` form); none affected: root `CLAUDE.md`, `README.md`, the plugin readme and `openspec/spec-map.md` (none states the `manual:` form or the map rule's removed-spec case). `DEVELOPER-GUIDE.md` section 11, the review checklist and `spec-to-pr/SKILL.md` belong to another session and are reported, not edited.
