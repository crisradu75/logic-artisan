Detail for items 6 and 7 of `SKILL.md`. Moved verbatim from `SKILL.md`; each item's ask-first rule is repeated there.

### 6. Retired ledgers — `cla.io/retro/`

Ledgers a skill once wrote and nothing writes or reads any more. A repo onboarded earlier still
holds them, and no install removes them. This block only lists the ones present:

```bash
: "${ROOT:?ROOT unset: set it with the repo-root step at the top of this skill first}"
for f in codify-runs commit-provenance right-model-runs multi-pr-runs multi-spec-runs \
         multi-lite-runs project-review-runs lite-pr-runs shape-decision-runs feedback-runs; do
  if [ -e "$ROOT/cla.io/retro/$f.jsonl" ]; then echo "retired ledger: cla.io/retro/$f.jsonl"; fi
done
```

- Nothing printed → say none is present.
- Lines printed → show them and ask once whether to delete those files. Only on an explicit yes,
  `rm -- <each listed path>` (exactly the listed paths, nothing else under `cla.io/retro/`), and
  report each `deleted`; on anything else report each `kept` and leave it. The deletion is left
  uncommitted, like every other change this skill makes.

### 7. Ignore the chains' run notes — `.gitignore`

`/cla:multi-lite` and `/cla:multi-pr` keep their run notes as local working state that nothing
commits, and refuse to start while git would see them. This adds the ignore line unless a
`.gitignore` in the repo already ignores the notes (any equivalent pattern, CRLF or trailing spaces
included), creating the file if needed. Only a `.gitignore` counts: this machine's global excludes
and the clone's `.git/info/exclude` hide the notes here but not in any other clone.

```bash
: "${ROOT:?ROOT unset: set it with the repo-root step at the top of this skill first}"
line='cla.io/retro/*-run-notes-*.md'
probe='cla.io/retro/multi-lite-run-notes-x.md'
# The deciding pattern, as <source>:<line>:<pattern>; global excludes switched off.
match="$(git -C "$ROOT" -c core.excludesFile=/dev/null check-ignore -v --no-index "$probe")" || match=''
case "${match%%:*}" in
  .gitignore|*/.gitignore) from_repo=1 ;;
  *) from_repo=0 ;;
esac
if [ "$from_repo" = 1 ] && git -C "$ROOT" check-ignore -q --no-index "$probe"; then
  echo "exists (skipped): .gitignore run-notes line"
elif [ "$from_repo" = 1 ]; then
  # Matched but not ignored: a ! pattern un-ignores the notes on purpose.
  echo "un-ignored (left as is): $match"
else
  # A last line with no newline would swallow the new one.
  if [ -s "$ROOT/.gitignore" ] && [ -n "$(tail -c 1 "$ROOT/.gitignore")" ]; then echo >> "$ROOT/.gitignore"; fi
  printf '%s\n' "$line" >> "$ROOT/.gitignore"
  echo "created: .gitignore run-notes line"
fi
```

`un-ignored` → leave the file alone and tell the user the chains will not start until that `!` line
goes.

Ignoring does not untrack a notes file git already tracks; a re-run then edits it, which blocks
branch switches and lets a PR pick it up. List those:

```bash
: "${ROOT:?ROOT unset: set it with the repo-root step at the top of this skill first}"
git -C "$ROOT" ls-files -- 'cla.io/retro/*-run-notes-*.md' | sed 's/^/tracked run notes: /'
```

- Nothing printed → say none is tracked.
- Lines printed → show them and ask once whether to untrack them, warning that every other clone
  loses its working copies on its next pull (history keeps them). Only on an explicit yes,
  `git -C "$ROOT" rm -q --cached -- <each listed path>` (exactly the listed paths; the files stay on
  disk), and report each `untracked`; on anything else report each `kept tracked`. Left
  uncommitted, like item 6.
