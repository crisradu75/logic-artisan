# Run on the one-protected-list change (2026-11-17)

What changed for the author: the seeded `openspec/config.yaml` rule now takes protected areas from
the Stakes section, with a shared default. The brief's one edited sentence applies only when a repo
has no Stakes section, and this benchmark has one, so the author saw brief v3 plus the new seeded rule.

One Opus author wrote both changes on a fresh copy of the round-3 setup. One blind Opus judge then
scored this run (r4), round 3 (r3, brief v3) and variant A with `judge-prompt.md`, applying the
owner's rule that a kept decision plus a raised conflict with a proposed fix passes an outcome.

| | Words | Requirements | Invented (rough) | a | b | c | d | e | f | g | h |
|---|---|---|---|---|---|---|---|---|---|---|---|
| r4 | 5,874 | 31 | ~10 | pass | pass | pass | pass | partial | partial | partial | pass |
| r3 | 8,860 | 45 | ~15 | pass | pass | pass | pass | partial | pass | missing | pass |
| A | 12,235 | 59 | ~25 | partial | pass | missing | pass | pass | partial | missing | missing |

Words: `find <change> -name '*.md' -exec cat {} + | wc -w` over both changes; requirements:
`grep -c '### Requirement:'` over the same files.

This judge scored r3 6.5 of 8 (e partial); round 3's own judge scored it 7 of 8. That difference is
judge noise, so compare r4 with r3 under this judge only: both 6.5.

Owner's verdict: pass. Recorded slip: r4 dropped decision structure Q15 ("stage named paths only");
its save would commit stray untracked files, which it admits under Risks noted. r3 kept Q15. The
change did not touch the brief's decision-keeping text, so this is read as a single-run slip. Watch
for it in the next run.
