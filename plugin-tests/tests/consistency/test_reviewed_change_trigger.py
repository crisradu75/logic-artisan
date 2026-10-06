"""spec-to-pr skips its checklist pass on two commit subjects that multi-spec writes.

The skip keys on the subject of the last commit touching a change directory
(`spec-to-pr/SKILL.md`, Review): multi-spec's review-fix commit, or the
squash-merge form of multi-spec's PR title. Both subjects are composed in
multi-spec's own references — the commit in `review-gate.md`, the PR title in
`phases.md`. If either side rewords its subject, the other still reads fine and
the skip silently stops firing, or fires on a subject nothing writes.

Scope, stated narrowly: this pins that the subjects agree across the files. It
does not exercise the skip, which is prose the orchestrator runs.
"""

from __future__ import annotations

from pathlib import Path

_SKILLS = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "skills"
_SPEC_TO_PR = _SKILLS / "spec-to-pr" / "SKILL.md"
_REVIEW_GATE = _SKILLS / "multi-spec" / "references" / "review-gate.md"
_PHASES = _SKILLS / "multi-spec" / "references" / "phases.md"

# What multi-spec writes, as the reader of the subject sees it.
_REVIEW_FIX = "docs(openspec): apply review fixes to <slug> proposals"
_PR_TITLE = "docs(openspec): <N> <slug> change proposals"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_multi_spec_writes_the_review_fix_subject():
    # review-gate.md names the batch `<batch-slug>`; the reader abbreviates it.
    assert 'git commit -m "docs(openspec): apply review fixes to <batch-slug> proposals"' in _read(
        _REVIEW_GATE
    )


def test_multi_spec_titles_its_pr_with_the_squash_subject():
    assert 'gh pr create --title "docs(openspec): <N> <batch-slug> change proposals"' in _read(_PHASES)


def test_spec_to_pr_keys_on_both_subjects():
    text = _read(_SPEC_TO_PR)
    assert f"`{_REVIEW_FIX}`" in text
    assert f"`{_PR_TITLE} (#<pr>)`" in text


def test_spec_to_pr_checks_the_squashed_pr_for_a_later_edit():
    text = _read(_SPEC_TO_PR)
    assert "gh pr view <pr> --json commits" in text
    assert "starts with `docs(openspec): `" in text
