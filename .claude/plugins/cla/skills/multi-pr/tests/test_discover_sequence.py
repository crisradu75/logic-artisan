"""discover_sequence.py tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from conftest import make_change
from discover_sequence import discover, main

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "discover_sequence.py"


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(_SCRIPT), *args], capture_output=True, text=True)


def test_no_changes_dir_returns_empty(tmp_path: Path):
    result = discover(tmp_path / "openspec" / "changes")
    assert result == {
        "changes": [], "order": [], "cycle_detected": False,
        "cycle_members": [], "blocked_by_cycle": [],
    }


def test_single_change_no_prerequisites(changes_dir: Path):
    make_change(changes_dir, "add-foo")
    result = discover(changes_dir)
    assert result["order"] == ["add-foo"]
    assert result["cycle_detected"] is False
    assert result["changes"][0]["prerequisites"] == []


def test_archive_directory_is_excluded(changes_dir: Path):
    make_change(changes_dir, "add-foo")
    make_change(changes_dir, "archive")
    result = discover(changes_dir)
    assert result["order"] == ["add-foo"]


def test_directory_with_no_artifact_files_is_excluded(changes_dir: Path):
    # A stray directory (e.g. a README-only scratch dir, or a change
    # directory mid-creation before any artifact exists yet) must not be
    # mistaken for a real change.
    make_change(changes_dir, "add-foo")
    stray = changes_dir / "not-a-change"
    stray.mkdir()
    (stray / "README.md").write_text("scratch notes\n", encoding="utf-8")
    result = discover(changes_dir)
    assert [c["name"] for c in result["changes"]] == ["add-foo"]


def test_linear_dependency_via_prerequisite_text_orders_prerequisite_first(changes_dir: Path):
    make_change(changes_dir, "add-foo")
    make_change(
        changes_dir, "add-bar",
        tasks="> Prerequisite: `add-foo` merged (foo's helper exists).\n\n## 1. Stub\n",
    )
    result = discover(changes_dir)
    assert result["order"] == ["add-foo", "add-bar"]
    bar = next(c for c in result["changes"] if c["name"] == "add-bar")
    assert bar["prerequisites"] == ["add-foo"]


def test_dependency_signal_in_design_md_is_also_detected(changes_dir: Path):
    # tasks.md isn't the only source -- design.md counts equally.
    make_change(changes_dir, "add-foo")
    make_change(changes_dir, "add-bar", design="This change requires `add-foo` to already exist.\n")
    result = discover(changes_dir)
    assert result["order"] == ["add-foo", "add-bar"]


def test_prerequisite_named_in_both_proposal_and_tasks_is_not_double_counted(changes_dir: Path):
    make_change(changes_dir, "add-foo")
    make_change(
        changes_dir, "add-bar",
        proposal="## Why\nDepends on `add-foo`.\n",
        tasks="> Prerequisite: `add-foo` merged.\n",
    )
    result = discover(changes_dir)
    bar = next(c for c in result["changes"] if c["name"] == "add-bar")
    assert bar["prerequisites"] == ["add-foo"]  # not ["add-foo", "add-foo"]


def test_dependency_word_without_change_name_is_not_counted(changes_dir: Path):
    make_change(changes_dir, "add-foo")
    make_change(changes_dir, "add-bar", tasks="This depends on the weather.\n")
    result = discover(changes_dir)
    bar = next(c for c in result["changes"] if c["name"] == "add-bar")
    assert bar["prerequisites"] == []


def test_change_name_without_dependency_signal_word_is_not_counted(changes_dir: Path):
    make_change(changes_dir, "add-foo")
    make_change(changes_dir, "add-bar", tasks="See also add-foo for context.\n")
    result = discover(changes_dir)
    bar = next(c for c in result["changes"] if c["name"] == "add-bar")
    assert bar["prerequisites"] == []


def test_signal_word_after_names_referring_back_to_this_change_is_not_a_false_dependency(changes_dir: Path):
    # Regression: add-foo's own proposal can legitimately say "before X or Y
    # depend on them" (X/Y are downstream consumers of add-foo, not
    # prerequisites of it) -- the signal word "depend" here refers back to
    # THIS change, not forward to a prerequisite. Only a name appearing
    # AFTER the signal word counts; a name appearing before it (as the
    # object of a later "depend on them") must not.
    make_change(changes_dir, "add-bar")
    make_change(changes_dir, "add-baz")
    make_change(
        changes_dir,
        "add-foo",
        proposal="This lays the foundation before the ETL (`add-bar`) or the page (`add-baz`) depend on them.\n",
    )
    result = discover(changes_dir)
    foo = next(c for c in result["changes"] if c["name"] == "add-foo")
    assert foo["prerequisites"] == []
    assert result["cycle_detected"] is False


def test_signal_word_before_name_within_window_is_still_counted(changes_dir: Path):
    # The real, correct phrasing this repo's changes actually use: the
    # signal word precedes the name closely ("Depends on X being merged").
    make_change(changes_dir, "add-foo")
    make_change(changes_dir, "add-bar", tasks="Depends on `add-foo` being merged.\n")
    result = discover(changes_dir)
    bar = next(c for c in result["changes"] if c["name"] == "add-bar")
    assert bar["prerequisites"] == ["add-foo"]


def test_a_second_signal_word_later_on_the_line_gets_its_own_window(changes_dir: Path):
    # Regression: an early, incidental signal word (here "after" -- a common
    # English word) must not shadow a REAL "requires X merged" clause
    # appearing later on the same line, past the first match's window. Only
    # the line's first signal-word match was ever inspected before this fix
    # (`.search`, not `.finditer`) -- a long enough preamble between the two
    # would silently drop a genuine prerequisite.
    make_change(changes_dir, "add-real")
    padding = "x" * 130  # longer than _MAX_DEPENDENCY_WINDOW (120)
    make_change(
        changes_dir,
        "add-bar",
        tasks=f"Delivered after {padding} it requires `add-real` merged.\n",
    )
    result = discover(changes_dir)
    bar = next(c for c in result["changes"] if c["name"] == "add-bar")
    assert bar["prerequisites"] == ["add-real"]


def test_name_exactly_at_the_window_boundary_is_still_counted(changes_dir: Path):
    make_change(changes_dir, "add-foo")
    # "Depends on " (11 chars) + filler so `add-foo` starts right at the
    # edge of the 120-char window measured from the end of "Depends".
    filler = "x" * (120 - len(" on ") - len("`add-foo`"))
    make_change(changes_dir, "add-bar", tasks=f"Depends on {filler}`add-foo`\n")
    result = discover(changes_dir)
    bar = next(c for c in result["changes"] if c["name"] == "add-bar")
    assert bar["prerequisites"] == ["add-foo"]


def test_name_just_past_the_window_boundary_is_not_counted(changes_dir: Path):
    make_change(changes_dir, "add-foo")
    filler = "x" * (120 - len(" on ") - len("`add-foo`") + 5)
    make_change(changes_dir, "add-bar", tasks=f"Depends on {filler}`add-foo`\n")
    result = discover(changes_dir)
    bar = next(c for c in result["changes"] if c["name"] == "add-bar")
    assert bar["prerequisites"] == []


def test_word_containing_signal_substring_is_not_a_false_positive(changes_dir: Path):
    # Regression: an earlier version of the signal-word regex had no word
    # boundaries, so "independent"/"dependency-free" (both contain "depend"
    # as a substring) incorrectly counted as a dependency signal.
    make_change(changes_dir, "add-foo")
    make_change(
        changes_dir, "add-bar",
        tasks="add-bar is fully independent of add-foo; ships as dependency-free.\n",
    )
    result = discover(changes_dir)
    bar = next(c for c in result["changes"] if c["name"] == "add-bar")
    assert bar["prerequisites"] == []


def test_change_name_is_a_prefix_of_another_change_name_is_not_a_false_positive(changes_dir: Path):
    # Regression: plain substring matching let "add-foo" match inside
    # "add-foo-extended" -- a realistic collision given this repo's
    # kebab-case change-naming convention (e.g. add-brief-file-upload vs. a
    # hypothetical add-brief-file-upload-validation).
    make_change(changes_dir, "add-foo")
    make_change(changes_dir, "add-foo-extended")
    make_change(
        changes_dir, "add-bar",
        tasks="> Prerequisite: `add-foo-extended` merged first.\n",
    )
    result = discover(changes_dir)
    bar = next(c for c in result["changes"] if c["name"] == "add-bar")
    assert bar["prerequisites"] == ["add-foo-extended"]  # NOT ["add-foo", "add-foo-extended"]


def test_signal_word_matching_is_case_insensitive(changes_dir: Path):
    make_change(changes_dir, "add-foo")
    make_change(changes_dir, "add-bar", tasks="REQUIRES `add-foo` to ship first.\n")
    result = discover(changes_dir)
    bar = next(c for c in result["changes"] if c["name"] == "add-bar")
    assert bar["prerequisites"] == ["add-foo"]


def test_has_proposal_false_when_only_tasks_md_exists(changes_dir: Path):
    make_change(changes_dir, "add-foo", proposal=None, tasks="## 1. Stub\n")
    result = discover(changes_dir)
    assert result["changes"][0]["has_proposal"] is False


def test_unreadable_artifact_file_does_not_crash_discovery(changes_dir: Path):
    # _read_text's OSError/UnicodeDecodeError fallback: a non-UTF-8 file
    # must degrade to "no signal found here", not raise.
    make_change(changes_dir, "add-foo")
    (changes_dir / "add-foo" / "tasks.md").write_bytes(b"\xff\xfe not valid utf-8 \x00\x01")
    result = discover(changes_dir)
    assert result["order"] == ["add-foo"]


def test_diamond_dependency_orders_both_middle_nodes_before_the_join(changes_dir: Path):
    #     add-base
    #      /    \
    #  add-left add-right
    #      \    /
    #     add-join
    make_change(changes_dir, "add-base")
    make_change(changes_dir, "add-left", tasks="> Prerequisite: `add-base` merged.\n")
    make_change(changes_dir, "add-right", tasks="> Prerequisite: `add-base` merged.\n")
    make_change(
        changes_dir, "add-join",
        tasks="> Prerequisite: `add-left` and `add-right` merged.\n",
    )
    result = discover(changes_dir)
    order = result["order"]
    assert order.index("add-base") < order.index("add-left")
    assert order.index("add-base") < order.index("add-right")
    assert order.index("add-left") < order.index("add-join")
    assert order.index("add-right") < order.index("add-join")
    join = next(c for c in result["changes"] if c["name"] == "add-join")
    assert set(join["prerequisites"]) == {"add-left", "add-right"}


def test_transitive_chain_orders_all_three(changes_dir: Path):
    make_change(changes_dir, "add-a")
    make_change(changes_dir, "add-b", tasks="> Prerequisite: `add-a` merged.\n")
    make_change(changes_dir, "add-c", tasks="> Prerequisite: `add-b` merged.\n")
    result = discover(changes_dir)
    assert result["order"] == ["add-a", "add-b", "add-c"]


def test_cycle_is_detected_and_cyclic_members_excluded_from_order(changes_dir: Path):
    make_change(changes_dir, "add-a", tasks="> Prerequisite: `add-b` merged.\n")
    make_change(changes_dir, "add-b", tasks="> Prerequisite: `add-a` merged.\n")
    result = discover(changes_dir)
    assert result["cycle_detected"] is True
    assert set(result["cycle_members"]) == {"add-a", "add-b"}
    assert result["order"] == []
    assert result["blocked_by_cycle"] == []


def test_node_downstream_of_a_cycle_is_blocked_not_mislabeled_as_cyclic(changes_dir: Path):
    # Regression: an earlier version treated every node Kahn's algorithm
    # couldn't place as a "cycle member", including add-c below, which
    # participates in NO cycle -- it's just stuck behind one via add-a.
    make_change(changes_dir, "add-a", tasks="> Prerequisite: `add-b` merged.\n")
    make_change(changes_dir, "add-b", tasks="> Prerequisite: `add-a` merged.\n")
    make_change(changes_dir, "add-c", tasks="> Prerequisite: `add-a` merged.\n")
    result = discover(changes_dir)
    assert set(result["cycle_members"]) == {"add-a", "add-b"}
    assert result["blocked_by_cycle"] == ["add-c"]
    assert result["cycle_detected"] is True
    assert result["order"] == []


def test_prerequisite_outside_discovered_set_is_ignored_not_an_error(changes_dir: Path):
    make_change(changes_dir, "add-foo", tasks="> Prerequisite: `some-already-merged-change` merged.\n")
    result = discover(changes_dir)
    # "some-already-merged-change" isn't among the discovered directories, so
    # it can't be recognized as a prerequisite (only known changes qualify)
    # and it can't gate ordering either way.
    assert result["order"] == ["add-foo"]
    assert result["changes"][0]["prerequisites"] == []


def test_cli_no_openspec_dir_exits_one_with_error_object(tmp_path: Path):
    result = _run_cli("--repo-root", str(tmp_path))
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert "error" in payload
    assert str(tmp_path) in payload["error"]


def test_cli_with_repo_root_returns_zero_and_discovers_changes(tmp_path: Path):
    changes_dir = tmp_path / "openspec" / "changes"
    changes_dir.mkdir(parents=True)
    make_change(changes_dir, "add-foo")
    result = _run_cli("--repo-root", str(tmp_path))
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["order"] == ["add-foo"]


def test_main_function_matches_cli_exit_codes(tmp_path: Path, capsys):
    assert main(["--repo-root", str(tmp_path)]) == 1
    changes_dir = tmp_path / "openspec" / "changes"
    changes_dir.mkdir(parents=True)
    make_change(changes_dir, "add-foo")
    assert main(["--repo-root", str(tmp_path)]) == 0
