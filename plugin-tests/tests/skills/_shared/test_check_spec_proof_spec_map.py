"""Tests for the spec map rule of check_spec_proof.py.

A repo declares a spec map in `cla.io/project-facts.md`; the checker then reports a live spec no map
file links, a map link to no live spec, and a declared path that matches no file. With no
declaration it prints nothing about a map. Each test builds a throwaway git repo under tmp_path.
The marker strings the fixtures write are built as single-line f-strings so no line of THIS file
starts with a comment token followed by a marker, which the checker would read as one.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[4]
_SCRIPT = _REPO / ".claude" / "plugins" / "cla" / "skills" / "_shared" / "scripts" / "check_spec_proof.py"
_spec = importlib.util.spec_from_file_location("check_spec_proof_spec_map", _SCRIPT)
csp = importlib.util.module_from_spec(_spec)
sys.modules["check_spec_proof_spec_map"] = csp
_spec.loader.exec_module(csp)

FACTS = "cla.io/project-facts.md"
MAP = "openspec/spec-map.md"
ALPHA = "[alpha](specs/alpha/spec.md)"
BETA = "[beta](specs/beta/spec.md)"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


def _spec(name: str, heading: str) -> str:
    return (
        f"# {name} Specification\n\n## Purpose\n\nSomething.\n\n## Requirements\n\n### Requirement: {heading}\n\n"
        "SHALL.\n\n#### Scenario: Case\n\n- **WHEN** x\n- **THEN** it works\n"
    )


def _marker(spec: str, heading: str) -> str:
    return f"# requirement: {spec} / {heading}\ndef test_x():\n    pass\n"


@pytest.fixture
def repo(tmp_path: Path):
    """A repo on branch main with two proven live specs, alpha and beta, and no spec map."""
    root = tmp_path / "r"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "commit.gpgsign", "false")
    for name in ("alpha", "beta"):
        _write(root, f"openspec/specs/{name}/spec.md", _spec(name, f"{name} rule"))
        _write(root, f"tests/test_{name}.py", _marker(name, f"{name} rule"))
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    _git(root, "checkout", "-q", "-b", "feat")
    return root


def run(root: Path, capsys) -> tuple[int, str, str]:
    code = csp.main(["--root", str(root), "--base", "main"])
    cap = capsys.readouterr()
    return code, cap.out, cap.err


def _declare(root: Path, *paths: str) -> None:
    _write(root, FACTS, "## Spec map\n\n" + "".join(f"- {p}\n" for p in paths))


def _map(*lines: str) -> str:
    return "# Spec map\n\n" + "\n".join(lines) + "\n"


# requirement: spec-map / A repo declares its spec map as a fact
@pytest.mark.parametrize("facts", [None, "- Test proof granularity: requirement\n", "# Facts\n\n## Other\n\n- openspec/spec-map.md\n"])
def test_no_declaration_means_no_map_and_no_output(repo, capsys, facts):
    # Two live specs and no file links either: with no declaration that is clean, and silent.
    if facts is not None:
        _write(repo, FACTS, facts)
    code, out, err = run(repo, capsys)
    assert code == 0, out
    assert "spec map" not in out.lower() and "spec-map" not in out and not err


# requirement: spec-map / A repo declares its spec map as a fact
def test_a_glob_declares_every_file_it_matches_in_any_layout(repo, capsys):
    _declare(repo, "docs/products/*/overview.md")
    _write(repo, "docs/products/a/overview.md", _map("- [alpha](../../../openspec/specs/alpha/spec.md)"))
    _write(repo, "docs/products/b/overview.md", _map("- [beta](../../../openspec/specs/beta/spec.md)"))
    code, out, _ = run(repo, capsys)
    assert code == 0, out
    assert "spec map: 2 file(s) from 1 declared path(s); 2 of 2 specs linked" in out


# requirement: spec-map / A repo declares its spec map as a fact
@pytest.mark.parametrize(
    ("facts", "where"),
    [
        ("## Spec map\n", f"{FACTS}:1"),
        ("## Spec map\n\n## Other\n\n- x.md\n", f"{FACTS}:1"),
        ("# Facts\n\n## Spec map\n\nopenspec/spec-map.md\n", f"{FACTS}:5"),
        ("## Spec map\n\n- a.md\n\n## Spec map\n\n- b.md\n", "lines 1, 5"),
    ],
)
def test_a_declaration_that_cannot_be_read_exits_2_and_names_the_line(repo, capsys, facts, where):
    _write(repo, FACTS, facts)
    code, out, err = run(repo, capsys)
    assert code == 2 and where in err and not out


# requirement: spec-map / A repo declares its spec map as a fact
def test_bullet_forms_and_the_end_of_the_section(repo, capsys):
    _write(
        repo,
        FACTS,
        "## Spec map\n\n<!-- one path per bullet -->\n- `openspec/spec-map.md` - the map\n- ./openspec\\spec-map.md\n\n## Other\n\n- not-a-map.md\n",
    )
    _write(repo, MAP, _map(ALPHA, BETA))
    code, out, _ = run(repo, capsys)
    assert code == 0, out
    assert "spec map: 1 file(s) from 2 declared path(s); 2 of 2 specs linked" in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_live_spec_no_map_file_links_is_reported(repo, capsys):
    _declare(repo, MAP)
    _write(repo, MAP, _map(ALPHA))
    code, out, _ = run(repo, capsys)
    assert code == 1
    assert "PROBLEM spec-map: openspec/specs/beta/spec.md is linked from no spec map" in out
    assert out.count("linked from no spec map") == 1 and "problems: 1" in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_map_link_to_a_missing_spec_is_reported_with_its_file_and_line(repo, capsys):
    _declare(repo, MAP)
    _write(repo, MAP, _map(ALPHA, BETA, "- [gamma](specs/gamma/spec.md)"))
    code, out, _ = run(repo, capsys)
    assert code == 1
    assert f"PROBLEM spec-map: {MAP}:5: link 'specs/gamma/spec.md' points at no spec" in out
    assert "problems: 1" in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_mistyped_link_into_the_specs_folder_is_dangling_but_a_real_file_there_is_not(repo, capsys):
    _declare(repo, MAP)
    _write(repo, "openspec/specs/alpha/notes.md", "notes\n")
    _write(repo, MAP, _map(ALPHA, BETA, "- [typo](specs/alpha/specs.md)", "- [notes](specs/alpha/notes.md)"))
    code, out, _ = run(repo, capsys)
    assert code == 1
    assert f"{MAP}:5: link 'specs/alpha/specs.md' points at no spec" in out
    assert "notes.md" not in out and "problems: 1" in out


GAMMA_DELTA = "## ADDED Requirements\n\n### Requirement: G\n\nSHALL.\n\n#### Scenario: S\n\n- **WHEN** x\n- **THEN** y\n"


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_spec_an_active_change_adds_must_be_linked_and_may_be_linked_before_it_is_archived(repo, capsys):
    _declare(repo, MAP)
    _write(repo, "openspec/changes/c1/specs/gamma/spec.md", GAMMA_DELTA)
    _write(repo, "tests/test_gamma.py", _marker("gamma", "G"))
    _write(repo, MAP, _map(ALPHA, BETA))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "openspec/changes/c1/specs/gamma/spec.md is linked from no spec map" in out
    _write(repo, MAP, _map(ALPHA, BETA, "- [gamma](specs/gamma/spec.md)"))
    code, out, _ = run(repo, capsys)
    assert code == 0, out
    assert "3 of 3 specs linked" in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_declared_path_that_matches_no_file_is_reported_once_and_not_per_spec(repo, capsys):
    _declare(repo, "nowhere/*.md")
    code, out, _ = run(repo, capsys)
    assert code == 1
    assert f"PROBLEM spec-map: declared path 'nowhere/*.md' in {FACTS} matches no file" in out
    assert "linked from no spec map" not in out and "problems: 1" in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_missing_second_path_is_reported_while_the_first_is_still_checked(repo, capsys):
    _declare(repo, MAP, "nowhere.md")
    _write(repo, MAP, _map(ALPHA))
    code, out, _ = run(repo, capsys)
    assert code == 1
    assert "declared path 'nowhere.md'" in out and "openspec/specs/beta/spec.md is linked from no spec map" in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_map_file_the_repo_ignores_is_not_a_map(repo, capsys):
    _write(repo, ".gitignore", "docs/\n")
    _declare(repo, "docs/map.md")
    _write(repo, "docs/map.md", _map(ALPHA, BETA))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "declared path 'docs/map.md'" in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_what_counts_as_a_link(repo, capsys):
    _declare(repo, "docs/map.md")
    _write(
        repo,
        "docs/map.md",
        _map(
            "- [alpha](../openspec/specs/alpha/spec.md#some-heading)",
            "- [beta][b]",
            "",
            "[b]: /openspec/specs/beta/",
            "- [site](https://example.com/openspec/specs/zzz/spec.md) and [readme](../README.md)",
            "- [outside](../../openspec/specs/zzz/spec.md)",
            "- `[code](../openspec/specs/zzz/spec.md)`",
            "",
            "```",
            "[fenced](../openspec/specs/zzz/spec.md)",
            "```",
        ),
    )
    code, out, _ = run(repo, capsys)
    assert code == 0, out
    assert "2 of 2 specs linked" in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_link_inside_a_code_fence_does_not_link_the_spec(repo, capsys):
    _declare(repo, MAP)
    _write(repo, MAP, _map("```", ALPHA, "```", BETA))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "openspec/specs/alpha/spec.md is linked from no spec map" in out
    assert "specs/beta/spec.md is linked" not in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_shorter_fence_quoted_inside_a_longer_one_does_not_end_it(repo, capsys):
    _declare(repo, MAP)
    _write(repo, MAP, _map("````markdown", "```", ALPHA, "```", "````", BETA))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "openspec/specs/alpha/spec.md is linked from no spec map" in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_fence_of_one_character_is_not_closed_by_the_other(repo, capsys):
    _declare(repo, MAP)
    _write(repo, MAP, _map("~~~", "```", ALPHA, "~~~", BETA))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "openspec/specs/alpha/spec.md is linked from no spec map" in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
@pytest.mark.parametrize("comment", ["<!-- {a} -->", "<!--\n{a}\n-->"])
def test_a_link_inside_an_html_comment_does_not_link_the_spec(repo, capsys, comment):
    _declare(repo, MAP)
    _write(repo, MAP, _map(ALPHA, comment.format(a=BETA)))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "openspec/specs/beta/spec.md is linked from no spec map" in out
    assert "alpha/spec.md is linked" not in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_line_number_after_a_multi_line_comment_still_points_at_the_line(repo, capsys):
    _declare(repo, MAP)
    _write(repo, MAP, _map(ALPHA, BETA, "<!--", "x", "-->", "- [gamma](specs/gamma/spec.md)"))
    code, out, _ = run(repo, capsys)
    assert code == 1 and f"{MAP}:8: link 'specs/gamma/spec.md'" in out


# requirement: spec-map / A repo declares its spec map as a fact
def test_a_star_stays_inside_one_folder_and_a_double_star_crosses_folders(repo, capsys):
    _declare(repo, "docs/*.md", "wiki/**/map.md")
    _write(repo, "docs/top.md", _map(ALPHA.replace("specs/", "../openspec/specs/")))
    _write(repo, "docs/deep/other.md", _map(BETA.replace("specs/", "../../openspec/specs/")))
    _write(repo, "wiki/map.md", _map("nothing"))
    _write(repo, "wiki/a/b/map.md", _map("nothing"))
    code, out, _ = run(repo, capsys)
    assert code == 1
    assert "spec map: 3 file(s) from 2 declared path(s); 1 of 2 specs linked" in out
    assert "openspec/specs/beta/spec.md is linked from no spec map" in out


# requirement: spec-map / A repo declares its spec map as a fact
@pytest.mark.parametrize("heading", ["### Spec map", "# Spec map", "## Spec map:", "## Spec maps", "## Spec-map", "   ## Spec map", "## Spec map ##"])
def test_a_heading_that_reads_as_the_declaration_in_another_form_exits_2(repo, capsys, heading):
    _write(repo, FACTS, f"{heading}\n\n- {MAP}\n")
    _write(repo, MAP, _map(ALPHA))
    code, out, err = run(repo, capsys)
    assert code == 2 and f"{FACTS}:1" in err and not out


# requirement: spec-map / A repo declares its spec map as a fact
def test_a_heading_that_only_mentions_the_map_is_not_a_declaration(repo, capsys):
    _write(repo, FACTS, "## Spec map scaffold notes\n\n- anything\n")
    code, out, err = run(repo, capsys)
    assert code == 0 and "spec map" not in out.lower() and not err


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_this_repos_own_map_links_every_spec_and_only_specs():
    patterns = csp.read_spec_map(_REPO)
    assert patterns is not None
    specs = {}
    for p in sorted((_REPO / "openspec" / "specs").glob("*/spec.md")) + sorted((_REPO / "openspec" / "changes").glob("*/specs/*/spec.md")):
        specs.setdefault(p.parent.name, p.relative_to(_REPO).as_posix())
    problems, _ = csp.check_spec_map(_REPO, specs, patterns)
    assert problems == []
