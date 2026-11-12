Detail for item 7a of `SKILL.md`. Moved verbatim from `SKILL.md`; the item's replace-whole and never-stops rules are repeated there.

### 7a. The economy rules file — `.claude/rules/cla-economy.md`

An agent working in this repo outside any skill reads the repo's own instruction files (`CLAUDE.md`, `AGENTS.md`)
and `.claude/rules/*.md` and nothing from the plugin. A rules file with no `paths:` frontmatter loads at
launch with the same priority as `.claude/CLAUDE.md`, so this file gets the cost rules to that
agent. The plugin owns the file whole: it is compared on every run and replaced with no prompt when
it differs, so a hand edit is replaced and the report says so (the repo's own rules go in its
instruction files; `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/instruction-files.md` says which). The file is usually committed in the repo, so an upgrade that changes it shows as an
ordinary diff; if `.claude/` is ignored it stays local. This skill never touches `CLAUDE.md` or `AGENTS.md`.

The text is `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/economy-rules-file.md` with two sources
inlined at its markers: `orchestration-economy.md` whole, and the span of `model-routing.md`
between its `review-sizing` begin and end comments. Every source is read through `tr -d '\r'`, so a
CRLF checkout and an LF one write the same bytes. The block prints `created`, `replaced` (existing
content differed, and a second line says local edits were overwritten) or `unchanged`, and writes
only when the text differs. Before writing it requires every source to be present and non-empty,
the begin and end comments to occur exactly once each and in that order, and each include marker
in the frame to occur exactly once; it renders to a temporary file and moves that into place, so a
failed write leaves the existing file untouched. Any failure prints `NOT written` with the reason
and stops the block: report it, then carry on with item 8 (Part 2). A failure here never stops the
skill.

`CLAUDE_PLUGIN_ROOT` below is a placeholder, not a shell variable, and this reference file arrives with
it literal: replace it with the plugin root (see "Resolving `${CLAUDE_PLUGIN_ROOT}`" in `SKILL.md`)
before running the block. If the block prints an unsubstituted or empty root, it aborts without writing.

```bash
: "${ROOT:?ROOT unset: set it with the repo-root step at the top of this skill first}"
PLUGIN="${CLAUDE_PLUGIN_ROOT}"
[ -n "$PLUGIN" ] || { echo ".claude/rules/cla-economy.md: NOT written, plugin root unresolved"; exit 1; }
REF="$PLUGIN/skills/_shared/references"
RULES_FILE="$ROOT/.claude/rules/cla-economy.md"
fail() { echo ".claude/rules/cla-economy.md: NOT written, $1"; exit 1; }
FRAME="$(tr -d '\r' < "$REF/economy-rules-file.md")"
COST="$(tr -d '\r' < "$REF/orchestration-economy.md")"
MODEL="$(tr -d '\r' < "$REF/model-routing.md")"
if [ -z "$FRAME" ] || [ -z "$COST" ] || [ -z "$MODEL" ]; then
  fail "a source is missing or empty under $REF"
fi
BEGIN='<!-- economy-rules-file:review-sizing:begin -->'
END='<!-- economy-rules-file:review-sizing:end -->'
INC_COST='<!-- include: cost-rules -->'
INC_SIZING='<!-- include: review-sizing -->'
[ "$(printf '%s\n' "$MODEL" | grep -cxF "$BEGIN")" = 1 ] && [ "$(printf '%s\n' "$MODEL" | grep -cxF "$END")" = 1 ] ||
  fail "model-routing.md must hold the review-sizing begin and end comments exactly once each"
LB="$(printf '%s\n' "$MODEL" | grep -nxF "$BEGIN" | cut -d: -f1)"
LE="$(printf '%s\n' "$MODEL" | grep -nxF "$END" | cut -d: -f1)"
[ "$LB" -lt "$LE" ] || fail "model-routing.md has the review-sizing end comment before the begin comment"
[ "$((LE - LB))" -gt 1 ] || fail "the review-sizing span in model-routing.md is empty"
SIZING="$(printf '%s\n' "$MODEL" | sed -n "$((LB + 1)),$((LE - 1))p")"
[ -n "$SIZING" ] || fail "the review-sizing span in model-routing.md is empty"
[ "$(printf '%s\n' "$FRAME" | grep -cxF "$INC_COST")" = 1 ] && [ "$(printf '%s\n' "$FRAME" | grep -cxF "$INC_SIZING")" = 1 ] &&
  [ "$(printf '%s\n' "$FRAME" | grep -cF '<!--')" = 2 ] ||
  fail "economy-rules-file.md must hold each include marker alone on a line exactly once, and no other comment"
NEW="$(printf '%s\n' "$FRAME" | while IFS= read -r line; do
  case "$line" in
    "$INC_COST") printf '%s\n' "$COST" ;;
    "$INC_SIZING") printf '%s\n' "$SIZING" ;;
    *) printf '%s\n' "$line" ;;
  esac
done)"
TMP="$RULES_FILE.tmp"
mkdir -p "$ROOT/.claude/rules" || fail "cannot create $ROOT/.claude/rules"
printf '%s\n' "$NEW" > "$TMP" || { rm -f "$TMP"; fail "cannot write $TMP"; }
if [ ! -e "$RULES_FILE" ]; then
  mv -f "$TMP" "$RULES_FILE" || { rm -f "$TMP"; fail "cannot move the new text into place"; }
  echo ".claude/rules/cla-economy.md: created"
elif tr -d '\r' < "$RULES_FILE" | cmp -s - "$TMP"; then
  rm -f "$TMP"
  echo ".claude/rules/cla-economy.md: unchanged"
else
  mv -f "$TMP" "$RULES_FILE" || { rm -f "$TMP"; fail "cannot move the new text into place"; }
  echo ".claude/rules/cla-economy.md: replaced"
  echo "any local edits to .claude/rules/cla-economy.md were overwritten; the repo's own rules go in its own instruction files"
fi
```
