"""Mutation batch for test_run_notes_stay_local.py.

Each mutant makes a chain commit its run notes again, drops the sentence that says
they are local, lets a notes-less multi-lite resume look mergeable or a notes-less
multi-pr resume run on, drops a chain's refusal to start while its notes are not
ignored, stops this repo ignoring new notes, breaks cla-init's ignore-line block
(re-appends on every run, misses an equivalent line, overrides a deliberate un-ignore,
probes a file the line does not cover, clobbers the file, glues the line onto an
unterminated last line), or breaks its tracked-notes offer (lists untracked or
non-notes files, deletes the working copy, drops the warning). One more lets
spec-to-pr commit its record with no PR open.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_run_notes_stay_local.py
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEV = Path(__file__).resolve().parents[2]
SKILLS = REPO / ".claude" / "plugins" / "cla" / "skills"
HANDOFF = SKILLS / "spec-to-pr" / "references" / "handoff.md"
LITE_SKILL = SKILLS / "multi-lite" / "SKILL.md"
LITE_PHASE4 = SKILLS / "multi-lite" / "references" / "phase4-and-log.md"
LITE_BOOT = SKILLS / "multi-lite" / "references" / "bootstrap-and-tracking.md"
LITE_LOOP = SKILLS / "multi-lite" / "references" / "candidate-loop.md"
PR_CLEANUP = SKILLS / "multi-pr" / "references" / "cleanup.md"
PR_SKILL = SKILLS / "multi-pr" / "SKILL.md"
PR_LOOP = SKILLS / "multi-pr" / "references" / "change-loop.md"
CLA_INIT = SKILLS / "cla-init" / "SKILL.md"
GITIGNORE = REPO / ".gitignore"
GUARD = DEV / "tests" / "consistency" / "test_run_notes_stay_local.py"

TARGETS = [GUARD]

MUTANTS = [
    (
        "spec-to-pr commits its ledger line even when Ship opened no PR",
        HANDOFF,
        "Do this ONLY when Ship opened a PR",
        "Do this whenever the run ends",
        TARGETS,
    ),
    (
        "multi-lite's Phase 4 commits the notes onto the last open PR again",
        LITE_PHASE4,
        "- **Out of scope**:",
        "- **Run notes**: on the last open PR's branch, `git add -- <notes>`, then commit and push.\n"
        "- **Out of scope**:",
        TARGETS,
    ),
    (
        "multi-pr's cleanup commits the running notes again",
        PR_CLEANUP,
        "5. Mark the",
        "5. `git add -- cla.io/retro/multi-pr-run-notes-<date>.md`, commit and push. Mark the",
        TARGETS,
    ),
    (
        "multi-lite stops saying nothing commits its notes",
        LITE_BOOT,
        ", nothing in this run adds or commits it,",
        ",",
        TARGETS,
    ),
    (
        "multi-pr stops saying its running notes are local",
        PR_LOOP,
        "**The running notes are local working state:** gitignored, never added or committed.",
        "**The running notes:**",
        TARGETS,
    ),
    (
        "a multi-lite resume without its notes reads a PR found on GitHub as mergeable",
        LITE_SKILL,
        "so it is left open as `head unverifiable (ledger lost)`, never merged.",
        "so it re-enters step 8.",
        TARGETS,
    ),
    (
        "this repo stops ignoring new run notes",
        GITIGNORE,
        "cla.io/retro/*-run-notes-*.md\n",
        "",
        TARGETS,
    ),
    (
        "cla-init appends the line on every run",
        CLA_INIT,
        'if git -C "$ROOT" check-ignore -q --no-index "$probe"; then',
        "if false; then",
        TARGETS,
    ),
    (
        "cla-init is back to an exact-line grep, so a CRLF or equivalent line is missed",
        CLA_INIT,
        'if git -C "$ROOT" check-ignore -q --no-index "$probe"; then',
        'if [ -e "$ROOT/.gitignore" ] && grep -qxF -- "$line" "$ROOT/.gitignore"; then',
        TARGETS,
    ),
    (
        "cla-init appends the line over a deliberate un-ignore",
        CLA_INIT,
        'elif match="$(git -C "$ROOT" check-ignore -v --no-index "$probe")"; then',
        "elif false; then",
        TARGETS,
    ),
    (
        "cla-init probes a file the run-notes line does not cover",
        CLA_INIT,
        "probe='cla.io/retro/multi-lite-run-notes-x.md'",
        "probe='cla.io/retro/multi-lite-runs.jsonl'",
        TARGETS,
    ),
    (
        "cla-init stops telling the user an un-ignore keeps the chains from starting",
        CLA_INIT,
        "tell the user the chains will not start until that `!` line",
        "tell the user",
        TARGETS,
    ),
    (
        "cla-init overwrites an existing .gitignore",
        CLA_INIT,
        "printf '%s\\n' \"$line\" >> \"$ROOT/.gitignore\"",
        "printf '%s\\n' \"$line\" > \"$ROOT/.gitignore\"",
        TARGETS,
    ),
    (
        "cla-init glues the line onto a last line with no newline",
        CLA_INIT,
        '[ -n "$(tail -c 1 "$ROOT/.gitignore")" ]; then echo >> "$ROOT/.gitignore"; fi',
        '[ -n "$(tail -c 1 "$ROOT/.gitignore")" ]; then :; fi',
        TARGETS,
    ),
    (
        "cla-init lists untracked notes as tracked",
        CLA_INIT,
        'git -C "$ROOT" ls-files -- \'cla.io/retro/*-run-notes-*.md\'',
        "git -C \"$ROOT\" ls-files --cached --others -- 'cla.io/retro/*-run-notes-*.md'",
        TARGETS,
    ),
    (
        "cla-init lists every tracked file under cla.io/retro/",
        CLA_INIT,
        'git -C "$ROOT" ls-files -- \'cla.io/retro/*-run-notes-*.md\'',
        "git -C \"$ROOT\" ls-files -- 'cla.io/retro/*'",
        TARGETS,
    ),
    (
        "cla-init's yes deletes the working copies too",
        CLA_INIT,
        'rm -q --cached -- <each listed path>',
        'rm -q -- <each listed path>',
        TARGETS,
    ),
    (
        "cla-init untracks without warning about other clones",
        CLA_INIT,
        ", warning that every other clone\n  loses its working copies on its next pull (history keeps them).",
        ".",
        TARGETS,
    ),
    (
        "multi-lite starts while git would see its notes",
        LITE_BOOT,
        "3. From the repo root, `git check-ignore -q --no-index cla.io/retro/multi-lite-run-notes-x.md`.",
        "3. From the repo root.",
        TARGETS,
    ),
    (
        "multi-pr checks the other chain's notes name",
        PR_SKILL,
        "`git check-ignore -q --no-index cla.io/retro/multi-pr-run-notes-x.md`",
        "`git check-ignore -q --no-index cla.io/retro/multi-lite-run-notes-x.md`",
        TARGETS,
    ),
    (
        "a notes-less multi-pr resume runs the later changes anyway",
        PR_LOOP,
        "**It then stops before running any not-yet-shipped change that has an earlier change in the sequence**",
        "**It then runs every not-yet-shipped change**",
        TARGETS,
    ),
    (
        "multi-pr's SKILL.md stops stating the notes-less stop",
        PR_SKILL,
        " A resume with no running notes stops before any not-yet-shipped change that has an earlier change, "
        "since its obligations are unknown.",
        "",
        TARGETS,
    ),
]
