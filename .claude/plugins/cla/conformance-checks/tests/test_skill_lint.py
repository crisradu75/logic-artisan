"""Conformance guard: every SKILL.md is structurally loadable and its references resolve.

The plugin's behaviour lives mostly in markdown, so a prose edit ships like code
but nothing compiles it. Two failure shapes cost a whole skill and neither shows
up in any other scope:

  1. **Broken frontmatter.** A `SKILL.md` whose leading `---` block is malformed,
     unterminated, or missing `name`/`description` does not register as a skill at
     all. Every other test in this repo still passes; the skill is simply gone.
  2. **A dangling reference.** A `SKILL.md` that says "read `references/foo.md`"
     when no such file exists sends the model to a Read that fails mid-workflow.
     `test_project_facts_paths.py` builds an almost identical existence checker,
     but scopes it to `cla.io/project-facts.md` and the overlays — it never looks
     at the SKILL.md -> references graph itself. This file closes that gap.

Stdlib only, like every script in this plugin: the frontmatter parser below is a
deliberate 20-line subset (leading `---`, `key: value` at top level) rather than
an import of PyYAML. That subset is sufficient because the only keys any consumer
of this guard cares about are flat strings, and a real YAML dependency would be
the plugin's first third-party runtime requirement.

The checker obeys the split it enforces: generic *procedure* here, no repo facts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Claude Code shows a skill's `description` in the picker and matches natural
# language against it. There is no hard platform ceiling documented, so this is a
# STYLE ceiling, not a platform one: the longest description in the tree today is
# 852 chars (`sync-context`), and 1024 leaves room to grow while still failing a
# description that has quietly turned into a second SKILL.md body. Raise it
# deliberately if a skill genuinely needs more; do not raise it to silence a
# failure.
MAX_DESCRIPTION_CHARS = 1024

# A skill's own name must match its directory, or `/cla:<dir>` and the registered
# skill name diverge and the slash command silently does not exist.
REQUIRED_KEYS = ("name", "description")

_PLUGIN_ROOT = Path(__file__).resolve().parents[2]


def _skill_files():
    """Every `skills/<name>/SKILL.md`. A dir WITHOUT one is not a skill and is
    skipped — that is how a shared-reference directory under `skills/` stays
    invisible to the loader and to this guard alike."""
    root = _PLUGIN_ROOT / "skills"
    return sorted(p for p in root.glob("*/SKILL.md") if p.is_file())


def _referencing_files():
    """Every markdown file that can cite another file: each `SKILL.md` PLUS every
    `references/*.md` body.

    Scanning only `SKILL.md` was a real hole, not a theoretical one: a reference
    doc citing a moved file is just as dead as a SKILL.md citing one, and the
    bodies are where most cross-skill citations actually live. `_shared/` is
    included — it has no SKILL.md, but its references cite other files too."""
    root = _PLUGIN_ROOT / "skills"
    return sorted(
        set(_skill_files())
        | {p for p in root.glob("*/references/*.md") if p.is_file()}
    )


def _owning_skill_dir(path: Path) -> Path:
    """The skill directory a scanned file belongs to — its parent for a SKILL.md,
    its grandparent for a `references/*.md`."""
    return path.parent if path.name == "SKILL.md" else path.parent.parent


def parse_frontmatter(text: str):
    """Return (mapping, error). `error` is None on success.

    Deliberately strict about the shape Claude Code actually requires: the file
    must OPEN with `---` on line 1 and that block must be closed by a later line
    that is exactly `---`. Anything else is reported rather than guessed at,
    because a guess here would hide the very breakage this guard exists to catch.
    """
    if not text.startswith("---"):
        return None, "does not open with a `---` frontmatter delimiter on line 1"
    lines = text.splitlines()
    close = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            close = i
            break
    if close is None:
        return None, "frontmatter block is never closed by a `---` line"

    mapping = {}
    key = None
    for line in lines[1:close]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1] not in (" ", "\t") and ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            mapping[key] = value.strip()
        elif key is not None:
            # A folded/continued value line. Join with a space so a multi-line
            # description measures at roughly its rendered length.
            mapping[key] = (mapping[key] + " " + line.strip()).strip()
    return mapping, None


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def extract_reference_paths(text: str, skill_dir: Path):
    """Every concrete plugin file path a SKILL.md names, as (raw, resolved).

    Conservative on purpose, matching the extraction discipline of the sibling
    staleness guard: only two unambiguous shapes are checked, because a broad
    "anything that looks like a path" sweep false-positives on prose and a guard
    people learn to ignore is worse than no guard.

      - `references/<file>` relative to the skill's own directory
      - `${CLAUDE_PLUGIN_ROOT}/<anything>` anywhere in the tree

    A glob or placeholder segment (`*`, `<`, `>`) is skipped — it names a shape,
    not a file. The `(?<![\\w/])` lookbehind keeps an explicit cross-skill path
    (`skills/review-change/references/checklist.md`) out of the bare-relative
    bucket; only a genuinely bare `references/...` lands there.

    Leading frontmatter is excluded, the same exemption the sibling token guard
    makes and for the same reason: a `description:` is trigger metadata read by
    the skill picker, not procedure the model follows, so a path named there is
    describing the skill rather than telling anyone to open it.
    """
    import re

    _, err = parse_frontmatter(text)
    if err is None:
        lines = text.splitlines(keepends=True)
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                text = "".join(lines[i + 1 :])
                break

    out = []
    for raw in re.findall(r"(?<![\w/])references/[A-Za-z0-9._/-]+", text):
        out.append((raw, skill_dir / raw))
    for raw in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/[A-Za-z0-9._/-]+", text):
        rel = raw.split("}/", 1)[1]
        out.append((raw, _PLUGIN_ROOT / rel))
    # A skill-qualified relative path: `<skill>/references/<file>` or
    # `<skill>/scripts/<file>`, written without the `${CLAUDE_PLUGIN_ROOT}` prefix.
    # This shape is what a cross-skill citation degrades into, and it is exactly
    # what a file move strands: the earlier `spec-to-pr/references/...` -> `_shared/`
    # migration left six of them behind, invisible to the first two patterns.
    # The lookbehind must exclude `-` as well as word chars and `/`: without it
    # `codify-learnings/references/x.md` matches starting at `learnings/`, and
    # `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/x.md` matches at `to-pr/`
    # — both nonexistent owners, both reported as dangling. The owner must also be
    # a real skill directory, so an ordinary hyphenated prose word cannot qualify.
    for raw in re.findall(
        r"(?<![\w/${\-])([a-z_][a-z0-9_-]*/(?:references|scripts)/[A-Za-z0-9._-]+)", text
    ):
        owner, _, rest = raw.partition("/")
        if (_PLUGIN_ROOT / "skills" / owner).is_dir():
            out.append((raw, _PLUGIN_ROOT / "skills" / owner / rest))

    keep = []
    for raw, resolved in out:
        if any(ch in raw for ch in "*<>"):
            continue
        # Trim trailing punctuation that belongs to the prose, not the path.
        cleaned = raw.rstrip(".,;:)")
        if cleaned != raw:
            resolved = Path(str(resolved).rstrip(".,;:)"))
        keep.append((cleaned, resolved))
    return keep


def _resolves_under_some_other_skill(raw: str) -> bool:
    """True when a bare `references/<file>` exists under SOME skill — i.e. the
    citation is real but points at a sibling, so it reads as this skill's own."""
    leaf = raw.split("references/", 1)[1]
    return any(
        (d / "references" / leaf).is_file()
        for d in (_PLUGIN_ROOT / "skills").iterdir()
        if d.is_dir()
    )


