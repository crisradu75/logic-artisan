# Design

Trigger: a cross-cutting change. It sets contracts that later changes cite, adds data formats, and covers a security scan (the secret scan). See `proposal.md` for the why, and the specs for the outcomes.

## Context

- The repo has no code, tests or tags yet. `marketplace.json` uses a folder source.
- No domain repo exists yet, so the real-file checks use the stand-in corpus defined in `tasks.md` group 1.

## Goals / Non-Goals

**Goals:** pin every default a reviewer must agree on before code exists.

**Non-Goals:**
- hooks, the Python probe and `hooks.json`
- trigger evals
- the per-folder write-rules file
- `hubs/` and `archive/` handling, and the other deferred metadata (structure Q14)
- wikilinks

## Decisions

**D1. One file, `plugins/mnemo/scripts/mnemo_check.py`, standard library only, with `argparse` subcommands.**
- Why: callers need one entry point, and a single file is one packaged path.
- Rejected: a package of modules, which means more shipped paths. PyYAML, which needs an install.

**D2. Output contract.**
- Exit codes:
  - 0: pass
  - 1: problems found
  - 2: could not run. This covers usage errors, a missing or unreadable schema, git errors and pull conflicts.
  - 3: `save` committed but did not push
- Each problem goes to stderr as one line: `<path>:<line>: <rule>: <message>`. `:<line>` is left out for file-level problems.
- stdout holds only one summary line, `mnemo_check <sub>: ok (<n> files)` or `mnemo_check <sub>: <n> problems`.
- Rule IDs:
  - `schema.no-frontmatter`
  - `schema.missing-field`
  - `schema.bad-value`
  - `schema.inbox-status`
  - `schema.unknown-type`
  - `schema.wrong-folder`
  - `schema.bad-name`
  - `yaml.unsupported`
  - `links.missing-target`
  - `links.deleted-target`
  - `deletions.outside-inbox`
  - `secrets.api-key`
  - `secrets.private-key`
  - `secrets.card-number`
  - `secrets.iban`
- Why stderr: Claude Code shows a blocking hook's stderr to Claude.
- Rejected: JSON output, which no caller needs yet.

