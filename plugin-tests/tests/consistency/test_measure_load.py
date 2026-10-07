"""Tests for measure_load.py."""

from __future__ import annotations

import json
from pathlib import Path

import measure_load as ml


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _tree(tmp_path: Path) -> Path:
    """A small plugin: skill `a` names references four ways, plus decoys."""
    root = tmp_path / "plugin"
    _write(
        root / "skills" / "a" / "SKILL.md",
        "---\nname: a\ndescription: \"one two three\"\n"
        "metadata:\n  description: nested decoy words here\n---\n"
        "Read `references/x.md` first.\n"
        "See `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/s.md`.\n"
        "Also `_shared/references/t.md` and `skills/b/SKILL.md`.\n"
        "Facts live in `cla.io/project-facts.md`; any `skills/<name>/SKILL.md`.\n"
        "Never `../../../outside/references/o.md`.\n",
    )
    _write(root / "skills" / "a" / "references" / "x.md", "x words here `references/y.md`\n")
    _write(root / "skills" / "a" / "references" / "y.md", "y\n")
    _write(root / "skills" / "_shared" / "references" / "s.md", "s s\n")
    _write(root / "skills" / "_shared" / "references" / "t.md", "t t t\n")
    _write(
        root / "skills" / "b" / "SKILL.md",
        "---\nname: b\ndescription: four five\ndisable-model-invocation: true\n---\n"
        "`references/z.md`\n",
    )
    _write(root / "skills" / "b" / "references" / "z.md", "z\n")
    _write(root / "agents" / "helper.md", "---\nname: helper\ndescription: six seven\n---\nbody\n")
    _write(root / "output-styles" / "S.md", "---\nname: S\n---\nalpha beta gamma\n")
    _write(tmp_path / "outside" / "references" / "o.md", "outside\n")
    return root


def _names(paths: set[Path]) -> set[str]:
    return {p.name for p in paths}


def test_reachable_follows_every_reference_form_transitively(tmp_path):
    """Skill-relative, `${CLAUDE_PLUGIN_ROOT}`-prefixed and bare `_shared/`
    references all resolve, and `y.md` is reached only through `x.md` — a
    resolver that took `references/y.md` relative to the plugin root, or that
    stopped at depth one, misses it."""
    root = _tree(tmp_path)
    assert _names(ml.reachable(root / "skills" / "a" / "SKILL.md", root)) == {
        "x.md", "y.md", "s.md", "t.md",
    }


def test_reachable_excludes_other_skills_and_paths_outside_the_plugin(tmp_path):
    """Another skill's SKILL.md is its own load, not this one's, and following
    it would pull `z.md` in. A `../` path escaping the plugin and a templated
    `skills/<name>/SKILL.md` (which matches as `/SKILL.md`) resolve to nothing."""
    root = _tree(tmp_path)
    names = _names(ml.reachable(root / "skills" / "a" / "SKILL.md", root))
    assert "z.md" not in names
    assert "SKILL.md" not in names
    assert "o.md" not in names


def test_session_counts_listed_descriptions_and_output_styles_only(tmp_path):
    """`b` sets `disable-model-invocation: true`, so its description is not in
    the always-loaded listing and must not be counted; the agent's is. The
    indented `description:` under `a`'s `metadata:` is not the top-level key."""
    session = ml.session_load(_tree(tmp_path))
    assert session["descriptions"] == {"a": 3, "helper": 2}
    assert session["output_styles"] == {"S.md": 3}
    assert session["total"] == 8


def test_skill_load_reports_body_and_reachable_totals(tmp_path):
    root = _tree(tmp_path)
    row = ml.skill_load(root)["a"]
    body = ml.count_words(root / "skills" / "a" / "SKILL.md")
    assert row["skill_md"] == body
    # x.md 4 words, y.md 1, s.md 2, t.md 3.
    assert row["reachable"] == body + 10
    assert set(row["references"]) == {
        "skills/a/references/x.md",
        "skills/a/references/y.md",
        "skills/_shared/references/s.md",
        "skills/_shared/references/t.md",
    }


def test_check_profiles_reports_a_missing_or_unreachable_file(tmp_path):
    """A profile is a claim about what a run reads; once the skill stops naming
    a file, or the file is gone, the claim is stale and the meter must say so."""
    root = _tree(tmp_path)
    profiles = {
        "good": ("skills/a/SKILL.md", "skills/a/references/y.md"),
        "gone": ("skills/a/SKILL.md", "skills/a/references/missing.md"),
        "unreached": ("skills/a/SKILL.md", "skills/b/references/z.md"),
        "no-skill": ("skills/c/SKILL.md",),
    }
    problems = ml.check_profiles(root, profiles)
    assert problems == [
        "gone: skills/a/references/missing.md does not exist",
        "unreached: skills/b/references/z.md is not reachable from skills/a/SKILL.md",
        "no-skill: skills/c/SKILL.md does not exist",
    ]


def test_profiles_hold_in_the_real_plugin():
    """The enforcement: every curated profile names files that exist and that
    its skill still reaches, so an edit that moves a reference fails here."""
    assert ml.check_profiles(ml.PLUGIN_ROOT) == []


def test_real_spec_to_pr_profile_is_more_than_its_skill_md():
    """Non-vacuity: the profile must actually add the references a run reads.
    A profile shrunk to SKILL.md alone would pass the check above."""
    profile = ml.profile_load(ml.PLUGIN_ROOT)["spec-to-pr"]
    files = profile["files"]
    assert "skills/review-change/references/checklist.md" in files
    assert profile["total"] > 2 * files["skills/spec-to-pr/SKILL.md"]


def test_cli_json_round_trips_and_stale_profile_exits_2(tmp_path, capsys, monkeypatch):
    root = _tree(tmp_path)
    monkeypatch.setattr(ml, "PROFILES", {"a": ("skills/a/SKILL.md", "skills/a/references/x.md")})
    assert ml.main(["--json", "--root", str(root)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert set(data) == {"session", "skills", "profiles"}
    assert data["profiles"]["a"]["total"] == data["skills"]["a"]["skill_md"] + 4

    monkeypatch.setattr(ml, "PROFILES", {"a": ("skills/a/SKILL.md", "skills/b/references/z.md")})
    assert ml.main(["--root", str(root)]) == 2
    assert "stale profile" in capsys.readouterr().err
