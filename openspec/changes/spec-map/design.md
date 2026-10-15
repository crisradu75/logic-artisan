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
- **Patterns match the tracked and untracked-unignored file list**, so an ignored folder never supplies
  a map. `*` stays inside one folder, `**/` crosses folders, and case counts.
  Rejected: `fnmatch` (its `*` crosses `/`, so `docs/*.md` would take in every nested file and any link
  in one would count as the map linking that spec); a filesystem glob (walks ignored folders).
- **A declaration that cannot be read exits 2.** A `## Spec map` heading with no bullet, a second such
  heading, a non-bullet line under it, or a heading that reads as "spec map" in another form (`### Spec
  map`, `## Spec map:`) exits 2 naming the line, as the granularity line does.
  Rejected: ignoring it, which would turn the guard off without a word.
- **A spec needs a link from the time a change adds it.** The rule counts live specs and specs an
  active change adds, so the map edit lands in the change and the map still passes after archive.
  Rejected: live specs only (the change would pass, then fail on the first run after archive, and
  Archive stages nothing outside the change and its specs).
- **A comment, a fence or a code span hides a link**, as in the rendered page. A link into
  `openspec/specs/` that names no spec and no existing file is dangling, so a typo is caught.
- **A pattern that matches no file is a PROBLEM**, one per pattern. When no pattern matches any file,
  the unlinked-spec rule is skipped, since it would repeat every spec.
- **No declaration prints nothing.** The summary line `spec map:` appears only for a declared map.
- **The scaffold lives in `cla-setup/SKILL.md`** as a fenced template, with a "Specs not yet placed"
  list holding every live spec, so declaring the map passes the check on day one. Rejected: a
  shipped template file (a new kind of shipped file no checker reads) or a seed script (prose
  does this reliably).