**D3. Roots.**
- The repo root is `git rev-parse --show-toplevel`, run from the working directory. No `mnemo.schema.yml` at that root means exit 2.
- Plugin assets, meaning the base schema, are found from the script's own folder. This is not the repo.
- Rejected: finding the repo from `__file__` (CLA #52).

**D4. Selection.**
- Default: `git status` against `HEAD`, untracked files included and ignored files excluded.
- `--staged`: the index against `HEAD`.
- `--range A..B`: the commits in that range.
- `--all`: tracked files plus untracked files that are not ignored.
- Optional trailing paths narrow any mode.
- A repo with no commits compares against the empty tree.
- Moves use git's default rename detection (50% similarity). A move is not a deletion.
- What a check reads in each mode:
  - default and `--all`: links and schema read the working tree
  - `--staged`: they read the index
  - `--range`: they read `B`
- An empty selection is a pass with `0 files`, not a skipped check.

**D5. YAML subset.** The same grammar is used for front matter and schema files.

| Construct | Rule |
|---|---|
| Encoding | UTF-8. A BOM is stripped. Line endings are LF or CRLF |
| Front matter | The first line is `---` and it ends at the next `---`. Only top-level keys are allowed |
| Schema files | Block mappings up to depth 2 (depth 0 to 2), indented 2 spaces per level. Tabs are rejected |
| Key | `[A-Za-z_][A-Za-z0-9_-]*`, then `:`, then a space or the end of the line. A duplicate key is rejected |
| Plain value | Read as a string. It must not start with `{ [ & * ! \| > % @ ` or `- `, must not contain `: ` or ` #`, and must not carry trailing text |
| Quoted value | `"…"` with only the escapes `\"` and `\\`, or `'…'` with `''`. Nothing may follow the closing quote |
| Inline list | `[a, "b, c"]`. Items are plain or quoted. Nested lists are rejected. `[]` is an empty list |
| Empty value | In front matter, `key:` means an empty value. In a schema file it opens a nested block |
| Comments | Only full-line `#` comments are allowed |
| Rejected | Block lists, inline maps, `\|`/`>` scalars, anchors, tags and multi-document files |

- Why reject these instead of reading them leniently: a construct that real YAML reads differently is never silently misread.
- Rejected: accepting block lists, which would add more grammar for one editor's style.

**D6. Base schema `plugins/mnemo/conventions/base-schema.yml`** (in the D5 subset):
```
required: [type, title, created, summary, status]
optional: [updated, tags, aliases, source]
date_fields: [created, updated]
list_fields: [tags, aliases]
status_values: [inbox, active, archived]
inbox_folder: inbox
```
- The status values come from build-guide report line 152.
- Rejected: a Markdown base schema, which a script cannot read reliably.

**D7. Domain schema `mnemo.schema.yml`.**
- Top-level keys: `domain` (string) and `types` (mapping). Each type allows only these keys:
  - `folder` (required)
  - `name` (default `<slug>`)
  - `required` (default `[]`)
  - `optional` (default `[]`)
- Any other key, or a type named `inbox`, means exit 2.
- Name-pattern tokens:
  - `YYYY` matches 4 digits
  - `MM` matches 01 to 12
  - `DD` matches 01 to 31
  - `<anything>` matches `[a-z0-9]+(-[a-z0-9]+)*`
  - anything else is literal
- The pattern is matched against the file stem. The note's path must start with `<folder>/`, and subfolders are allowed.
- Rejected: being lenient with unknown keys, which hides typos. A later key arrives with a plugin release.

**D8. Notes and links.**
- Which files are notes: as in the `check-interface` spec.
- Links come in three forms: inline `[t](x)`, image `![a](x)` and reference definition `[id]: x`.
- These are ignored:
  - fenced code (`` ``` `` and `~~~`) and inline code
  - targets with a URL scheme
  - pure `#` anchors
- Before resolving a target:
  - `#…` and `?…` are stripped
  - `%xx` is decoded
  - `<…>` is unwrapped
  - a link title is dropped
- A target starting with `/` resolves from the repo root. A target that resolves outside the repo is a problem.
- Matching is case-exact against git's file list.
- Deleted-path linkers: for each path deleted or moved away, every `.md` file in the repo is scanned for links that resolve to it.

**D9. Secret patterns.**
- Scope: every covered file that has no NUL byte in its first 8000 bytes (git's binary test). The file is decoded as UTF-8 with invalid bytes replaced.
- The whole file is scanned. `--range` scans each commit's introduced versions.

| Kind | Pattern (word-bounded) | Unmasked hit needs |
|---|---|---|
| api-key | `AKIA`/`ASIA`+16 `[A-Z0-9]`. `gh[pousr]_`+36. `github_pat_`+22. `sk-ant-`+20. `sk-`/`sk-proj-`+20. `AIza`+35. `xox[abprs]-`+10. `(sk\|rk)_(live\|test)_`+16. `glpat-`+20 | the prefix and the length |
| private-key | `-----BEGIN [A-Z ]*PRIVATE KEY( BLOCK)?-----` | the line |
| card-number | 13 to 19 digit positions, optionally grouped by single spaces or hyphens | a Luhn pass |
| iban | `[A-Z]{2}\d{2}` + 11 to 30 alphanumerics, optionally in groups of 4 | mod-97 = 1 |

- Masks are `*`, `•` and `x`/`X`.
- A masked card number or IBAN counts as a hit with no checksum when:
  - it has the same shape
  - at least one character is masked
  - at least 4 real digits remain
- In API-key bodies, `*` and `•` count toward the length.
- Messages give the kind, the file and the line, and never the value.
- Rejected:
  - generic `password=` rules, because of false positives
  - letting masked values pass (the owner overruled this in structure Q8)
  - scanning only added lines, because a staged old secret is still committed

**D10. `save`.**
- Steps:
  1. Resolve the repo root.
  2. If `git status --porcelain` is empty, print "nothing to save" and exit 0.
  3. The paths to save are the arguments, or else every changed path, named one by one.
  4. Run `git pull --rebase --autostash`. A branch with no upstream means exit 2.
  5. Run all four checks on those paths, in the default selection.
  6. Run `git add -- <paths>`.
  7. Run `git commit --only -m <msg> -- <paths>`. The message comes from `--message` and defaults to `mnemo: save changes`.
  8. Run `git push`.
- When the push fails, `save` runs one more pull with rebase and one more push. The retry count is 1 and the checks do not run again.
- On a conflict, `save` runs `git rebase --abort`. Autostash then puts the owner's changes back.
- Each network call is limited by `MNEMO_NET_TIMEOUT_SECONDS`, default 30. The constant `SAVE_WORST_CASE_SECONDS = 150` covers 4 network calls plus 30 s of checks. The `add-guard-hooks` change must set the `hooks.json` timeout to at least this value, and a test ties the two together.
- `save` never moves or edits a file. The `inbox/` fallback belongs to capture.
- Rejected: committing before pulling, which is not the decided order (structure Q13). Re-running the checks after the retry, which could leave an unpushable local commit that is half-checked.

**D11. Release pointer.**
- `marketplace.json` entry: `{"source": "git-subdir", "url": "https://github.com/crisradu75/mnemo-plugin", "path": "plugins/mnemo", "ref": "mnemo--v<version>"}`. This is CLA's shape and tag form.
- The test runs `git show <ref>:plugins/mnemo/.claude-plugin/plugin.json` and checks the version against the version in the tag's name. It then checks that the version at `HEAD` is at least the pointer's version.
- Why at the tag, not at `HEAD`: every PR bumps the version, and the owner rejected "a version bump is the release" (architecture Q10). A test that compares at `HEAD` would fail on every PR.

**D12. Tests.**
- Tests live in `tests/` at the repo root and run with `python -m unittest discover -s tests`.
- Each test builds its git repos in `tempfile.TemporaryDirectory`, with a local bare remote and a fixed git identity from the environment.
- The script runs through `sys.executable`.
- Fixtures use invented placeholders.
- The packaging tests read `git ls-files`, so `__pycache__` does not count.

## Risks / Trade-offs

- Editors that write block lists will hit `yaml.unsupported`. Mitigation: the message shows the inline form.
- Binary files and generic passwords are not scanned. Mitigation: the scope is stated in the reports. Revisit after the false-positive measurement.
- An upstream deletion that lands during the push retry can break a link without the checks running again. Mitigation: `mnemo-review` checks the whole repo.
- An autostash re-apply can itself conflict. Mitigation: exit 2, with git's message and the stash left for the owner. Never drop the stash.
- Switching the pointer before sync is verified could break installs. Mitigation: it is gated on task 1.3.
