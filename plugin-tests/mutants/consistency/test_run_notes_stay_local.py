"""Mutation batch for test_run_notes_stay_local.py.

Each mutant makes a chain commit its run notes again, drops the sentence that says
they are local, lets a notes-less multi-lite resume look mergeable, stops this repo
ignoring new notes, or breaks cla-init's ignore-line block (re-appends on every run,
clobbers the file, glues the line onto an unterminated last line, or takes a line
that merely contains the pattern for it). One more lets spec-to-pr commit its record
with no PR open.

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
        'if [ -e "$ROOT/.gitignore" ] && grep -qxF -- "$line" "$ROOT/.gitignore"; then',
        "if false; then",
        TARGETS,
    ),
    (
        "cla-init takes a line that only contains the pattern for it",
        CLA_INIT,
        'grep -qxF -- "$line" "$ROOT/.gitignore"',
        'grep -qF -- "$line" "$ROOT/.gitignore"',
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
]
