"""Measure how many words of plugin prose each skill puts in front of the model.

Every token-cutting change in issues #296-#299 promises a saving, and CLAUDE.md
check 3 says a saving with no command behind it is not a measurement. This is
that command: run it before an edit and after, and quote both.

Three numbers, each with a fixed rule so a before/after compares like with like:

- **Session** — what every session pays before any skill runs: the body of each
  output style with `force-for-plugin` true, plus the `description:` of every
  skill the model can invoke on its own (skills with `disable-model-invocation`
  true are not listed) and every agent.
- **Per skill** — `SKILL.md` (loaded whole on invocation) and its *reachable* set:
  every `references/*.md` the skill names, followed transitively. Reachable is an
  upper bound — a reference read only on a rare branch still counts — so moving
  text from SKILL.md into a reference lowers the first number and leaves the
  second unchanged, which is the evidence that nothing was dropped.
- **Profiles** — the files a typical run actually reads, curated in `PROFILES`
  because "read on every run" is a judgement about prose no regex can make. Each
  entry names the file whose text forces the read, and `check_profiles` fails
  when that file no longer names it directly. Reachability alone would not do:
  most references reach most others, so a pointer could be deleted and the file
  would still be "reachable".

Words are whitespace-separated runs, which is what `LC_ALL=C.UTF-8 wc -w`
reports. Under a C locale `wc -w` skips a run with no printable ASCII, such as a
lone em dash, and reads about 2% lower on this plugin's prose (2026-10-07,
`LC_ALL=C wc -w` against `LC_ALL=C.UTF-8 wc -w` on `skills/spec-to-pr/SKILL.md`).
Tokens are not reported: the ratio varies by model and text, and a word count is
reproducible.

    python3 plugin-tests/scripts/measure_load.py              # summary table
    python3 plugin-tests/scripts/measure_load.py --skill spec-to-pr
    python3 plugin-tests/scripts/measure_load.py --json       # for a PR body
    python3 plugin-tests/scripts/measure_load.py --root <other checkout>/.claude/plugins/cla
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

_DEV_TREE = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = _DEV_TREE.parent / ".claude" / "plugins" / "cla"

_SPEC = "skills/spec-to-pr/SKILL.md"
_SPEC_REFS = "skills/spec-to-pr/references"
_SHARED = "skills/_shared/references"
_CHECKLIST = "skills/review-change/references/checklist.md"

# A typical run of each skill: file -> the file whose text forces the read
# (None for the SKILL.md itself). Paths are relative to the plugin root.
PROFILES: dict[str, dict[str, str | None]] = {
    # Baseline in #296: one change, tests written, PR opened, no delegate.
    "spec-to-pr": {
        _SPEC: None,
        f"{_SPEC_REFS}/precheck.md": _SPEC,  # Precheck: "Read ... first"
        _CHECKLIST: _SPEC,  # Review: "Read ... and execute it inline"
        f"{_SPEC_REFS}/review-sweeps.md": _SPEC,  # Review: sweeps + a FIX FIRST round's fixes
        f"{_SHARED}/test-quality.md": _SPEC,  # Implement: tests "follow" it
        f"{_SPEC_REFS}/ship.md": _SPEC,  # Ship: "Read ... first"
        f"{_SPEC_REFS}/revise.md": _SPEC,  # Revise: "Read ... first"
        f"{_SPEC_REFS}/archive.md": _SPEC,  # Archive: "Read ... first"
        f"{_SPEC_REFS}/handoff.md": _SPEC,  # Handoff: "Read ... first"
        f"{_SHARED}/run-log-schema.md": f"{_SPEC_REFS}/handoff.md",  # builds the run record
    },
    "lite-pr": {
        "skills/lite-pr/SKILL.md": None,
        f"{_SHARED}/test-quality.md": "skills/lite-pr/SKILL.md",  # tests "follow" it
    },
    "review-change": {
        "skills/review-change/SKILL.md": None,
        _CHECKLIST: "skills/review-change/SKILL.md",  # "Read ... and execute it"
    },
}

_REF = re.compile(r"(\$\{CLAUDE_PLUGIN_ROOT\}/)?([\w./-]+\.md)")
_YAML_TRUE = {"true", "yes", "on"}


def _load_parse_frontmatter():
    """The repo's one frontmatter parser, loaded by path from the conformance
    area (not on `pythonpath`), as `test_doc_facts.py` does. A second parser
    here could disagree with it, which is the defect class that file names."""
    path = _DEV_TREE / "tests" / "conformance" / "test_skill_lint.py"
    spec = importlib.util.spec_from_file_location("_skill_lint_for_measure_load", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.parse_frontmatter


parse_frontmatter = _load_parse_frontmatter()


def _is_true(value: str) -> bool:
    """YAML's spellings of true; the parser leaves quotes and comments on."""
    return value.split("#")[0].strip().strip("\"'").lower() in _YAML_TRUE


