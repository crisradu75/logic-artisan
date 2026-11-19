"""The format limits and the per-change budget `check_spec_proof.py` enforces.

Reads them out of the repo's own OpenSpec rules text and counts a change's
requirements and words against them. Not a command: import it, or run
`check_spec_proof.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

from spec_proof_parse import CheckerError, _fence_after


_LIMIT_PATTERNS = {
    "chars": r"(\d+)\s+characters\s+or\s+(?:fewer|less)",
    "scenarios": r"(?:at\s+most|no\s+more\s+than|up\s+to)\s+(\d+)\s+scenarios",
    # Per spec. Optional: a sentence about the whole change ("... requirements across all its specs") is not this limit.
    "requirements": r"(?:at\s+most|no\s+more\s+than|up\s+to)\s+(\d+)\s+requirements(?!\s+across\b)",
}
_OPTIONAL_LIMITS = {"requirements"}
# The whole-change budget, read from the same `rules:` text: "at most 25 requirements across all its specs
# and at most 6,000 words in total".
_BUDGET_PATTERNS = {
    "requirements": r"(?:at\s+most|no\s+more\s+than|up\s+to)\s+(\d[\d,]*)\s+requirements\s+across\s+all\b",
    "words": r"(?:at\s+most|no\s+more\s+than|up\s+to)\s+(\d[\d,]*)\s+words\s+in\s+total\b",
}
_LIMIT_WORDS = {"chars": "characters", "scenarios": "scenarios", "requirements": "requirements"}
_NUMBER_WORDS = r"one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d+"


def _specs_rules_block(text: str) -> str | None:
    """The lines of `rules:` -> `specs:` in a config, at any indent and in either list style
    (items deeper than the key, or at the key's own indent). None when there is no such key."""
    lines = text.splitlines()
    in_rules = False
    rules_indent = 0
    for i, line in enumerate(lines):
        if not in_rules:
            if re.match(r"^rules:\s*(?:#.*)?$", line):
                in_rules, rules_indent = True, 0
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= rules_indent:
            return None  # left `rules:` without meeting `specs:`
        if re.match(r"^specs:\s*(?:[|>][-+]?\s*)?(?:#.*)?$", stripped):
            block = []
            for nxt in lines[i + 1:]:
                s = nxt.strip()
                n_indent = len(nxt) - len(nxt.lstrip())
                if s and not s.startswith("#"):
                    if n_indent < indent or (n_indent == indent and not s.startswith("- ")):
                        break
                block.append(nxt)
            return "\n".join(block)
    return None


def read_format_limits(root: Path) -> tuple[dict[str, int], list[str]]:
    """The spec format limits, read from the `rules.specs` text of openspec/config.yaml (or .yml).

    Nothing is copied into this script: the numbers come from the sentences the repo
    wrote ("500 characters or fewer", "at most 3 scenarios", "at most 8 requirements").
    Returns ({limit: number}, [names of limits not found]). No config, or a config with no
    `rules.specs`, means no limits and every name is returned as not enforced.

    A `rules.specs` that exists but yields no limit at all, or that gives a number for a
    limit in words this reader does not know ("at most three scenarios"), raises: a
    guard that enforces nothing must not look like one that found nothing wrong."""
    cfg = next((p for p in (root / "openspec" / "config.yaml", root / "openspec" / "config.yml") if p.is_file()), None)
    try:
        text = cfg.read_text(encoding="utf-8-sig") if cfg else ""
    except (OSError, UnicodeDecodeError) as exc:
        raise CheckerError(f"cannot read {cfg.name}: {exc}") from exc
    block = _specs_rules_block(text)
    if block is None:
        return {}, list(_LIMIT_PATTERNS)
    found, missing = {}, []
    for name, pat in _LIMIT_PATTERNS.items():
        hit = re.search(pat, block, re.I)
        if hit:
            found[name] = int(hit.group(1))
        elif name in _OPTIONAL_LIMITS:
            continue  # the per-spec cap is retired; a repo that states none simply has none
        else:
            missing.append(name)
            word = _LIMIT_WORDS[name]
            if re.search(rf"(?i)\b(?:{_NUMBER_WORDS})\s+(?:\w+\s+)?{word}\b", block):
                raise CheckerError(f"rules.specs in {cfg.name} gives a number for {word} in wording this checker does not read; use e.g. 'at most 3 scenarios', '500 characters or fewer'")
    if not found:
        raise CheckerError(f"rules.specs in {cfg.name} states none of the format limits this checker reads")
    return found, missing


def read_change_budget(root: Path) -> tuple[dict[str, int], dict[str, int]]:
    """The whole-change budget, read from the `rules:` text of openspec/config.yaml (or .yml).

    Like `read_format_limits`, nothing is copied here: the numbers come from the sentence the repo
    wrote ("at most 25 requirements across all its specs and at most 6,000 words in total").
    Returns (the repo's budget, the protected override budget), each {"requirements": n, "words": n}
    for each number found; one the config does not state is not enforced, and the output line says so."""
    cfg = next((p for p in (root / "openspec" / "config.yaml", root / "openspec" / "config.yml") if p.is_file()), None)
    try:
        text = cfg.read_text(encoding="utf-8-sig") if cfg else ""
    except (OSError, UnicodeDecodeError) as exc:
        raise CheckerError(f"cannot read {cfg.name}: {exc}") from exc
    rules = _rules_text(text)
    # The override sentence names `Budget: protected`; every other budget sentence is the repo's own.
    items = _list_items(rules)  # whole items, so a sentence YAML wraps onto a second line stays one
    override_text = "\n".join(item for item in items if _OVERRIDE_MARK in item)
    repo_text = "\n".join(item for item in items if _OVERRIDE_MARK not in item)
    name = cfg.name if cfg else "config"
    return _parse_budget(repo_text, name), _parse_budget(override_text, name)


_OVERRIDE_MARK = "Budget: protected"
_BUDGET_PHRASES = {"requirements": r"requirements\s+across\s+all\b", "words": r"words\s+in\s+total\b"}


def _rules_text(text: str) -> str:
    """The lines under the top-level `rules:` key, comments dropped: nothing outside it (a `context:`
    block, say) can state a budget."""
    out, in_rules = [], False
    for line in text.splitlines():
        if not in_rules:
            in_rules = bool(re.match(r"^rules:\s*(?:#.*)?$", line))
            continue
        if line.strip() and not line[0].isspace() and not line.startswith("- "):
            break  # the next top-level key
        if not line.lstrip().startswith("#"):
            out.append(line)
    return "\n".join(out)


def _list_items(rules: str) -> list[str]:
    """The `- ` list items of a `rules:` block, each on one line: a line that does not start with `- `
    and is not a `key:` line continues the item above it. A key line ends the item."""
    items: list[str] = []
    open_item = False
    for line in rules.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("- "):
            items.append(s[2:].strip())
            open_item = True
        elif re.fullmatch(r"[\w-]+:\s*(?:[|>][-+]?)?", s):
            open_item = False
        elif open_item:
            items[-1] += " " + s
        else:
            items.append(s)  # a block scalar's line or a bare scalar: its own item
    return items


def _parse_budget(text: str, name: str) -> dict[str, int]:
    """{"requirements": n, "words": n} for each budget `text` states. A budget phrase whose number is
    in wording this reader does not know ("twenty-five", "6 000", "6.000") raises: a guard that
    enforces less than the config says must not look like one that found nothing wrong."""
    found = {}
    for key, pat in _BUDGET_PATTERNS.items():
        if len(re.findall(_BUDGET_PHRASES[key], text, re.I)) > 1:
            raise CheckerError(f"the change budget in {name} states a {key} budget more than once for the same budget; keep one sentence per budget")
        hit = re.search(pat, text, re.I)
        if hit:
            found[key] = int(hit.group(1).replace(",", ""))
        elif re.search(_BUDGET_PHRASES[key], text, re.I):
            raise CheckerError(f"the change budget in {name} gives a {key} number in wording this checker does not read; use e.g. 'at most 25 requirements across all its specs', 'at most 6,000 words in total'")
    return found


_BUDGET_LINE = re.compile(r"^[ \t]*Budget:[ \t]*(.*?)[ \t]*$", re.M)


def change_budget_for(proposal: Path, budget: dict[str, int], override: dict[str, int], name: str) -> tuple[dict[str, int], str, list[str]]:
    """(the budget this change is held to, a label for the output line, PROBLEM lines) after reading a
    `Budget:` line of its proposal. `Budget: protected` selects the override sentence; any other value, or
    that value with no override sentence in the config, is a problem and the repo budget stays."""
    try:
        text = proposal.read_text(encoding="utf-8-sig", errors="replace") if proposal.is_file() else ""
    except OSError as exc:
        raise CheckerError(f"cannot read {proposal}: {exc}") from exc
    # A `Budget:` line inside a code fence is an example, not this change's choice.
    outside, fence = [], None
    for line in text.splitlines():
        was_fenced = fence is not None
        fence = _fence_after(line, fence)
        if not was_fenced and fence is None:
            outside.append(line)
    values = _BUDGET_LINE.findall("\n".join(outside))
    problems, chosen = [], budget
    for value in values:
        if value != "protected":
            problems.append(f"PROBLEM budget: openspec/changes/{name}/proposal.md: 'Budget: {value}' is not a budget this checker knows; the only value is 'Budget: protected'")
        elif not override:
            problems.append(f"PROBLEM budget: openspec/changes/{name}/proposal.md: 'Budget: protected' but the config states no protected budget sentence, so it raises nothing")
        else:
            chosen = override
    return chosen, (" (Budget: protected)" if chosen is override else ""), problems


def change_totals(change_dir: Path) -> tuple[int, int]:
    """(requirements, words) over every `.md` file under one change folder: the count `wc -w` and
    `grep '### Requirement:'` give over the same files."""
    requirements = words = 0
    for md in sorted(change_dir.rglob("*.md")):
        try:
            # -sig: a byte-order mark would count as a word of its own or hide a heading on line 1.
            text = md.read_bytes().decode("utf-8-sig", errors="replace")
        except OSError as exc:
            raise CheckerError(f"cannot read {md}: {exc}") from exc
        words += len(text.split())
        requirements += len(re.findall(r"^### Requirement:", text, re.M))
    return requirements, words


def check_change_budget(root: Path, budget: dict[str, int], override: dict[str, int] | None = None) -> tuple[list[str], list[str]]:
    """(PROBLEM lines, one info line per active change) for the changes over the whole-change budget.

    Active changes only: `openspec/changes/<name>/`, never `archive/`, which is not edited. Every active
    change, whatever `--base` or `--tests` says: like `format`, the budget is a property of the change as
    it stands in the tree, not of what this branch edited, and `--tests` narrows only the marker scan. An
    over-budget change on the default branch would otherwise pass every branch that does not touch it."""
    changes = root / "openspec" / "changes"
    problems, info = [], []
    if not changes.is_dir():
        return problems, info
    for d in sorted(p for p in changes.iterdir() if p.is_dir() and p.name != "archive"):
        reqs, words = change_totals(d)
        held, label, bad = change_budget_for(d / "proposal.md", budget, override or {}, d.name)
        problems += bad
        info.append(f"change {d.name}: {reqs} requirements, {words} words{label}")
        if "requirements" in held and reqs > held["requirements"]:
            problems.append(f"PROBLEM budget: openspec/changes/{d.name}: {reqs} requirements, the budget is {held['requirements']}")
        if "words" in held and words > held["words"]:
            problems.append(f"PROBLEM budget: openspec/changes/{d.name}: {words} words, the budget is {held['words']}")
    return problems, info
