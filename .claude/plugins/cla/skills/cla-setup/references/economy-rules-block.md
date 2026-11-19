The block for item 7a of `SKILL.md` (replace `${CLAUDE_PLUGIN_ROOT}` first, as "Resolving `${CLAUDE_PLUGIN_ROOT}`" there says): report the line it prints, `created`, `replaced` (with its second line), `unchanged` or `NOT written` with the reason, and after a `NOT written` or any other non-zero exit carry on with item 8.

```bash
: "${ROOT:?ROOT unset: set it with the repo-root step at the top of this skill first}"
python3 "${CLAUDE_PLUGIN_ROOT}/skills/cla-setup/scripts/render_economy_rules.py" --root "$ROOT"
```
