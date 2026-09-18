"""Mutation batch for test_multi_lite_policy_names_agree.py.

The guard reads multi-lite's prose, which is the procedure an unattended
orchestrator executes, so each mutant reintroduces one defect a review of the
merge-policy change actually found — or the one its fix most plausibly regresses
to — and leaves the surrounding text intact.

The last mutant aims at the GUARD: a policy scanner that stops recognising the
real policy names reads nothing and must not pass.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_multi_lite_policy_names_agree.py
"""

from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
DEV = Path(__file__).resolve().parents[2]
REFS = PLUGIN / "skills" / "multi-lite" / "references"
LOOP = REFS / "candidate-loop.md"
GUARD = DEV / "tests" / "consistency" / "test_multi_lite_policy_names_agree.py"


def _nl(text: str, path: Path = LOOP) -> str:
    """Re-spell `\\n` as the target file's own line ending.

    `mutate.py` matches raw text, so a bare `\\n` in an anchor matches NOTHING on
    a CRLF checkout — and a batch with one unresolvable anchor aborts in preflight
    and runs no mutant at all, silently. This is derived from the file's bytes
    rather than spelled, which is the shape `mutants/annotate/` already uses."""
    return text.replace("\n", "\r\n" if b"\r\n" in path.read_bytes() else "\n")

# Scoped to the one guard, never the whole area: a batch pointed at an area
# reports every mutant killed the moment anything else there is red.
TARGETS = [GUARD]

MUTANTS = [
    (
        "a policy is renamed in one file only",
        REFS / "phase4-and-log.md",
        "- **Merge policy**: `merge-each-clean` or",
        "- **Merge policy**: `merge-all-clean` or",
        TARGETS,
    ),
    (
        "the ledger stops declaring head_sha, which resume branches on",
        REFS / "bootstrap-and-tracking.md",
        "pr_number | head_sha | deferred",
        "pr_number | deferred",
        TARGETS,
    ),
    (
        "step 7's no-findings arm reaches step 8 without recording review: clean",
        LOOP,
        "Write `review: clean` to its ledger row and go to step 8.",
        "Go to step 8.",
        TARGETS,
    ),
    (
        "the two policies swap what they merge",
        LOOP,
        "yes, whether or not anything depends on it.",
        "yes only if a later candidate depends on it.",
        TARGETS,
    ),
    (
        "a resume with no recorded findings is inferred clean",
        LOOP,
        "**Never infer clean.** Write `review: unresolved` with the reason `findings lost on resume`, and take step 7's unresolved branch.",
        "Treat the findings as none: write `review: clean` and re-enter step 8.",
        TARGETS,
    ),
    (
        "step 7 treats undeterminable findings as zero",
        LOOP,
        "Write `review: unresolved` with the reason `deferred findings not determinable`, and take the unresolved branch below.",
        "Treat it as `0`: write `review: clean` and go to step 8.",
        TARGETS,
    ),
    (
        "a resume adopts a moved head and merges it",
        LOOP,
        "the PR may hold commits nobody in this run tested or reviewed. Do not merge.",
        "the PR holds new commits. Re-enter step 8, which runs the full gate on them.",
        TARGETS,
    ),
    (
        "step 3 stops checking a dependency's merge commit",
        LOOP,
        "must have ledger `status: merged` with a `merge_commit`, and `git merge-base --is-ancestor <merge_commit> HEAD`",
        "must have ledger `status: merged`, and the base",
        TARGETS,
    ),
    (
        "a gate with no test commands becomes a warning and the merge proceeds",
        LOOP,
        "→ do not merge; the reason is `full gate unavailable`.",
        "→ record `full gate unavailable` as a warning and continue.",
        TARGETS,
    ),
    (
        "a conflicting PR proceeds to the merge",
        LOOP,
        "`CLEAN`, `HAS_HOOKS`, or `BEHIND` → proceed.",
        "`CLEAN`, `HAS_HOOKS`, `DIRTY`, or `BEHIND` → proceed.",
        TARGETS,
    ),
    (
        "a zero exit code is trusted as a merge",
        LOOP,
        "`state` must be `MERGED`. Otherwise:",
        "The exit code already confirmed the merge; read `mergeCommit` for the ledger. If it is empty:",
        TARGETS,
    ),
    (
        "an ordinary gh error stops merging for the whole run",
        LOOP,
        "It does **not** set `merging stopped`: an error",
        "It also sets `merging stopped`, since an error",
        TARGETS,
    ),
    (
        "merging stopped overrides a policy's no as well as its yes",
        LOOP,
        "**Then, only for a yes: the ledger header records `merging stopped`** → the host already refused a merge this session, so do not attempt one.",
        "**The ledger header records `merging stopped`** → the host already refused a merge this session.",
        TARGETS,
    ),
    (
        "the enforcement round trusts HEAD == remote without proving a commit exists",
        LOOP,
        _nl("     - `git rev-parse HEAD` must differ from the row's current `head_sha`. The same value means no commit was made (a hook rejected it, or nothing was staged).\n"),
        "",
        TARGETS,
    ),
    (
        "8b stops requiring a clean tree before the gate",
        LOOP,
        " Then `git status --porcelain -- . ':(exclude)cla.io/retro'` must be empty. Anything listed would be tested by the gate below without being part of the merge, so do not merge; the reason is `uncommitted changes`.",
        "",
        TARGETS,
    ),
    (
        "a queued or auto-merge PR is recorded as merged",
        LOOP,
        "It is not merged now, so a candidate that must merge before a later one is still `failed-merge` and quarantined.",
        "Treat it as merged: write `status: merged` and continue.",
        TARGETS,
    ),
    (
        "step 7's unresolved branch quarantines only dependents, even for a "
        "shared-state PR",
        LOOP,
        "quarantine as defined at the top of step 8: its downstream subtree for a `depends_on` edge, every later candidate for a shared-state edge.",
        "quarantine its downstream subtree (`blocked-by-upstream-failure`).",
        TARGETS,
    ),
    (
        "steps 2 and 7 no longer run the changed-files check before stopping a "
        "candidate",
        LOOP,
        "**Steps 2 and 7 can stop a candidate before step 8 runs, so each runs 8a's changed-files check itself first**",
        "**Step 8 runs 8a's check when it reaches a candidate**",
        TARGETS,
    ),
    (
        "GUARD: the policy scanner stops recognising two-segment names",
        GUARD,
        '_POLICY_SHAPED = re.compile(r"(?<![A-Za-z0-9-])merge-[a-z]+(?:-[a-z]+)+")',
        '_POLICY_SHAPED = re.compile(r"(?<![A-Za-z0-9-])merge-[a-z]+(?:-[a-z]+){2,}")',
        TARGETS,
    ),
]