def test_every_skill_has_parseable_frontmatter_with_required_keys():
    problems = []
    for path in _skill_files():
        rel = path.relative_to(_PLUGIN_ROOT).as_posix()
        mapping, error = parse_frontmatter(path.read_text(encoding="utf-8"))
        if error:
            problems.append(f"  {rel}: {error}")
            continue
        for key in REQUIRED_KEYS:
            if not mapping.get(key):
                problems.append(f"  {rel}: frontmatter has no non-empty `{key}:`")
        name = _unquote(mapping.get("name", ""))
        if name and name != path.parent.name:
            problems.append(
                f"  {rel}: frontmatter name `{name}` != directory `{path.parent.name}`; "
                "`/cla:<dir>` would not resolve to this skill"
            )
    assert not problems, (
        "SKILL.md frontmatter problems — a skill with broken frontmatter does not "
        "register at all, and every other test still passes:\n" + "\n".join(problems)
    )


def test_no_skill_description_has_grown_into_a_second_body():
    problems = []
    for path in _skill_files():
        mapping, error = parse_frontmatter(path.read_text(encoding="utf-8"))
        if error:
            continue  # reported by the frontmatter test
        desc = _unquote(mapping.get("description", ""))
        if len(desc) > MAX_DESCRIPTION_CHARS:
            problems.append(
                f"  {path.relative_to(_PLUGIN_ROOT).as_posix()}: "
                f"{len(desc)} chars > {MAX_DESCRIPTION_CHARS}"
            )
    assert not problems, (
        "skill description(s) over the style ceiling; a description is trigger "
        "metadata, not documentation:\n" + "\n".join(problems)
    )


def test_every_reference_a_skill_names_actually_exists():
    """A path that resolves NOWHERE in the plugin. This is the hard failure: the
    model is sent to a Read that cannot succeed."""
    problems = []
    for path in _referencing_files():
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(_PLUGIN_ROOT).as_posix()
        for raw, resolved in extract_reference_paths(text, _owning_skill_dir(path)):
            if resolved.exists():
                continue
            if raw.startswith("references/") and _resolves_under_some_other_skill(raw):
                continue  # real file, wrong owner — the ambiguity test below owns it
            problems.append(f"  {rel} -> {raw} (no such file anywhere in the plugin)")
    assert not problems, (
        "SKILL.md names a file that does not exist — the model is sent to a Read "
        "that fails mid-workflow:\n" + "\n".join(problems)
    )


