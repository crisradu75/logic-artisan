"""Mutation batch for test__git_common.py.

`_git_common.py` is two things `probe_state.py` cannot work without: the repo
root, and the `branch-prefix.local.md` overlay contract. Both fail the same
quiet way — the wrong answer is a perfectly ordinary-looking one. A repo on
`claude/feature/` that silently gets `feature/` makes `probe_state` report
finished work as not started, and the orchestrator then redoes it.

**One fixture fact decides several kills, and it is worth stating because it
nearly hides mutant 1.** `plugin-tests/tests/skills/spec-to-pr/conftest.py` pins
`CLA_BRANCH_PREFIX=feature/` autouse for the whole scope, AND this repo carries a
real `cla.io/overlays/branch-prefix.local.md` whose value is also `feature/`. So
most tests cannot tell a working overlay reader from a broken one — they agree by
coincidence. Only `test_a_present_overlay_is_actually_read_end_to_end` unsets the
env var, writes an overlay saying something DIFFERENT, and repoints `repo_root`.
That test's own docstring records mutant 1 having survived once, which is why it
exists.

**Mutants 3 and 5 are about the DIAGNOSTIC, not the return value**, and both
would be invisible to a test that only checked what came back. Mutant 3 moves the
fallback warning to stdout, where it corrupts a JSON contract instead of warning
anyone; mutant 5 makes the two frontmatter degradations indistinguishable, so
whoever has to fix the overlay is told the wrong thing about it.

**DELIBERATELY NOT MUTANTS, each unkillable in a correct tree:**

  * `if out.returncode == 0 and out.stdout.strip():` -> `if out.returncode == 0:`.
    No test supplies rc 0 with empty stdout — the resolve test gives rc 0 WITH
    stdout, and the three fallback tests give an exception or rc 128. This is a
    coverage gap, not a mutant: that arm of the `detail` assignment never runs.
  * `if env:` -> `if env is not None:`. `CLA_BRANCH_PREFIX=""` is never exercised;
    every test either sets a non-empty value or deletes the variable.
  * changing `timeout=10`. Nothing in this guard asserts on the timeout — which
    is itself worth noting, since `probe_state`'s guard DOES have such a test and
    its dependency does not.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/spec-to-pr/test__git_common.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"

SCRIPT = PLUGIN / "skills" / "spec-to-pr" / "scripts" / "_git_common.py"

TARGETS = [DEV / "tests" / "skills" / "spec-to-pr" / "test__git_common.py"]

MUTANTS = [
    (
        # The one the killing test's docstring was written about.
        "the overlay is read and then thrown away, so a repo configured for "
        "`claude/feature/` silently gets `feature/` and its work reads as not started",
        SCRIPT,
        "    return prefix_from_text(text) or DEFAULT_BRANCH_PREFIX",
        "    return DEFAULT_BRANCH_PREFIX",
        TARGETS,
    ),
    (
        # Note `test_an_absent_overlay_is_silent` keeps PASSING under this, since
        # it fakes `is_file` by leaf name — which is exactly the "every repo reads
        # as un-configured and says nothing" failure the docstring names.
        "the overlay is looked for outside `cla.io/`, so every repo reads as "
        "un-configured and the silence is indistinguishable from having no overlay",
        SCRIPT,
        '    return repo_root() / "cla.io" / "overlays" / _BRANCH_PREFIX_OVERLAY',
        '    return repo_root() / "overlays" / _BRANCH_PREFIX_OVERLAY',
        TARGETS,
    ),
    (
        "the fallback warning moves to stdout, where it corrupts a JSON contract "
        "instead of warning anyone",
        SCRIPT,
        "        file=sys.stderr,",
        "        file=sys.stdout,",
        TARGETS,
    ),
    (
        # `TimeoutExpired` is a `SubprocessError` and NOT an `OSError`, so
        # narrowing the tuple lets a hung git escape `repo_root()` entirely.
        # The FileNotFoundError test stays green, which is what proves the two
        # fallback tests are not redundant.
        "a hung git stops being survivable, so a timeout kills the probe outright "
        "instead of falling back to cwd",
        SCRIPT,
        "    except (OSError, subprocess.SubprocessError) as e:",
        "    except OSError as e:",
        TARGETS,
    ),
    (
        "the two frontmatter degradations become indistinguishable, so a "
        "fence-less overlay is misdiagnosed as an unclosed fence",
        SCRIPT,
        '    if not lines or lines[0].strip() != "---":',
        "    if not lines:",
        TARGETS,
    ),
    (
        # The env-var twin does NOT kill this — it short-circuits before
        # `prefix_from_text` — so the two halves of the "they must agree" rule
        # are pinned by different tests and only this one is load-bearing here.
        "the prefix stops being verbatim and a trailing slash is forced back on, "
        "so a repo that configured `wip-` gets `wip-/`",
        SCRIPT,
        "                return value",
        '                return value if value.endswith("/") else value + "/"',
        TARGETS,
    ),
]
