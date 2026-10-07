"""Measure how many words of plugin prose each skill puts in front of the model.

Every token-cutting change in issues #296-#299 promises a saving, and CLAUDE.md
check 3 says a saving with no command behind it is not a measurement. This is
that command: run it before an edit and after, and quote both.

Three numbers, each with a fixed rule so a before/after compares like with like:

- **Session** — what every session pays before any skill runs: the forced output
  style body, plus the `description:` of every skill the model can invoke on its
  own (`disable-model-invocation: true` skills are not listed) and every agent.
- **Per skill** — `SKILL.md` (loaded whole on invocation) and its *reachable* set:
  every `references/*.md` the skill names, followed transitively. Reachable is an
  upper bound — a reference read only on a rare branch still counts — so moving
  text from SKILL.md into a reference lowers the first number and leaves the
  second unchanged, which is the evidence that nothing was dropped.
- **Profiles** — the files a typical run actually reads, curated in `PROFILES`
  because "read on every run" is a judgement about prose no regex can make. Each
  entry names the line that forces the read, and `check_profiles` fails when a
  profile names a file that no longer exists or that its skill no longer reaches.

Words are whitespace-separated runs, which is what `LC_ALL=C.UTF-8 wc -w`
reports. Under a C locale `wc -w` skips a run with no printable ASCII, such as a
lone em dash, and reads about 2% lower on this plugin's prose (2026-10-07,
`LC_ALL=C wc -w` against `LC_ALL=C.UTF-8 wc -w` on `skills/spec-to-pr/SKILL.md`).
The figures quoted in #296-#299 were taken under the C locale.
Tokens are not reported: the ratio varies by model and text, and a word count is
reproducible.

    python3 plugin-tests/scripts/measure_load.py              # summary table
    python3 plugin-tests/scripts/measure_load.py --skill spec-to-pr
    python3 plugin-tests/scripts/measure_load.py --json       # for a PR body
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = _REPO_ROOT / ".claude" / "plugins" / "cla"

# A typical run of each skill: the files read on every pass, not on a branch.
# Paths are relative to the plugin root; the first entry is the skill's SKILL.md.
PROFILES: dict[str, tuple[str, ...]] = {
    # Baseline in #296: one change, tests written, PR opened, no delegate.
    "spec-to-pr": (
        "skills/spec-to-pr/SKILL.md",
        "skills/spec-to-pr/references/precheck.md",  # Precheck: "Read ... first"
        "skills/review-change/references/checklist.md",  # Review: "Read ... and execute it inline"
        "skills/_shared/references/test-quality.md",  # Implement: tests "follow" it
        "skills/spec-to-pr/references/ship.md",  # Ship: "Read ... first"
        "skills/spec-to-pr/references/revise.md",  # Revise: "Read ... first"
        "skills/spec-to-pr/references/archive.md",  # Archive: "Read ... first"
        "skills/spec-to-pr/references/archive-preflight.md",  # read from archive.md
        "skills/spec-to-pr/references/handoff.md",  # Handoff: "Read ... first"
        "skills/_shared/references/run-log-schema.md",  # Handoff builds the run record from it
    ),
    "lite-pr": (
        "skills/lite-pr/SKILL.md",
        "skills/_shared/references/test-quality.md",  # Implement: tests "follow" it
    ),
    "review-change": (
        "skills/review-change/SKILL.md",
        "skills/review-change/references/checklist.md",  # "Read ... and execute it"
    ),
}

_REF = re.compile(r"(\$\{CLAUDE_PLUGIN_ROOT\}/)?([\w./-]+\.md)")


def count_words(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").split())


def frontmatter(text: str) -> dict[str, str]:
    """Top-level `key: value` pairs of a leading `---` block. Values are raw."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line[:1] in (" ", "\t", "#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def _skill_dir(path: Path, root: Path) -> Path:
    """The skill directory a file belongs to: `skills/<name>/`."""
    rel = path.relative_to(root / "skills")
    return root / "skills" / rel.parts[0]


def _resolve(token: str, prefixed: bool, source: Path, root: Path) -> Path | None:
    if prefixed:
        candidates = [root / token]
    else:
        candidates = [_skill_dir(source, root) / token, root / "skills" / token, root / token]
    resolved_root = root.resolve()
    for candidate in candidates:
        candidate = candidate.resolve()
        if not candidate.is_file():
            continue
        if not candidate.is_relative_to(resolved_root):
            continue
        return candidate
    return None


def references(source: Path, root: Path) -> set[Path]:
    """The `references/*.md` files `source` names, resolved and existing."""
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


def session_load(root: Path) -> dict:
    """Words present in every session: forced output styles plus listings."""
    styles = {}
    for style in sorted((root / "output-styles").glob("*.md")):
        text = style.read_text(encoding="utf-8")
        body = text.split("---", 2)[2] if text.startswith("---") else text
        styles[style.name] = len(body.split())
    descriptions = {}
    for path in sorted(root.glob("skills/*/SKILL.md")) + sorted(root.glob("agents/*.md")):
        fields = frontmatter(path.read_text(encoding="utf-8"))
        if fields.get("disable-model-invocation", "").lower() == "true":
            continue
        name = fields.get("name") or path.parent.name
        descriptions[name] = len(fields.get("description", "").split())
    return {
        "output_styles": styles,
        "descriptions": descriptions,
        "total": sum(styles.values()) + sum(descriptions.values()),
    }


def skill_load(root: Path) -> dict[str, dict]:
    result = {}
    for skill_md in sorted(root.glob("skills/*/SKILL.md")):
        refs = reachable(skill_md, root)
        body = count_words(skill_md)
        result[skill_md.parent.name] = {
            "skill_md": body,
            "reachable": body + sum(count_words(p) for p in refs),
            "references": {
                p.relative_to(root.resolve()).as_posix(): count_words(p)
                for p in sorted(refs)
            },
        }
    return result


def check_profiles(root: Path, profiles: dict[str, tuple[str, ...]] | None = None) -> list[str]:
    """Problems with `profiles`: a missing file, or one its skill cannot reach."""
    problems = []
    for name, files in (PROFILES if profiles is None else profiles).items():
        skill_md = root / files[0]
        if not skill_md.is_file():
            problems.append(f"{name}: {files[0]} does not exist")
            continue
        refs = reachable(skill_md, root)
        for rel in files[1:]:
            path = root / rel
            if not path.is_file():
                problems.append(f"{name}: {rel} does not exist")
            elif path.resolve() not in refs:
                problems.append(f"{name}: {rel} is not reachable from {files[0]}")
    return problems


def profile_load(root: Path, profiles: dict[str, tuple[str, ...]] | None = None) -> dict[str, dict]:
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
    parser.add_argument("--root", type=Path, default=PLUGIN_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    problems = check_profiles(args.root)
    if problems:
        for problem in problems:
            print(f"stale profile: {problem}", file=sys.stderr)
        return 2
    data = measure(args.root)
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