def test_a_bare_reference_path_belongs_to_the_skill_that_writes_it():
    """A bare `references/<file>` reads as "my own reference". When it actually
    means a SIBLING skill's file, a reader resolving it literally opens nothing —
    the failure is a confused reader rather than a crash, which is why it is
    separated from the hard-failure test above rather than folded into it.

    The fix is always the same and always cheap: write the explicit
    `${CLAUDE_PLUGIN_ROOT}/skills/<owner>/references/<file>` path instead."""
    problems = []
    for path in _referencing_files():
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(_PLUGIN_ROOT).as_posix()
        for raw, resolved in extract_reference_paths(text, _owning_skill_dir(path)):
            if resolved.exists() or not raw.startswith("references/"):
                continue
            if _resolves_under_some_other_skill(raw):
                problems.append(
                    f"  {rel} -> {raw} (exists, but under another skill; "
                    "write the explicit ${CLAUDE_PLUGIN_ROOT} path)"
                )
    assert not problems, (
        "bare reference path(s) naming another skill's file:\n" + "\n".join(problems)
    )


def test_the_scan_is_not_vacuous():
    """A guard that scans nothing passes forever, and two guards in this repo
    already did once. Pinned near the real count (19 skills today), per the rule
    the sibling guards state: lower it to the new real count when something is
    deliberately deleted, never to a number chosen to be safe from deletions."""
    files = _skill_files()
    assert len(files) >= 17, f"skill scan collapsed to {len(files)} SKILL.md files"
    refs = sum(
        len(extract_reference_paths(p.read_text(encoding="utf-8"), p.parent))
        for p in files
    )
    assert refs >= 40, (
        f"only {refs} reference paths extracted across {len(files)} skills; the "
        "extraction regex has probably stopped matching rather than the skills "
        "having stopped citing their references"
    )


# ---------- the checkers' own behaviour, on seeded inputs ----------


def _seed(tmp_path: Path, rel: str, body: str) -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


@pytest.mark.parametrize(
    "body,expected",
    [
        ("no frontmatter here\n", "does not open"),
        ("---\nname: x\ndescription: y\n", "never closed"),
    ],
)
def test_parse_frontmatter_reports_each_broken_shape(body, expected):
    mapping, error = parse_frontmatter(body)
    assert mapping is None
    assert expected in error


def test_parse_frontmatter_reads_flat_keys_and_folds_continuations():
    mapping, error = parse_frontmatter(
        "---\nname: demo\ndescription: one\n  two\nallowed-tools: Read\n---\n\nBody.\n"
    )
    assert error is None
    assert mapping["name"] == "demo"
    assert mapping["description"] == "one two"
    assert mapping["allowed-tools"] == "Read"


def test_extract_reference_paths_skips_globs_and_placeholders(tmp_path):
    skill_dir = tmp_path / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    text = (
        "Read `references/real.md` first.\n"
        "Also `references/*.md` and `references/<name>.md` are shapes, not files.\n"
    )
    got = [raw for raw, _ in extract_reference_paths(text, skill_dir)]
    assert got == ["references/real.md"]


def test_extract_reference_paths_trims_trailing_prose_punctuation(tmp_path):
    skill_dir = tmp_path / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    got = [raw for raw, _ in extract_reference_paths("see references/a.md.\n", skill_dir)]
    assert got == ["references/a.md"]

def test_the_arg_placeholder_pattern_keeps_its_binding():
    """`$ARGUMENTS` is the harness's substitution token: a skill body sees its
    invocation argument only where that literal appears.

    A skill that adopts the bind-once pattern (`<arg>` = `$ARGUMENTS`, then every
    later rule says `<arg>`) must keep exactly one binding site. Dropping to zero
    while the prose still reasons about `<arg>` means the argument never arrives
    and the skill runs argument-blind — a silent failure with no other symptom.
    This is not hypothetical: the edit that introduced the pattern removed every
    occurrence, and this test is what caught it.

    The upper bound is the token-waste half: re-embedding the raw token per rule
    interpolates a long invocation once per mention.

    Deliberately NOT asserted: that every skill with an `argument-hint` names
    `$ARGUMENTS`. Several hints read "(no args)", and whether the remainder read
    their argument from the token or from conversation context is unverified —
    asserting it here would be a guess wearing a test."""
    problems = []
    for path in _skill_files():
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(_PLUGIN_ROOT).as_posix()
        n = text.count("$ARGUMENTS")
        if "`<arg>`" in text and n != 1:
            problems.append(
                f"  {rel}: uses the `<arg>` placeholder but has {n} `$ARGUMENTS` "
                "binding site(s); it needs exactly 1"
            )
        elif n > 3:
            problems.append(
                f"  {rel}: $ARGUMENTS appears {n} times; bind it once to a "
                "placeholder instead of re-embedding a long invocation"
            )
    assert not problems, "argument-binding problems:\n" + "\n".join(problems)
