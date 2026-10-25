# A repo's instruction files

A repo keeps its standing rules in `CLAUDE.md`, `AGENTS.md`, or both. Each can sit at the root and
in a nested folder for one area.

## Reading

Read every instruction file that exists: `CLAUDE.md` and `AGENTS.md`, at the root and nested for
the affected area. When both exist, read both.

Why: by default Claude Code loads `AGENTS.md` only when no `CLAUDE.md`, `.claude/CLAUDE.md` or
`CLAUDE.local.md` exists in the working directory or above. With both present it loads the
`CLAUDE.md` files alone, so rules living only in `AGENTS.md` stay invisible, unless the user sets
"Project instructions" to load both. Versions before 2.1.277 do not read `AGENTS.md` directly.
Source: the Claude Code memory documentation.

## Writing

When a rule or lesson goes into the repo's instruction file, follow the repo's setup.

- **Exactly one file exists at the root:** write to it. Nested files hold rules for their own folder.
- **Both exist and `CLAUDE.md` imports or symlinks `AGENTS.md`:** write to `AGENTS.md`. The import
  is a line that reads `@AGENTS.md` in `CLAUDE.md`.
- **Both exist and are not linked:** write to `CLAUDE.md`. Say in the report line which file and why.
- **Neither exists:** ask the user which one to create. Never create one silently.
