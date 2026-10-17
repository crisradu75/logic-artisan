"""Tests for the spec map rule of check_spec_proof.py.

A repo declares a spec map in `cla.io/project-facts.md`; the checker then reports a spec (live, or added by an open change) no map
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


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
@pytest.mark.parametrize(
    ("lines", "what", "at"),
    [
        ((ALPHA, "<!-- old links", BETA), "an HTML comment is never closed", 4),
        ((ALPHA, "```", BETA), "a code fence is never closed", 4),
    ],
)
def test_a_comment_or_fence_left_open_is_reported_where_it_began(repo, capsys, lines, what, at):
    _declare(repo, MAP)
    _write(repo, MAP, _map(*lines))
    code, out, _ = run(repo, capsys)
    assert code == 1 and f"PROBLEM spec-map: {MAP}:{at}: {what}" in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_text_after_the_closer_of_a_comment_on_its_line_is_not_a_link(repo, capsys):
    _declare(repo, MAP)
    _write(repo, MAP, _map("<!--", f"old --> {BETA}", ALPHA))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "openspec/specs/beta/spec.md is linked from no spec map" in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_top_level_fence_opened_with_indent_keeps_its_less_indented_content(repo, capsys):
    _declare(repo, MAP)
    _write(repo, MAP, _map("  ```", ALPHA, "```", BETA))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "openspec/specs/alpha/spec.md is linked from no spec map" in out
    assert "never closed" not in out and "problems: 1" in out


# requirement: spec-map / A repo declares its spec map as a fact
def test_a_lazy_continuation_line_keeps_its_list_item_open_so_the_fence_after_it_ends_with_the_item(repo, capsys):
    _write(repo, FACTS, f"- example:\nlazy text\n  ```\n  foo\n## Spec map\n- {MAP}\n## Notes\n```text\nx\n```\n")
    _write(repo, MAP, _map(ALPHA, BETA))
    code, out, err = run(repo, capsys)
    assert code == 0 and not err, out
    assert "spec map: 1 file(s) from 1 declared path(s); 2 of 2 specs linked" in out and "NOTE" not in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_laziness_ends_at_a_blank_line_a_heading_and_a_fence_but_not_at_plain_text(repo, capsys):
    _declare(repo, MAP)
    # Plain text keeps the item open: the fence after it belongs to the item and ends at the less indented link.
    _write(repo, MAP, _map("- step", "lazy text", "  ```", "  [g](specs/gamma/spec.md)", ALPHA, BETA))
    code, out, _ = run(repo, capsys)
    assert code == 0, out
    # A blank line, then plain text, ends the item: the fence is top level, so it keeps its less indented link.
    _write(repo, MAP, _map("- step", "", "para", "  ```", ALPHA, "```", BETA))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "openspec/specs/alpha/spec.md is linked from no spec map" in out
    # A heading is a new block, not a continuation.
    _write(repo, MAP, _map("- step", "text", "# Heading", "  ```", ALPHA, "```", BETA))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "openspec/specs/alpha/spec.md is linked from no spec map" in out
    assert "never closed" not in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_list_that_has_ended_does_not_make_a_later_indented_fence_a_list_fence(repo, capsys):
    _declare(repo, MAP)
    _write(repo, MAP, _map("- item", "", "A paragraph.", "", "  ```", ALPHA, "```", BETA))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "openspec/specs/alpha/spec.md is linked from no spec map" in out
    assert "never closed" not in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_fence_opened_on_the_line_of_a_list_marker_is_a_fence_in_that_item(repo, capsys):
    _declare(repo, MAP)
    _write(repo, MAP, _map("- ```text", f"  {ALPHA}", "  ```", BETA))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "openspec/specs/alpha/spec.md is linked from no spec map" in out
    assert "never closed" not in out and "problems: 1" in out
    # The item's content starts after the marker: a line indented less than that ends the item and its fence.
    _write(repo, MAP, _map("- ```text", f" {ALPHA}", BETA))
    code, out, _ = run(repo, capsys)
    assert code == 0, out
    # The item ends the fence: an unclosed one is cut at the first less indented line.
    _write(repo, MAP, _map("1. step", "   ```", "   [g](specs/gamma/spec.md)", ALPHA, BETA))
    code, out, _ = run(repo, capsys)
    assert code == 0, out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_line_that_begins_with_a_comment_is_all_raw_html_even_when_it_closes_on_that_line(repo, capsys):
    _declare(repo, MAP)
    _write(repo, MAP, _map(f"<!-- old --> {ALPHA}", BETA))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "openspec/specs/alpha/spec.md is linked from no spec map" in out
    assert "never closed" not in out and "problems: 1" in out
    # A comment in the middle of a line is inline HTML: a link after it is still a link.
    _write(repo, MAP, _map(f"text <!-- old --> {ALPHA}", BETA))
    code, out, _ = run(repo, capsys)
    assert code == 0, out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_fence_inside_a_list_item_is_a_fence_and_a_deeper_run_inside_it_is_content(repo, capsys):
    _declare(repo, MAP)
    _write(repo, MAP, _map("1. Step", "    ```", f"    {ALPHA}", "    ```", BETA))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "openspec/specs/alpha/spec.md is linked from no spec map" in out
    assert "specs/beta/spec.md is linked" not in out and "never closed" not in out
    _write(repo, MAP, _map("```", "        ```", ALPHA, "```", BETA))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "openspec/specs/alpha/spec.md is linked from no spec map" in out
    assert "never closed" not in out


# requirement: spec-map / A repo declares its spec map as a fact
def test_a_fence_of_the_other_character_quoted_in_the_facts_file_does_not_hide_the_heading(repo, capsys):
    _write(repo, FACTS, f"~~~\n```\n~~~\n\n## Spec map\n\n- {MAP}\n")
    _write(repo, MAP, _map(ALPHA, BETA))
    code, out, _ = run(repo, capsys)
    assert code == 0, out
    assert "spec map: 1 file(s) from 1 declared path(s); 2 of 2 specs linked" in out


# requirement: spec-map / A repo declares its spec map as a fact
def test_a_fence_never_closed_above_the_heading_exits_2_but_one_with_no_heading_after_it_is_quiet(repo, capsys):
    _write(repo, FACTS, f"```\n\n## Spec map\n\n- {MAP}\n")
    code, out, err = run(repo, capsys)
    assert code == 2 and f"{FACTS}:1: a code fence is never closed" in err and "line 3" in err and not out
    _write(repo, FACTS, "```\n\nnotes only\n")
    code, out, err = run(repo, capsys)
    assert code == 0 and "spec map" not in out.lower() and not err


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_comment_marker_quoted_in_a_code_span_or_a_fence_opens_nothing(repo, capsys):
    _declare(repo, MAP)
    _write(repo, MAP, _map("Write `<!--` to open a comment.", "```html", "<!--", "```", ALPHA, BETA))
    code, out, _ = run(repo, capsys)
    assert code == 0, out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_fence_closes_only_on_a_bare_line_and_a_one_line_triple_backtick_span_opens_none(repo, capsys):
    _declare(repo, MAP)
    _write(repo, MAP, _map("```", "```js", ALPHA, "```", BETA))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "openspec/specs/alpha/spec.md is linked from no spec map" in out
    _write(repo, MAP, _map("```x```", ALPHA, BETA))
    code, out, _ = run(repo, capsys)
    assert code == 0, out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_link_with_one_dot_dot_too_many_is_dangling_and_a_file_beside_the_specs_is_not(repo, capsys):
    _declare(repo, "docs/map.md")
    _write(repo, "openspec/specs/README.md", "readme\n")
    _write(
        repo,
        "docs/map.md",
        _map(
            "- [alpha](../openspec/specs/alpha/spec.md) [beta](../openspec/specs/beta/spec.md)",
            "- [readme](../openspec/specs/README.md)",
            "- [too far](../../openspec/specs/alpha/spec.md)",
        ),
    )
    code, out, _ = run(repo, capsys)
    assert code == 1
    assert "docs/map.md:5: link '../../openspec/specs/alpha/spec.md' points at no spec" in out
    assert "README" not in out and "problems: 1" in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_spec_held_live_and_by_an_active_change_is_named_by_its_live_file(repo, capsys):
    _declare(repo, MAP)
    _write(repo, "openspec/changes/c1/specs/alpha/spec.md", GAMMA_DELTA.replace("Requirement: G", "Requirement: A2"))
    _write(repo, "tests/test_a2.py", _marker("alpha", "A2"))
    _write(repo, MAP, _map(BETA))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "openspec/specs/alpha/spec.md is linked from no spec map" in out
    assert "changes/c1" not in out


# requirement: spec-map / A repo declares its spec map as a fact
def test_a_star_stays_inside_one_folder_and_a_double_star_crosses_folders(repo, capsys):
    _declare(repo, "docs/*.md", "wiki/**/map.md", "notes/**")
    _write(repo, "notes/deep/x.md", _map("nothing"))
    _write(repo, "docs/top.md", _map(ALPHA.replace("specs/", "../openspec/specs/")))
    _write(repo, "docs/deep/other.md", _map(BETA.replace("specs/", "../../openspec/specs/")))
    _write(repo, "wiki/map.md", _map("nothing"))
    _write(repo, "wiki/a/b/map.md", _map("nothing"))
    code, out, _ = run(repo, capsys)
    assert code == 1
    assert "spec map: 4 file(s) from 3 declared path(s); 1 of 2 specs linked" in out
    assert "openspec/specs/beta/spec.md is linked from no spec map" in out


# requirement: spec-map / A repo declares its spec map as a fact
@pytest.mark.parametrize(
    "heading",
    [
        "### Spec map", "# Spec map", "## Spec map:", "## Spec maps", "## Spec-map", "   ## Spec map", "## Spec map ##",
        "## Spec  map", "## Spec_map", "## **Spec map**", "## Spec map.", "## Spec map",
    ],
)
def test_a_heading_that_reads_as_the_declaration_in_another_form_exits_2(repo, capsys, heading):
    _write(repo, FACTS, f"{heading}\n\n- {MAP}\n")
    _write(repo, MAP, _map(ALPHA))
    code, out, err = run(repo, capsys)
    assert code == 2 and f"{FACTS}:1" in err and not out


# requirement: spec-map / A line that looks like the spec map heading is never silently ignored
def test_a_heading_shown_in_a_fenced_example_with_a_bullet_below_it_is_still_only_a_note(repo, capsys):
    _write(repo, FACTS, "## Notes\n\n```markdown\n### Spec map\n\n- openspec/spec-map.md\n```\n")
    code, out, err = run(repo, capsys)
    assert code == 0 and not err, out
    assert f"NOTE spec-map: {FACTS}:4: looks like the 'Spec map' heading but sits inside a code fence or comment" in out
    assert "PROBLEM" not in out


# requirement: spec-map / A line that looks like the spec map heading is never silently ignored
@pytest.mark.parametrize(
    ("facts", "line"),
    [
        ("- ## Spec map\n- openspec/spec-map.md\n", 1),
        ("> ## Spec map\n", 1),
        ("1. ### SPEC  MAP ###\n", 1),
        ("##Spec map\n\n- openspec/spec-map.md\n", 1),
        ("# Facts\n\nSpec map\n========\n\n- openspec/spec-map.md\n", 3),
        ("Spec map\n---\n", 1),
    ],
)
def test_a_heading_outside_any_fence_or_comment_the_scan_did_not_read_exits_2_and_names_the_line(repo, capsys, facts, line):
    _write(repo, FACTS, facts)
    code, out, err = run(repo, capsys)
    assert code == 2 and f"{FACTS}:{line}: looks like the 'Spec map' heading" in err and not out


# requirement: spec-map / A line that looks like the spec map heading is never silently ignored
@pytest.mark.parametrize(
    ("facts", "line"),
    [
        ("# Facts\n\n<!--\n## Spec map\n- openspec/spec-map.md\n-->\n", 4),
        ("# Facts\n\n```\n## Spec map\n```\n", 4),
        ("- item\n  ```\n  ## Spec map\n  ```\n", 3),
        ("# Facts\n\n```\nSpec map\n===\n```\n", 4),
    ],
)
def test_the_same_line_inside_a_fence_or_comment_is_a_note_and_never_fails_the_run(repo, capsys, facts, line):
    _write(repo, FACTS, facts)
    code, out, err = run(repo, capsys)
    assert code == 0 and not err, out
    assert f"NOTE spec-map: {FACTS}:{line}: looks like the 'Spec map' heading" in out and "PROBLEM" not in out


# requirement: spec-map / A line that looks like the spec map heading is never silently ignored
@pytest.mark.parametrize(
    "facts",
    [
        "We have no spec map yet.\n",
        "Use `## Spec map` in this file to declare it.\n",
        "## Spec map notes\n\n- anything\n",
        "Spec map\n\n- item\n",
        "Spec map\n-\n",
        "<!-- TODO: add a SPEC   MAP -->\n",
        "# Facts\n\nSpecs are mapped in spec-map.md and the map is elsewhere.\n",
    ],
)
def test_words_that_are_not_a_heading_leave_the_run_quiet(repo, capsys, facts):
    _write(repo, FACTS, facts)
    code, out, err = run(repo, capsys)
    assert code == 0 and "spec map" not in out.lower() and not err


# requirement: spec-map / A repo declares its spec map as a fact
def test_a_comment_that_ends_before_the_heading_does_not_hide_it(repo, capsys):
    _write(repo, FACTS, f"<!--\nnote\n-->\n<!-- one line -->\n\n## Spec map\n\n- {MAP}\n")
    _write(repo, MAP, _map(ALPHA, BETA))
    code, out, err = run(repo, capsys)
    assert code == 0 and not err, out
    assert "2 of 2 specs linked" in out


# requirement: spec-map / A repo declares its spec map as a fact
def test_the_backstop_does_not_run_once_a_declaration_is_read(repo, capsys):
    _write(repo, FACTS, f"# Facts\n\nSpec map\n===\n\n## Spec map\n\n- {MAP}\n")
    _write(repo, MAP, _map(ALPHA, BETA))
    code, out, err = run(repo, capsys)
    assert code == 0 and not err, out


# requirement: spec-map / A repo declares its spec map as a fact
def test_a_fence_opened_in_a_list_item_ends_with_the_item_so_the_heading_after_it_is_read(repo, capsys):
    _write(repo, FACTS, f"- example:\n  ```\n  foo\n## Spec map\n- {MAP}\n## Notes\n```text\nx\n```\n")
    _write(repo, MAP, _map(ALPHA, BETA))
    code, out, err = run(repo, capsys)
    assert code == 0 and not err, out
    assert "spec map: 1 file(s) from 1 declared path(s); 2 of 2 specs linked" in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_fence_in_a_list_item_ends_at_the_first_less_indented_line_but_not_at_a_blank_one(repo, capsys):
    _declare(repo, MAP)
    _write(repo, MAP, _map("- step", "  ```", f"  {ALPHA}", ALPHA, BETA, "```text", "x", "```"))
    code, out, _ = run(repo, capsys)
    assert code == 0, out
    _write(repo, MAP, _map("- step", "  ```", "", f"  {ALPHA}", "  ```", BETA))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "openspec/specs/alpha/spec.md is linked from no spec map" in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_this_repos_own_map_links_every_spec_and_only_specs():
    patterns = csp.read_spec_map(_REPO)
    assert patterns is not None
    specs = {}
    for p in sorted((_REPO / "openspec" / "specs").glob("*/spec.md")) + sorted((_REPO / "openspec" / "changes").glob("*/specs/*/spec.md")):
        specs.setdefault(p.parent.name, p.relative_to(_REPO).as_posix())
    problems, _ = csp.check_spec_map(_REPO, specs, patterns)
    assert problems == []


# ---- a link counts only if it renders ----


def _unlinked(out: str, name: str) -> bool:
    return f"openspec/specs/{name}/spec.md is linked from no spec map" in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
@pytest.mark.parametrize(
    "lines",
    [
        [r"- \[alpha\](specs/alpha/spec.md)", BETA],
        [r"- [alpha\](specs/alpha/spec.md)", BETA],
        ["- ![alpha](specs/alpha/spec.md)", BETA],
        # a code span holds the link, and a stray backtick elsewhere on the line must not unmask it
        ["- a `[alpha](specs/alpha/spec.md)` and a stray ` here", BETA],
        # an indented code block, after a blank line, also at the content column of a list item
        ["    [alpha](specs/alpha/spec.md)", "", BETA],
        ["- item", "", "      [alpha](specs/alpha/spec.md)", "", BETA],
        ["\t[alpha](specs/alpha/spec.md)", "", BETA],
        # a bracket pair with no opening bracket is text
        ["- alpha](specs/alpha/spec.md)", BETA],
        # a footnote definition is not a link definition, even when its text is a spec path
        ["Text[^1].", "", "[^1]: specs/alpha/spec.md", BETA],
        # link text wrapped over a blank line, or over a new list item, is two paragraphs or two items, not one link
        ["- [alpha", "", "capability](specs/alpha/spec.md)", BETA],
        ["- [alpha", "- capability](specs/alpha/spec.md)", BETA],
        # a heading, a setext underline, a quote and an indented code block each end the paragraph that an open bracket began
        ["# See [alpha", "capability](specs/alpha/spec.md)", BETA],
        ["[alpha", "===", "capability](specs/alpha/spec.md)", BETA],
        ["[alpha", "> capability](specs/alpha/spec.md)", BETA],
        # a quote line at the margin ends the list item, so the indented line after it is a code block
        ["- item", "> note", "", "    [alpha](specs/alpha/spec.md)", "", BETA],
    ],
)
def test_a_link_that_does_not_render_does_not_link_the_spec(repo, capsys, lines):
    _declare(repo, MAP)
    _write(repo, MAP, _map(*lines))
    code, out, _ = run(repo, capsys)
    assert code == 1 and _unlinked(out, "alpha") and not _unlinked(out, "beta"), out
    assert "problems: 1" in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
@pytest.mark.parametrize(
    "lines",
    [
        # a stray backtick with no partner is literal, so a link beside it renders
        ["- a stray ` here and [alpha](specs/alpha/spec.md)", BETA],
        ["- [![badge](x.png)](specs/alpha/spec.md)", BETA],
        # text a paragraph continues, and an item's own paragraph, are not code however far they are indented
        ["para", "    [alpha](specs/alpha/spec.md)", "", BETA],
        ["- item", "", "  [alpha](specs/alpha/spec.md)", "", BETA],
        ["- item", "", "    [alpha](specs/alpha/spec.md)", "", BETA],
        ["> [alpha](specs/alpha/spec.md)", "", BETA],
        ["- [a `code` label](specs/alpha/spec.md)", BETA],
        [r"- an escaped \[ bracket then [alpha](specs/alpha/spec.md)", BETA],
        # link text hard-wrapped over two lines of one paragraph or one list item is one link
        ["- [alpha", "  capability](specs/alpha/spec.md)", BETA],
        ["[alpha", "capability](specs/alpha/spec.md)", "", BETA],
        # a line that only starts like a definition (a footnote, prose, a trailing sentence) is a line with a link
        ["[^1]: see " + ALPHA, BETA],
        ["[Note]: see " + ALPHA, BETA],
        # a quote inside a list item, or an item inside a quote, does not end the item the code-block test is measured from
        ["- item", "  > note", "", "    [alpha](specs/alpha/spec.md)", "", BETA],
        ["> - item", "> lazy text", ">", ">     [alpha](specs/alpha/spec.md)", "", BETA],
        # an ordered item that does not start at 1 cannot interrupt a paragraph, so the wrapped link text goes on
        ["[alpha", "2026. capability](specs/alpha/spec.md)", "", BETA],
        # a title that runs onto the next line is still part of the definition
        ["- [alpha][a]", "", '[a]: specs/alpha/spec.md "The alpha', 'spec"', BETA],
        # an indented line right after a quoted paragraph continues it (lazily); it is not a code block
        ["> note", "    [alpha](specs/alpha/spec.md)", "", BETA],
        # a definition may carry a title
        ["- [alpha][a]", "", '[a]: specs/alpha/spec.md "The alpha spec"', BETA],
    ],
)
def test_a_link_that_renders_still_links_the_spec(repo, capsys, lines):
    _declare(repo, MAP)
    _write(repo, MAP, _map(*lines))
    code, out, _ = run(repo, capsys)
    assert code == 0, out
    assert "2 of 2 specs linked" in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_reference_definition_counts_only_when_a_link_uses_its_label(repo, capsys):
    _declare(repo, MAP)
    _write(repo, MAP, _map("- [alpha][a]", "", "[a]: specs/alpha/spec.md", "[b]: specs/beta/spec.md", "[z]: specs/zzz/spec.md"))
    code, out, _ = run(repo, capsys)
    # beta's definition is unused, so beta is unlinked; the unused one naming no spec is not a dangling link
    assert code == 1 and _unlinked(out, "beta") and not _unlinked(out, "alpha")
    assert "points at no spec" not in out and "problems: 1" in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
@pytest.mark.parametrize("use", ["- [Beta][B]", "- [b][]", "- [b]", "- [beta text][ b ]", "- ![b]", "- ![alt][b]"])
def test_each_form_of_reference_link_uses_its_label(repo, capsys, use):
    _declare(repo, MAP)
    # an image reference shows a picture, so it does not use the label as a link
    _write(repo, MAP, _map(ALPHA, "", use, "", "[b]: specs/beta/spec.md"))
    code, out, _ = run(repo, capsys)
    if use.startswith("- ![") :
        assert code == 1 and _unlinked(out, "beta")
    else:
        assert code == 0, out
        assert "2 of 2 specs linked" in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_definition_after_its_use_and_inside_a_quote_counts(repo, capsys):
    _declare(repo, MAP)
    _write(repo, MAP, _map(ALPHA, "- [beta][b]", "", "> [b]: specs/beta/spec.md"))
    code, out, _ = run(repo, capsys)
    assert code == 0, out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_only_the_first_definition_of_a_label_counts(repo, capsys):
    _declare(repo, MAP)
    _write(repo, MAP, _map("- [map][x]", "", "[x]: specs/alpha/spec.md", "[x]: specs/beta/spec.md"))
    code, out, _ = run(repo, capsys)
    assert code == 1 and _unlinked(out, "beta") and not _unlinked(out, "alpha"), out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_wrapped_link_to_a_missing_spec_is_reported_on_the_line_that_holds_its_target(repo, capsys):
    _declare(repo, MAP)
    _write(repo, MAP, _map(ALPHA, BETA, "- [gamma", "  capability](specs/gamma/spec.md)"))
    code, out, _ = run(repo, capsys)
    assert code == 1 and f"{MAP}:6: link 'specs/gamma/spec.md' points at no spec" in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_an_image_inside_a_link_does_not_link_the_spec_its_picture_names(repo, capsys):
    _declare(repo, MAP)
    _write(repo, MAP, _map("- [![pic](specs/beta/spec.md)](specs/alpha/spec.md)"))
    code, out, _ = run(repo, capsys)
    assert code == 1 and _unlinked(out, "beta") and not _unlinked(out, "alpha"), out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_problems_come_in_line_order_whether_the_link_is_inline_or_through_a_definition(repo, capsys):
    _declare(repo, MAP)
    _write(repo, MAP, _map(ALPHA, BETA, "[g]: specs/gamma/spec.md", "", "- [g][g]", "- [h](specs/hhh/spec.md)"))
    code, out, _ = run(repo, capsys)
    lines = [l.split(": link")[0] for l in out.splitlines() if "points at no spec" in l]
    assert code == 1 and lines == [f"PROBLEM spec-map: {MAP}:5", f"PROBLEM spec-map: {MAP}:8"], out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_dangling_link_through_a_used_definition_is_reported_on_the_definitions_line(repo, capsys):
    _declare(repo, MAP)
    _write(repo, MAP, _map(ALPHA, BETA, "- [g][g]", "", "[g]: specs/gamma/spec.md"))
    code, out, _ = run(repo, capsys)
    assert code == 1 and f"{MAP}:7: link 'specs/gamma/spec.md' points at no spec" in out


# ---- a map is a Markdown file ----


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_glob_that_also_matches_a_binary_file_reads_only_the_markdown_ones(repo, capsys):
    _declare(repo, "docs/*")
    _write(repo, "docs/map.md", _map(ALPHA.replace("specs/", "../openspec/specs/"), BETA.replace("specs/", "../openspec/specs/")))
    (repo / "docs" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\xff\xfe")
    (repo / "docs" / "blob.bin").write_bytes(b"\x00\x01\xff\xfe\x80")
    code, out, err = run(repo, capsys)
    assert code == 0 and not err, (out, err)
    assert "spec map: 1 file(s) from 1 declared path(s); 2 of 2 specs linked" in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_glob_that_matches_only_files_that_are_not_markdown_is_reported(repo, capsys):
    _declare(repo, "docs/*.png")
    (repo / "docs").mkdir()
    (repo / "docs" / "logo.png").write_bytes(b"\x89PNG\x00")
    code, out, err = run(repo, capsys)
    assert code == 1 and not err
    assert f"PROBLEM spec-map: declared path 'docs/*.png' in {FACTS} matches no file (only .md and .markdown files are read as maps)" in out


# ---- a setext heading in another form ----


# requirement: spec-map / A line that looks like the spec map heading is never silently ignored
@pytest.mark.parametrize(
    ("facts", "line"),
    [
        ("Spec maps\n=========\n\n- openspec/spec-map.md\n", 1),
        ("# Facts\n\n**Spec map**\n---\n\n- openspec/spec-map.md\n", 3),
        ("Spec-map\n--\n", 1),
        ("> Spec_map.\n> ===\n", 1),
    ],
)
def test_a_setext_heading_reading_as_the_declaration_in_another_form_exits_2(repo, capsys, facts, line):
    _write(repo, FACTS, facts)
    code, out, err = run(repo, capsys)
    assert code == 2 and f"{FACTS}:{line}: looks like the 'Spec map' heading" in err and not out


# requirement: spec-map / A line that looks like the spec map heading is never silently ignored
def test_a_setext_variant_beside_a_real_declaration_stays_quiet_and_in_a_fence_is_a_note(repo, capsys):
    _write(repo, FACTS, f"Spec maps\n===\n\n## Spec map\n\n- {MAP}\n")
    _write(repo, MAP, _map(ALPHA, BETA))
    assert run(repo, capsys)[0] == 0
    _write(repo, FACTS, "```\nSpec maps\n---\n```\n")
    code, out, err = run(repo, capsys)
    assert code == 0 and not err and f"NOTE spec-map: {FACTS}:2: looks like the 'Spec map' heading" in out


# ---- a link must name a file the repo lists, in the case it is listed ----


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_link_to_an_ignored_file_or_one_in_the_wrong_case_points_at_no_spec(repo, capsys):
    _write(repo, ".gitignore", "openspec/specs/alpha/ignored.md\n")
    _write(repo, "openspec/specs/alpha/ignored.md", "x\n")
    _write(repo, "openspec/specs/alpha/notes.md", "x\n")
    _declare(repo, MAP)
    _write(
        repo,
        MAP,
        _map(ALPHA, BETA, "- [ok](specs/alpha/notes.md)", "- [ign](specs/alpha/ignored.md)", "- [case](specs/alpha/NOTES.md)", "- [dir](specs/Alpha/spec.md)"),
    )
    code, out, _ = run(repo, capsys)
    assert code == 1
    problems = [l for l in out.splitlines() if l.startswith("PROBLEM")]
    assert [p.split("link ")[1].split(" points")[0] for p in problems] == [
        "'specs/alpha/ignored.md'", "'specs/alpha/NOTES.md'", "'specs/Alpha/spec.md'"
    ]


# ---- a fence inside a block quote ----


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
@pytest.mark.parametrize(
    "lines",
    [
        ["> ```", "> " + ALPHA, "> ```", BETA],
        ["> ```markdown", ">     " + ALPHA, "> ```", BETA],
        ["> > ```", "> > " + ALPHA, "> > ```", BETA],
    ],
)
def test_a_fence_in_a_block_quote_hides_the_links_in_it(repo, capsys, lines):
    _declare(repo, MAP)
    _write(repo, MAP, _map(*lines))
    code, out, _ = run(repo, capsys)
    assert code == 1 and _unlinked(out, "alpha") and not _unlinked(out, "beta"), out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
@pytest.mark.parametrize("gap", ["", "text with no marker"])
def test_a_fence_in_a_block_quote_ends_where_the_quote_does(repo, capsys, gap):
    _declare(repo, MAP)
    _write(repo, MAP, _map("> ```", "> code", gap, "- " + ALPHA, BETA))
    code, out, err = run(repo, capsys)
    assert code == 0, out  # the quote took its fence with it, so alpha's link after them renders
    assert "2 of 2 specs linked" in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_fence_left_open_in_a_block_quote_is_reported_where_it_began(repo, capsys):
    _declare(repo, MAP)
    _write(repo, MAP, _map(ALPHA, BETA, "> ```", "> " + ALPHA))
    code, out, _ = run(repo, capsys)
    assert code == 1 and f"PROBLEM spec-map: {MAP}:5: a code fence is never closed" in out


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_quote_markers_inside_a_fence_that_was_not_opened_in_a_quote_are_content(repo, capsys):
    _declare(repo, MAP)
    _write(repo, MAP, _map("```", "> ```", ALPHA, "```", BETA))
    code, out, _ = run(repo, capsys)
    assert code == 1 and _unlinked(out, "alpha") and not _unlinked(out, "beta"), out


# ---- a spec a change in progress removes ----

REMOVE_BETA = (
    "## REMOVED Requirements\n\n### Requirement: beta rule\n\n**Reason**: folded elsewhere.\n**Migration**: None.\n"
)


def _remove_beta(repo: Path, delta: str = REMOVE_BETA, change: str = "c1") -> None:
    _write(repo, f"openspec/changes/{change}/specs/beta/spec.md", delta)


# requirement: spec-map / A spec a change in progress removes is gone for the map rule
def test_a_spec_a_change_removes_whole_needs_no_map_link(repo, capsys):
    _declare(repo, MAP)
    _remove_beta(repo)
    _write(repo, MAP, _map(ALPHA))
    code, out, _ = run(repo, capsys)
    assert code == 0, out
    assert "spec map: 1 file(s) from 1 declared path(s); 1 of 1 specs linked" in out


# requirement: spec-map / A spec a change in progress removes is gone for the map rule
def test_a_map_link_to_a_spec_a_change_removes_whole_is_reported(repo, capsys):
    _declare(repo, MAP)
    _remove_beta(repo)
    _write(repo, MAP, _map(ALPHA, BETA))
    code, out, _ = run(repo, capsys)
    assert code == 1
    assert f"PROBLEM spec-map: {MAP}:4: link 'specs/beta/spec.md' points at spec beta, which change c1 removes" in out
    assert "problems: 1" in out


# requirement: spec-map / A spec a change in progress removes is gone for the map rule
def test_a_spec_a_change_trims_is_still_live_for_the_map_rule(repo, capsys):
    # beta holds two requirements and the change removes one of them
    two = _spec("beta", "beta rule") + "\n### Requirement: beta other\n\nSHALL.\n\n#### Scenario: S2\n\n- **WHEN** x\n- **THEN** y\n"
    _write(repo, "openspec/specs/beta/spec.md", two)
    _write(repo, "tests/test_beta_other.py", _marker("beta", "beta other"))
    _declare(repo, MAP)
    _remove_beta(repo)
    _write(repo, MAP, _map(ALPHA))
    code, out, _ = run(repo, capsys)
    assert code == 1 and _unlinked(out, "beta"), out


# requirement: spec-map / A spec a change in progress removes is gone for the map rule
def test_a_spec_a_change_rewrites_is_still_live_for_the_map_rule(repo, capsys):
    # every requirement removed and one added back under a new heading
    added = "\n## ADDED Requirements\n\n### Requirement: beta again\n\nSHALL.\n\n#### Scenario: S\n\n- **WHEN** x\n- **THEN** y\n"
    _declare(repo, MAP)
    _remove_beta(repo, REMOVE_BETA + added)
    _write(repo, "tests/test_beta_again.py", _marker("beta", "beta again"))
    _write(repo, MAP, _map(ALPHA))
    code, out, _ = run(repo, capsys)
    assert code == 1 and _unlinked(out, "beta"), out


# requirement: spec-map / A spec a change in progress removes is gone for the map rule
def test_a_spec_with_no_requirement_is_never_read_as_removed_whole(repo, capsys):
    # Nothing to remove is not everything removed: the empty spec stays in the map rule and is reported as before.
    _write(repo, "openspec/specs/beta/spec.md", "# beta Specification\n\n## Purpose\n\nx\n\n## Requirements\n")
    _declare(repo, MAP)
    _remove_beta(repo)
    _write(repo, MAP, _map(ALPHA))
    code, out, _ = run(repo, capsys)
    assert code == 1 and _unlinked(out, "beta"), out


# requirement: spec-map / A spec a change in progress removes is gone for the map rule
def test_another_change_that_modifies_the_spec_keeps_it_live(repo, capsys):
    _declare(repo, MAP)
    _remove_beta(repo)
    _write(repo, "openspec/changes/c2/specs/beta/spec.md", "## MODIFIED Requirements\n\n### Requirement: beta rule\n\nSHALL, again.\n\n#### Scenario: Case\n\n- **WHEN** x\n- **THEN** it works\n")
    _write(repo, "tests/test_beta3.py", _marker("beta", "beta rule"))
    _write(repo, MAP, _map(ALPHA))
    code, out, _ = run(repo, capsys)
    assert code == 1 and _unlinked(out, "beta"), out


# ---- corners of the fence tracker and the code spans that run over lines ----


def _read(*lines: str) -> tuple[list[str], list[tuple[int, str]]]:
    links, issues = csp.map_links("\n".join(lines) + "\n")
    return [target for _, target in links], issues


# The three run-on lines below each belong to the list item before them. The fence after the item is then a
# fence in the item: it ends at the first line less indented than itself, and the next fence is never closed.
# A tracker that wrongly ended the item would read the first fence as top level and the second as closed.
_ITEM_FENCES = ("  ```", "[hidden](a.md)", "  ```", "[shown](b.md)")


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
@pytest.mark.parametrize("run_on", ["```x``` more text", "2026. more text"])
def test_a_run_on_line_that_only_looks_like_a_fence_or_a_list_marker_keeps_its_item_open(run_on):
    targets, issues = _read("- step", run_on, *_ITEM_FENCES)
    assert targets == ["a.md"] and [i[1] for i in issues] == ["a code fence is never closed, so the rest of the map is not read"]


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_an_html_comment_right_after_an_items_paragraph_ends_the_item():
    # The item is over, so the fence is top level: it keeps its less indented link, and the second one closes it.
    targets, issues = _read("- step", "<!-- note -->", *_ITEM_FENCES)
    assert targets == ["b.md"] and not issues


# requirement: spec-map / A repo declares its spec map as a fact
def test_an_html_comment_right_after_an_items_paragraph_ends_the_item_in_the_facts_file(tmp_path):
    root = tmp_path / "r"
    # With the item over, the fence is top level and never closed, and it swallows the heading after it.
    _write(root, FACTS, "- step\n<!-- note -->\n  ```\n## Spec map\n- openspec/spec-map.md\n")
    with pytest.raises(csp.CheckerError, match="never closed"):
        csp.read_spec_map(root)


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_fence_opened_two_quotes_deep_ends_when_the_inner_quote_does():
    targets, issues = _read("> > ```", "> > [hidden](a.md)", "> [shown](b.md)")
    assert targets == ["b.md"] and not issues


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_code_span_left_open_on_one_line_and_closed_on_the_next_hides_the_link_between():
    assert _read("a ` [x](a.md)", "b ` c")[0] == []
    assert _read("a ``` [x](a.md)", "text", "b ``` c")[0] == []


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_code_span_closed_on_the_next_line_does_not_hide_the_link_after_it():
    # The first backtick pairs with the one on the line below, so the pair after it on that line is not a span.
    assert _read("a ` b", "c ` [x](a.md) ` d")[0] == ["a.md"]


# requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere
def test_a_stray_backtick_no_later_line_of_the_paragraph_closes_hides_nothing():
    assert _read("a ` [x](a.md)", "", "b ` c")[0] == ["a.md"]
    assert _read("a ` [x](a.md)", "# heading `", "text")[0] == ["a.md"]
    assert _read("a ` [x](a.md)", "- item `")[0] == ["a.md"]
    assert _read("a ` [x](a.md)", "b `` c")[0] == ["a.md"]