def count_words(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").split())


def _skill_dir(path: Path, root: Path) -> Path:
    """The skill directory a file belongs to: `skills/<name>/`. Both resolved."""
    rel = path.relative_to(root / "skills")
    return root / "skills" / rel.parts[0]


def _resolve(token: str, prefixed: bool, source: Path, root: Path) -> Path | None:
    """`root` and `source` must be resolved. Bare names try the naming file's
    own directory first, so a reference naming a sibling (`design-tradeoffs.md`
    from `revise.md`) resolves."""
    if prefixed:
        candidates = [root / token]
    else:
        candidates = [
            source.parent / token,
            _skill_dir(source, root) / token,
            root / "skills" / token,
            root / token,
        ]
    for candidate in candidates:
        candidate = candidate.resolve()
        if not candidate.is_file():
            continue
        if not candidate.is_relative_to(root):
            continue
        return candidate
    return None


def references(source: Path, root: Path) -> set[Path]:
    """The `references/*.md` files `source` names directly, resolved."""
    root, source = root.resolve(), source.resolve()
    found: set[Path] = set()
    for match in _REF.finditer(source.read_text(encoding="utf-8")):
        target = _resolve(match.group(2), bool(match.group(1)), source, root)
        if target is None or target.parent.name != "references":
            continue
        found.add(target)
    return found


def reachable(skill_md: Path, root: Path) -> set[Path]:
    """Every reference reachable from `skill_md`, transitively. Excludes it."""
    seen: set[Path] = set()
    queue = [skill_md.resolve()]
    while queue:
        for target in references(queue.pop(), root):
            if target not in seen:
                seen.add(target)
                queue.append(target)
    return seen


def _frontmatter(path: Path) -> dict[str, str]:
    mapping, error = parse_frontmatter(path.read_text(encoding="utf-8"))
    return {} if error is not None else mapping


def session_load(root: Path) -> dict:
    """Words present in every session: forced output styles plus listings.
    Keyed by path relative to the plugin root, so no two entries collide."""
    root = root.resolve()
    styles = {}
    for style in sorted((root / "output-styles").glob("*.md")):
        if not _is_true(_frontmatter(style).get("force-for-plugin", "")):
            continue
        text = style.read_text(encoding="utf-8")
        body = text.split("---", 2)[2] if text.startswith("---") else text
        styles[style.relative_to(root).as_posix()] = len(body.split())
    descriptions = {}
    for path in sorted(root.glob("skills/*/SKILL.md")) + sorted(root.glob("agents/*.md")):
        fields = _frontmatter(path)
        if _is_true(fields.get("disable-model-invocation", "")):
            continue
        descriptions[path.relative_to(root).as_posix()] = len(
            fields.get("description", "").split()
        )
    return {
        "output_styles": styles,
        "descriptions": descriptions,
        "total": sum(styles.values()) + sum(descriptions.values()),
    }


def skill_load(root: Path) -> dict[str, dict]:
    root = root.resolve()
    result = {}
    for skill_md in sorted(root.glob("skills/*/SKILL.md")):
        refs = reachable(skill_md, root)
        body = count_words(skill_md)
        result[skill_md.parent.name] = {
            "skill_md": body,
            "reachable": body + sum(count_words(p) for p in refs),
            "references": {
                p.relative_to(root).as_posix(): count_words(p) for p in sorted(refs)
            },
        }
    return result


def check_profiles(root: Path, profiles: dict[str, dict[str, str | None]] | None = None) -> list[str]:
    """Problems with `profiles`: a missing file, a forcing file outside the
    profile, or a forcing file that no longer names the file directly."""
    root = root.resolve()
    problems = []
    for name, files in (PROFILES if profiles is None else profiles).items():
        for rel, forced_by in files.items():
            path = root / rel
            if not path.is_file():
                problems.append(f"{name}: {rel} does not exist")
            elif forced_by is None:
                continue
            elif forced_by not in files:
                problems.append(f"{name}: {rel} is forced by {forced_by}, which is not in the profile")
            elif not (root / forced_by).is_file():
                continue  # reported as missing on its own entry
            elif path.resolve() not in references(root / forced_by, root):
                problems.append(f"{name}: {forced_by} no longer names {rel}")
    return problems


def profile_load(root: Path, profiles: dict[str, dict[str, str | None]] | None = None) -> dict[str, dict]:
    root = root.resolve()
    result = {}
    for name, files in (PROFILES if profiles is None else profiles).items():
        words = {rel: count_words(root / rel) for rel in files}
        result[name] = {"files": words, "total": sum(words.values())}
    return result


def measure(root: Path) -> dict:
    return {
        "session": session_load(root),
        "skills": skill_load(root),
        "profiles": profile_load(root),
    }


def _print_summary(data: dict) -> None:
    session = data["session"]
    print(f"Session (every session): {session['total']} words")
    for name, words in session["output_styles"].items():
        print(f"  output style {name}: {words}")
    print(f"  descriptions ({len(session['descriptions'])} listed): "
          f"{sum(session['descriptions'].values())}")
    print()
    print(f"{'skill':<20} {'SKILL.md':>9} {'reachable':>10}")
    for name, row in data["skills"].items():
        print(f"{name:<20} {row['skill_md']:>9} {row['reachable']:>10}")
    print()
    print("Profiles (typical run):")
    for name, row in data["profiles"].items():
        print(f"  {name}: {row['total']} words over {len(row['files'])} files")


def _print_skill(data: dict, name: str) -> None:
    row = data["skills"][name]
    print(f"{name}: SKILL.md {row['skill_md']}, reachable {row['reachable']}")
    for rel, words in sorted(row["references"].items(), key=lambda kv: -kv[1]):
        print(f"  {words:>6}  {rel}")
    if name in data["profiles"]:
        print(f"profile: {data['profiles'][name]['total']} words")
        for rel, words in data["profiles"][name]["files"].items():
            print(f"  {words:>6}  {rel}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="print the full measurement as JSON")
    parser.add_argument("--skill", help="break one skill down by file")
    parser.add_argument("--root", type=Path, default=PLUGIN_ROOT,
                        help="plugin root to measure (default: this checkout's)")
    args = parser.parse_args(argv)
    root = args.root.resolve()

    problems = check_profiles(root)
    if problems:
        for problem in problems:
            print(f"stale profile: {problem}", file=sys.stderr)
        return 2
    data = measure(root)
    if args.json:
        print(json.dumps(data, indent=2))
    elif args.skill:
        if args.skill not in data["skills"]:
            print(f"no such skill: {args.skill}", file=sys.stderr)
            return 2
        _print_skill(data, args.skill)
    else:
        _print_summary(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
