# A repo's instruction files

A repo keeps its standing rules in `CLAUDE.md`, `AGENTS.md`, or both. Each can sit at the root and
in a nested folder for one area.

## Reading

Read every instruction file that exists: `CLAUDE.md` and `AGENTS.md`, at the root and nested for
the affected area. When both exist, read both.

Why: Claude Code loads `AGENTS.md` by itself only when no `CLAUDE.md` exists in the working
directory or above. With both present it loads `CLAUDE.md` alone, so rules living only in
`AGENTS.md` stay invisible. Claude Code versions before 2.1.277 never load `AGENTS.md`. Source: the Claude Code memory documentation.

## Writing

When a rule or lesson goes into the repo's instruction file, follow the repo's setup.

- **Exactly one file exists at the root:** write to it. Nested files hold rules for their own folder.
- **Both exist and `CLAUDE.md` imports `AGENTS.md`:** write to `AGENTS.md`. The import is a line
  that reads `@AGENTS.md` in `CLAUDE.md`.
- **Both exist and are not linked:** write to `CLAUDE.md`. Say in the report line which file and why.
- **Neither exists:** ask the user which one to create. Never create one silently.
