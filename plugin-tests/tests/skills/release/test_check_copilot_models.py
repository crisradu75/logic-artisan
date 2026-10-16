"""`check_copilot_models.py` refuses a release whose Copilot model IDs are not in GitHub's table.

Every test reads a saved copy of the page structure and passes a fake fetch: none makes a
network call, so the suite is the same offline. The page layout below copies the rendered
command reference (a heading with `id="supported-models"`, then a table whose first cell holds
the ID in a code span), with another section's table before and after it, so a scan that read
the whole page instead of the one section would pass the "missing" tests for the wrong reason.

The check against the live page is a manual step of the release procedure; the last test here
only proves the release skill runs the script.
"""

from __future__ import annotations

import re
import urllib.error
from pathlib import Path

import pytest

import check_copilot_models as ccm

_SKILL_MD = Path(__file__).resolve().parents[4] / ".claude" / "skills" / "release" / "SKILL.md"

_MAP = {"haiku": "claude-haiku-5.5", "sonnet": "claude-sonnet-5.5", "opus": "claude-opus-5.5"}


def _page(*ids: str, section: bool = True) -> str:
    rows = "".join(f"<tr><td><code>{i}</code></td><td>Best for</td></tr>" for i in ids)
    models = (
        '<h2 id="supported-models" tabindex="-1"><a class="heading-link" href="#supported-models">'
        "Supported models</a></h2>\n<p>Use <code>--model=MODEL</code> to select.</p>\n\n\n"
        '<table aria-labelledby="supported-models"><thead><tr><th scope="col">Model</th>'
        f'<th scope="col">Best for</th></tr></thead><tbody>{rows}</tbody></table>\n'
    ) if section else ""
    before = ('<h2 id="command-line-options">Options</h2><table><tbody>'
              "<tr><td><code>claude-before-5.0</code></td><td>x</td></tr></tbody></table>\n")
    after = ('<h2 id="tool-availability-values">Tools</h2><table><tbody>'
             "<tr><td><code>claude-after-5.0</code></td><td>x</td></tr></tbody></table>\n")
    return f"<html><body>{before}{models}{after}</body></html>"


def _fetch(page: str):
    return lambda: page


def test_the_ids_are_read_from_the_supported_models_section_only():
    page = _page("claude-sonnet-5.5", "gpt-5.4")
    assert ccm.supported_ids(page) == ["claude-sonnet-5.5", "gpt-5.4"]


def test_a_page_without_the_section_or_its_rows_is_an_error_not_an_empty_list():
    with pytest.raises(ValueError, match="no 'supported-models' section"):
        ccm.supported_ids(_page(section=False))
    with pytest.raises(ValueError, match="no model rows"):
        ccm.supported_ids(_page())


def test_the_last_section_of_a_page_is_read_to_its_end():
    page = _page("claude-sonnet-5.5").split('<h2 id="tool-availability-values">')[0]
    assert ccm.supported_ids(page) == ["claude-sonnet-5.5"]


def test_missing_ids_names_each_alias_whose_id_is_not_listed():
    listed = ["claude-sonnet-5.5", "claude-opus-5.5"]
    assert ccm.missing_ids(_MAP, listed) == {"haiku": "claude-haiku-5.5"}
    assert ccm.missing_ids(_MAP, [*listed, "claude-haiku-5.5"]) == {}
    # An ID that exists elsewhere on the page but not in the table is missing.
    assert ccm.missing_ids({"sonnet": "claude-before-5.0"}, listed) == {"sonnet": "claude-before-5.0"}


def test_main_exits_0_when_every_id_is_listed(capsys):
    page = _page("claude-sonnet-5.5", "claude-opus-5.5", "claude-haiku-5.5", "claude-haiku-4.5")
    assert ccm.main(_fetch(page), _MAP) == ccm.EXIT_OK
    assert "all 3 Copilot model IDs are listed" in capsys.readouterr().out


def test_main_exits_1_naming_every_missing_id(capsys):
    page = _page("claude-sonnet-5.5")
    assert ccm.main(_fetch(page), _MAP) == ccm.EXIT_MISSING
    captured = capsys.readouterr()
    assert "claude-haiku-5.5" in captured.err and "'haiku'" in captured.err
    assert "claude-opus-5.5" in captured.err and "'opus'" in captured.err
    assert "claude-sonnet-5.5 (" not in captured.err, "a listed ID must not be reported"
    assert "ok:" not in captured.out


@pytest.mark.parametrize(
    "fetch",
    [
        pytest.param(lambda: (_ for _ in ()).throw(urllib.error.URLError("offline")), id="offline"),
        pytest.param(lambda: (_ for _ in ()).throw(TimeoutError("slow")), id="timeout"),
        pytest.param(lambda: (_ for _ in ()).throw(UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad")), id="bad bytes"),
        pytest.param(_fetch("<html>layout changed</html>"), id="no section"),
        pytest.param(_fetch(_page()), id="section with no rows"),
    ],
)
def test_main_exits_2_when_the_table_cannot_be_read(fetch, capsys):
    assert ccm.main(fetch, _MAP) == ccm.EXIT_CANNOT_RUN
    assert "cannot read GitHub's supported-models table" in capsys.readouterr().err


def test_main_exits_2_on_an_empty_model_map(capsys):
    assert ccm.main(_fetch(_page("claude-sonnet-5.5")), {}) == ccm.EXIT_CANNOT_RUN
    assert "MODEL_MAP is empty" in capsys.readouterr().err


def test_the_default_map_is_the_one_the_agent_generator_writes():
    import sync_copilot_agents

    assert ccm._model_map() == sync_copilot_agents.MODEL_MAP


def test_the_release_skill_runs_the_model_check_before_a_tag():
    body = _SKILL_MD.read_text(encoding="utf-8")
    step1 = body.split("## Step 1", 1)[1].split("## Step 2", 1)[0]
    runnable = "\n".join(re.findall(r"```(?:bash|sh)?\n(.*?)```", step1, re.S))
    assert "python3 .claude/skills/release/scripts/check_copilot_models.py" in runnable, (
        "release/SKILL.md Step 1 no longer runs the Copilot model check"
    )
    table = step1.replace(runnable, "")
    assert "check_copilot_models.py" in table and "exits 2" in table, (
        "the precondition table must say why the check is there and that exit 2 also refuses"
    )
