Detail for item 5 of `SKILL.md`. Moved verbatim from `SKILL.md`; the item's start-of-step rules are repeated there.

### 5. OpenSpec authoring rules — `openspec/config.yaml`

The one path outside `cla.io/`, `.gitignore` and the rules file of item 7a this skill writes, and it is still project data. OpenSpec injects a
config's `rules:` into every artifact's authoring instructions, so the block the script holds is how OpenSpec's
own stock limits reach every CLA authoring run.

- `openspec/` exists and neither `openspec/config.yaml` nor `openspec/config.yml` does → seed
  `config.yaml` and report `created`.
- Either file exists → leave it **byte-identical** and compare: the script lists, under its
  artifact, each shipped rule the file does not carry word for word (`+`) and each earlier wording
  of a shipped rule it still carries (`-`), or reports the rules current. OpenSpec reads
  `config.yaml` first, so a new `config.yaml` would silently hide an existing `config.yml`.
  `openspec init` writes `config.yaml` whenever neither exists, so this is the common path.
- Lines listed → show the user exactly those `+` and `-` lines and ask for a yes on that diff. Only
  on yes, add each `+` line under its artifact and delete each `-` line, and change nothing else: a
  line the script did not mark `-` is the repo's own and stays, however close it reads to a shipped
  rule. Never make this edit silently.
- `openspec/` absent → print the block and create nothing. `openspec init` owns that directory.

**OpenSpec version.** CLA relies on `openspec validate <change> --strict` failing a MODIFIED block that
drops a live scenario (verified on 1.14.1). When `openspec/` exists, run `openspec --version` and, if it
is older than 1.14.1, say so in the report and recommend upgrading.

Run the script, which holds the shipped `rules:` block and the earlier wordings, and report what it
prints. Any non-zero exit, or output with no `openspec/...:` status line, means the config was
not checked (exit 1: the script could not write or read it): say so, and never call the rules current.

```bash
: "${ROOT:?ROOT unset: set it with the repo-root step at the top of this skill first}"
SEED="${CLAUDE_PLUGIN_ROOT}/skills/cla-setup/scripts/seed_openspec_rules.py"
[ -f "$SEED" ] || { echo "openspec/config.yaml: NOT checked, seed script not found at $SEED (plugin root unresolved?)"; exit 1; }
python3 "$SEED" "$ROOT"
```

The script reads the `Test proof granularity:` line of `cla.io/project-facts.md` and compares the `tasks`
rule for that granularity (`requirement` when there is no line). When item 13 records a `scenario`
choice, re-run the script after the facts file is written, so the `tasks` rule offered matches it.

Each item in the script's `rules:` block that contains `: ` stays double-quoted, or YAML reads it as
a mapping and OpenSpec drops that artifact's rules.
