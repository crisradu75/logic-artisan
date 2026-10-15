"""The docs task and the doc list are stated at every site that reads them.

A change's tasks end with `docs and spec map: <files updated>, or none affected: <reason>`. The rule
lives in `openspec/config.yaml` and, in step with it, in the `cla-setup` seed script
(`test_cla_setup_rules_match_config.py` pins those two as identical). The doc list is the "Doc-sweep
paths" section of `cla.io/project-facts.md`. The review checklist, the Implement post-check, Revise's
docs-currency step, lite-pr's Plan and Review and the cla-setup description all point at that
heading and token. They are prose a model reads, so this pins what text can show: each site still
names the token or the heading, and this repo's own list is there and names real files. It does not
show that a review reports a stale doc; the requirement's prompt half is a `manual:` line.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_SKILLS = _REPO / ".claude" / "plugins" / "cla" / "skills"
_SEED = _SKILLS / "cla-setup" / "scripts" / "seed_openspec_rules.py"
_CONFIG = _REPO / "openspec" / "config.yaml"
_FACTS = _REPO / "cla.io" / "project-facts.md"

TOKEN = "docs and spec map:"
# What the checking sites say about the line itself, so a site that only mentions the rule in passing fails.
LINE = f"task whose text starts with `{TOKEN}`"
EXCUSE = "none affected:"
HEADING = "Doc-sweep paths"

# (file, what it must still say). The Revise and lite-pr sites also name their own step.
_SITES = {
    "review-change checklist": (_SKILLS / "review-change" / "references" / "checklist.md", (LINE, EXCUSE, HEADING)),
    "review-change dispatch": (_SKILLS / "review-change" / "references" / "dispatch.md", (LINE, EXCUSE)),
    "spec-to-pr Implement post-check": (_SKILLS / "spec-to-pr" / "SKILL.md", (LINE, EXCUSE)),
    "spec-to-pr Revise": (_SKILLS / "spec-to-pr" / "references" / "revise.md", (TOKEN, EXCUSE, HEADING, "Docs currency")),
    "spec-to-pr sweeps": (_SKILLS / "spec-to-pr" / "references" / "review-sweeps.md", (HEADING,)),
    "lite-pr": (_SKILLS / "lite-pr" / "SKILL.md", (HEADING, EXCUSE, "Docs check")),
    "cla-setup": (_SKILLS / "cla-setup" / "SKILL.md", (f"**{HEADING}**",)),
}


def _missing(text: str, wanted: tuple[str, ...]) -> list[str]:
    """The strings of `wanted` that `text` lacks."""
    return [w for w in wanted if w not in text]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _tasks_rules(text: str) -> str:
    match = re.search(r"^  tasks:\n((?:    .*\n)+)", text, re.M)
    assert match, "no tasks: rules block found"
    return match.group(1)


# requirement: docs-currency / A change keeps the repo's docs current
def test_the_config_and_the_seed_script_both_carry_the_docs_task_rule():
    seed = _read(_SEED)
    start = seed.index('RULES = r"""')
    block = seed[start : seed.index('""".rstrip', start)]
    for name, rules in (("openspec/config.yaml", _tasks_rules(_read(_CONFIG))), ("seed script RULES", _tasks_rules(block))):
        assert TOKEN in rules, f"{name}: rules.tasks lost the docs task token {TOKEN!r}"
        assert EXCUSE in rules, f"{name}: rules.tasks lost {EXCUSE!r}"
        assert HEADING in rules, f"{name}: rules.tasks no longer points at {HEADING!r}"


# requirement: docs-currency / A change keeps the repo's docs current
@pytest.mark.parametrize("site", sorted(_SITES))
def test_each_site_still_names_what_it_reads(site: str):
    path, wanted = _SITES[site]
    missing = _missing(_read(path), wanted)
    assert missing == [], f"{site} ({path.relative_to(_REPO)}) no longer says {missing}"


# requirement: docs-currency / A change keeps the repo's docs current
def test_this_repos_doc_list_is_present_and_names_real_files():
    facts = _read(_FACTS)
    match = re.search(rf"^## {HEADING}\n(.*?)(?=^## |\Z)", facts, re.M | re.S)
    assert match, f"cla.io/project-facts.md has no '## {HEADING}' section"
    section = match.group(1)
    names = re.findall(r"`([^`]+)`", section)
    assert len(names) >= 3, f"the doc list names {names}"
    for name in names:
        assert (_REPO / name).is_file(), f"the doc list names {name}, which is not a file"


# requirement: docs-currency / A change keeps the repo's docs current
def test_the_site_check_is_not_vacuous():
    # A site that dropped the token must be reported, and a site that keeps it must not be.
    assert _missing("no mention here", (TOKEN, HEADING)) == [TOKEN, HEADING]
    assert _missing(f"{TOKEN} and {HEADING}", (TOKEN, HEADING)) == []
