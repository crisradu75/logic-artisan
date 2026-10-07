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
    _write(root / "skills" / "a" / "references" / "x.md", "x words `references/y.md` [w](w.md)\n")
    _write(root / "skills" / "a" / "references" / "y.md", "y\n")
    _write(root / "skills" / "a" / "references" / "w.md", "w w\n")
    _write(root / "skills" / "_shared" / "references" / "s.md", "s s\n")
    _write(root / "skills" / "_shared" / "references" / "t.md", "t t t\n")
    _write(
        root / "skills" / "b" / "SKILL.md",
        "---\nname: b\ndescription: four five\ndisable-model-invocation: true\n---\n"
        "`references/z.md`\n",
    )
    _write(root / "skills" / "b" / "references" / "z.md", "z\n")
    _write(
        root / "skills" / "c" / "SKILL.md",
        "---\nname: c\ndescription: eight nine\n"
        "disable-model-invocation: \"yes\"  # merges PRs unattended\n---\n",
    )
    _write(root / "agents" / "helper.md", "---\nname: helper\ndescription: six seven\n---\nbody\n")
    _write(root / "agents" / "other.md", "---\ndescription: ten\n---\nbody\n")
    _write(root / "output-styles" / "S.md", "---\nname: S\nforce-for-plugin: true\n---\nalpha beta gamma\n")
    _write(root / "output-styles" / "Opt.md", "---\nname: Opt\n---\nnot paid every session\n")
    _write(tmp_path / "outside" / "references" / "o.md", "outside\n")
    return root


def _names(paths: set[Path]) -> set[str]:
    return {p.name for p in paths}


def test_reachable_follows_every_reference_form_transitively(tmp_path):
    """Skill-relative, `${CLAUDE_PLUGIN_ROOT}`-prefixed and bare `_shared/`
    references all resolve. `y.md` and `w.md` are reached only through `x.md`,
    and `w.md` only as a bare sibling name in a markdown link — a resolver that
    stopped at depth one, or that never looked beside the naming file, misses
    them."""
    root = _tree(tmp_path)
    assert _names(ml.reachable(root / "skills" / "a" / "SKILL.md", root)) == {
        "x.md", "y.md", "w.md", "s.md", "t.md",
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


def test_session_counts_listed_descriptions_and_forced_styles_only(tmp_path):
    """`b` and `c` both opt out of model invocation, `c` spelled the way YAML
    also reads as true, with an inline comment; neither is listed. The indented
    `description:` under `a`'s `metadata:` is not the top-level key. Two agents,
    one without `name:`, are keyed by path so neither overwrites the other. The
    style without `force-for-plugin` is opt-in, so no session pays for it."""
    session = ml.session_load(_tree(tmp_path))
    assert session["descriptions"] == {
        "skills/a/SKILL.md": 3,
        "agents/helper.md": 2,
        "agents/other.md": 1,
    }
    assert session["output_styles"] == {"output-styles/S.md": 3}
    assert session["total"] == 9


def test_skill_load_reports_body_and_reachable_totals(tmp_path):
    root = _tree(tmp_path)
    row = ml.skill_load(root)["a"]
    body = ml.count_words(root / "skills" / "a" / "SKILL.md")
    assert row["skill_md"] == body
    # x.md 4 words, y.md 1, w.md 2, s.md 2, t.md 3.
    assert row["reachable"] == body + 12
    assert set(row["references"]) == {
        "skills/a/references/x.md",
        "skills/a/references/y.md",
        "skills/a/references/w.md",
        "skills/_shared/references/s.md",
        "skills/_shared/references/t.md",
    }


def test_check_profiles_needs_a_direct_pointer_not_reachability(tmp_path):
    """A profile entry claims its forcing file names it. `y.md` is reachable
    from SKILL.md through `x.md`, so a reachability check would accept it as
    forced by SKILL.md — exactly the pointer deletion the check exists to see."""
    root = _tree(tmp_path)
    sk, x, y = "skills/a/SKILL.md", "skills/a/references/x.md", "skills/a/references/y.md"
    profiles = {
        "good": {sk: None, x: sk, y: x},
        "indirect": {sk: None, y: sk},
        "gone": {sk: None, "skills/a/references/missing.md": sk},
        "outsider": {sk: None, y: x},
        "no-skill": {"skills/q/SKILL.md": None},
    }
    assert ml.check_profiles(root, profiles) == [
        f"indirect: {sk} no longer names {y}",
        "gone: skills/a/references/missing.md does not exist",
        f"outsider: {y} is forced by {x}, which is not in the profile",
        "no-skill: skills/q/SKILL.md does not exist",
    ]


def test_profiles_hold_in_the_real_plugin():
    """The enforcement: every curated profile entry is still named directly by
    the file it says forces the read, so deleting a pointer fails here."""
    assert ml.check_profiles(ml.PLUGIN_ROOT) == []


def test_real_spec_to_pr_profile_is_more_than_its_skill_md():
    """Non-vacuity: the profile must actually add the references a run reads.
    A profile shrunk to SKILL.md alone would pass the check above."""
    profile = ml.profile_load(ml.PLUGIN_ROOT)["spec-to-pr"]
    files = profile["files"]
    assert "skills/review-change/references/checklist.md" in files
    assert profile["total"] > 2 * files["skills/spec-to-pr/SKILL.md"]


def test_relative_root_measures_the_same_as_absolute(tmp_path, monkeypatch):
    """A sibling checkout passed by relative path is the obvious way to take a
    "before" reading; a resolved/unresolved path mismatch used to crash it."""
    root = _tree(tmp_path)
    monkeypatch.setattr(ml, "PROFILES", {})
    monkeypatch.chdir(tmp_path)
    assert ml.measure(Path("plugin")) == ml.measure(root)
    assert ml.reachable(Path("plugin/skills/a/SKILL.md"), Path("plugin")) == ml.reachable(
        root / "skills" / "a" / "SKILL.md", root
    )


def test_cli_json_round_trips_and_stale_profile_exits_2(tmp_path, capsys, monkeypatch):
    root = _tree(tmp_path)
    sk, x = "skills/a/SKILL.md", "skills/a/references/x.md"
    monkeypatch.setattr(ml, "PROFILES", {"a": {sk: None, x: sk}})
    assert ml.main(["--json", "--root", str(root)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert set(data) == {"session", "skills", "profiles"}
    assert data["profiles"]["a"]["total"] == data["skills"]["a"]["skill_md"] + 4

    monkeypatch.setattr(ml, "PROFILES", {"a": {sk: None, "skills/b/references/z.md": sk}})
    assert ml.main(["--root", str(root)]) == 2
    assert "stale profile" in capsys.readouterr().err


def test_cli_skill_breakdown_lists_references_largest_first(tmp_path, capsys, monkeypatch):
    root = _tree(tmp_path)
    sk, x = "skills/a/SKILL.md", "skills/a/references/x.md"
    monkeypatch.setattr(ml, "PROFILES", {"a": {sk: None, x: sk}})
    assert ml.main(["--skill", "a", "--root", str(root)]) == 0
    lines = capsys.readouterr().out.splitlines()
    refs = [line.split()[1] for line in lines[1:6]]
    assert refs[0] == "skills/a/references/x.md"
    assert refs[-1] == "skills/a/references/y.md"
    assert lines[6].startswith("profile: ")

    assert ml.main(["--skill", "nope", "--root", str(root)]) == 2
    assert "no such skill" in capsys.readouterr().err
