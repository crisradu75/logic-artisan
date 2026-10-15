# Design

Trigger: real ambiguity. The map has no fixed path or layout, so the guard needs one rule for what
counts as a link and one for a declaration that cannot be read.

## Decisions

- **A link is a Markdown link.** An inline `](target)` or a reference definition `[x]: target`, outside
  code fences, with the `#fragment` dropped, resolved against the map file's folder (a leading `/`
  means the repo root). It is a spec link when it lands on `openspec/specs/<name>` or
  `openspec/specs/<name>/spec.md`. One rule serves every layout.
  Rejected: matching spec names in prose (a sentence mentioning a spec would count as linking it);
  requiring a fixed path prefix (breaks the "any layout" decision).
- **Patterns match like `--tests`.** `fnmatch` over the tracked and untracked-unignored file list, so
  an ignored folder never supplies a map.
  Rejected: a filesystem glob (walks ignored folders, and `**` would mean something different from the
  existing flag).
- **A declaration that cannot be read exits 2.** A `## Spec map` heading with no bullet, a second such
  heading, or a non-bullet line under it exits 2 naming the line, as the granularity line does.
  Rejected: ignoring it, which would turn the guard off without a word.
- **A pattern that matches no file is a PROBLEM**, one per pattern. When no pattern matches any file,
  the unlinked-spec rule is skipped, since it would repeat every spec.
- **No declaration prints nothing.** The summary line `spec map:` appears only for a declared map.
- **The scaffold lives in `cla-setup/SKILL.md`** as a fenced template, with a "Specs not yet placed"
  list holding every live spec, so declaring the map passes the check on day one. Rejected: a
  shipped template file (a new kind of shipped file no checker reads) or a seed script (prose
  does this reliably).
