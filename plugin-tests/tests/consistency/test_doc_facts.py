"""Drift guard: three facts this repo's docs restate must match their source.

1. The release version: `CLAUDE.md`'s "Current release" line must name the
   version in `plugin.json` (which `test_marketplace_manifest.py` pins to the
   marketplace `ref`). `/release` edits all three in one commit.
2. Every guard hook a doc names in backticks has a file under `hooks/`.
3. Whether Claude may invoke a skill: a value that lives in each `SKILL.md`'s
   frontmatter (`disable-model-invocation`) and is restated in the plugin
   README's phase table and in a sentence naming the skills in `CLAUDE.md` and
   `DEVELOPER-GUIDE.md`.

Restated counts (skills, scopes, hooks) are no longer checked here.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

_PLUGIN_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
_REPO_ROOT = _PLUGIN_ROOT.parents[2]

_DOCS = {
    "CLAUDE.md": _REPO_ROOT / "CLAUDE.md",
    "README.md": _REPO_ROOT / "README.md",
    "DEVELOPER-GUIDE.md": _REPO_ROOT / "DEVELOPER-GUIDE.md",
    "plugin README.md": _PLUGIN_ROOT / "README.md",
}


def test_the_release_version_agrees_across_the_manifest_and_the_prose():
    """`test_marketplace_manifest.py` already pins plugin.json against the
    marketplace ref. CLAUDE.md carries a third copy that nothing checked, and it
    sat one release stale until a review caught it."""
    version = json.loads(
        (_PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )["version"]
    claude_md = _DOCS["CLAUDE.md"].read_text(encoding="utf-8")
    match = re.search(r"\*\*Current release: `cla--v([0-9.]+)`", claude_md)
    assert match, (
        "CLAUDE.md no longer states `**Current release: `cla--v<version>`**`. Either "
        "restore that phrasing or delete this assertion deliberately — do not let "
        "the claim drift back in unchecked."
    )
    assert match.group(1) == version, (
        f"CLAUDE.md says release {match.group(1)}, plugin.json says {version}"
    )


def test_every_named_leaf_hook_exists():
    """A 2026-08 review found six invented hook names in a single guide section.
    A backticked `block-`/`ask-`/`warn-`/`guard-` name is read as a live hook;
    mention a deleted one WITHOUT backticks if the reference is historical.

    The `(?:\\.py)?` is load-bearing, not decoration: without it a backticked
    `` `guard-x.py` `` matched nothing at all — the character class cannot match a
    dot — so the one spelling most likely to name a real hook file was the one
    spelling this guard could not see."""
    missing = []
    for name, path in _DOCS.items():
        text = path.read_text(encoding="utf-8")
        for hook in re.findall(r"`((?:block|ask|warn|guard)-[a-z0-9-]+(?:\.py)?)`", text):
            stem = hook[:-3] if hook.endswith(".py") else hook
            if not (_PLUGIN_ROOT / "hooks" / f"{stem}.py").is_file():
                missing.append(f"  {name}: `{hook}` has no hooks/{stem}.py")
    assert not missing, (
        "doc names a guard hook that does not exist on disk:\n" + "\n".join(missing)
    )


# --- ground truth: the phase table's "Invoked by" column ---------------------
#
# The column restates a fact that lives in each skill's frontmatter, which is
# this file's whole subject: a derived value copied into prose goes stale when
# the source changes and nothing reads the prose. The named rot is a THIRD skill
# setting `disable-model-invocation: true` while the table still shows it as
# model-invocable, telling a reader Claude may start an unattended orchestrator
# on a description match.
#
# **Read the frontmatter with the repo's parser, not a string compare.** The
# first draft of this guard tested `line.strip() == "disable-model-invocation:
# true"`, which is one of at least six legal YAML spellings of that fact — and
# review found it misses `True`, `yes`, `"true"`, a doubled space, and an inline
# `# comment`. The last is the likely one: BOTH existing skills already carry
# exactly that rationale as a comment on the preceding lines, so an author
# shortening it to one line disarms the guard. Worse, it disarms it in the
# silent direction — if the table is also not updated, both sets stay at two and
# the guard passes in its own headline scenario.
#
# `test_skill_lint.parse_frontmatter` already bounds the block strictly, skips
# comment lines, and splits on `partition(":")`. It lives in another area
# directory, so it is loaded by path with `importlib`. Duplicating it here would
# give this repo two frontmatter parsers that can disagree, which is the class of
# defect the whole file exists to catch.

_USER_ONLY_MARK = "**you only**"

# Every value the Invoked by column may hold. Asserted as a closed set so that a
# DELETED cell, or a real skill relabelled as a non-skill row, is caught — the
# marked-set comparison below sees neither, because both leave the marks alone.
_LEGAL_INVOCATION_CELLS = {
    "you or Claude",
    _USER_ONLY_MARK,
    "n/a — vendored",
    "n/a — dispatched",
}

# YAML's spellings of true. `parse_frontmatter` hands back the raw value with an
# inline comment still attached, so the comment is stripped before comparison.
_YAML_TRUE = {"true", "yes", "on"}

_TABLE_HEADER = "| Phase | Skill | Invoked by | What it does |"


def _load_parse_frontmatter():
    """The repo's one frontmatter parser, loaded from the conformance area.

    Not importable by name: `tests/conformance` is not on `pythonpath` (see
    `plugin-tests/pyproject.toml`), and relying on pytest's import-mode side
    effects would make this depend on collection order.
    """
    path = Path(__file__).resolve().parents[1] / "conformance" / "test_skill_lint.py"
    spec = importlib.util.spec_from_file_location("_skill_lint_for_doc_facts", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.parse_frontmatter


def _declares_user_only(text: str) -> bool:
    """True when this SKILL.md's frontmatter forbids model invocation."""
    mapping, error = _load_parse_frontmatter()(text)
    if error is not None:
        # A malformed SKILL.md is `test_skill_lint`'s finding, not this one.
        # Reporting it here too would give one defect two owners.
        return False
    value = mapping.get("disable-model-invocation", "")
    return value.split("#")[0].strip().strip("\"'").lower() in _YAML_TRUE


def skills_declaring_user_only(skills_dir: Path | None = None) -> set[str]:
    """Skills whose frontmatter forbids model invocation — from the source."""
    skills_dir = (_PLUGIN_ROOT / "skills") if skills_dir is None else skills_dir
    return {
        skill_md.parent.name
        for skill_md in skills_dir.glob("*/SKILL.md")
        if _declares_user_only(skill_md.read_text(encoding="utf-8"))
    }


def phase_table_rows(readme: Path | None = None) -> list[list[str]]:
    """The phase table's body rows, as lists of stripped cells.

    Bounded to the table rather than scanning every `|` line in the file. The
    README carries a second table (`Dependency | Reached by | How hard`), and a
    guard reading both would feed its columns into a comparison about skills.
    """
    readme = _DOCS["plugin README.md"] if readme is None else readme
    rows: list[list[str]] = []
    inside = False
    for line in readme.read_text(encoding="utf-8").splitlines():
        if line.strip() == _TABLE_HEADER:
            inside = True
            continue
        if not inside:
            continue
        if not line.startswith("|"):
            break
        if set(line.replace("|", "").strip()) <= {"-"}:
            continue  # the |---|---| separator
        rows.append([c.strip() for c in line.split("|")[1:-1]])
    return rows


def _row_skill_name(row: list[str]) -> str:
    """The skill a row names, or '' for the two non-skill rows."""
    name = row[1].strip("`() ")
    return "" if name.startswith("opsx:") or name == "agents" else name


def skills_marked_user_only_in_the_table(readme: Path | None = None) -> set[str]:
    """Skills the phase table marks user-invoked only.

    Reads cell 2 — the Invoked by column — rather than searching the whole row.
    An earlier draft used `mark in line`, which counted a row whose Invoked by
    cell said `you or Claude` and whose *description* happened to contain the
    marker: the guard agreed with the frontmatter while the column said the
    opposite of it.
    """
    readme = _DOCS["plugin README.md"] if readme is None else readme
    return {
        name
        for row in phase_table_rows(readme)
        if len(row) == 4 and row[2] == _USER_ONLY_MARK and (name := _row_skill_name(row))
    }


def test_the_invocation_column_is_not_vacuous() -> None:
    """Both halves must be non-empty AND at their real size.

    Two empty sets are equal, so the match test below passes on a tree where the
    column was deleted and every skill dropped the frontmatter key. The floor is
    the real population, not a decorative 1: measured with
    `grep -l '^disable-model-invocation: true' .claude/plugins/cla/skills/*/SKILL.md | wc -l`
    -> 2 (multi-lite, multi-pr). A floor below its population permits the
    shrinkage it exists to catch.
    """
    declared = skills_declaring_user_only()
    marked = skills_marked_user_only_in_the_table()
    assert len(declared) >= 2, (
        f"{len(declared)} skill(s) declare `disable-model-invocation: true`; the "
        f"tree had 2 when this floor was written. A genuine drop to one means "
        f"deleting a skill — update the floor in that commit, never to go green."
    )
    assert len(marked) >= 2, (
        f"the phase table marks {len(marked)} skill(s) {_USER_ONLY_MARK}. Either "
        f"the column was dropped or its marker was reworded."
    )


def test_the_invocation_column_matches_the_frontmatter() -> None:
    declared = skills_declaring_user_only()
    marked = skills_marked_user_only_in_the_table()
    assert marked == declared, (
        f"the phase table marks {sorted(marked)} as user-invoked only, but the "
        f"frontmatter declares {sorted(declared)}. The frontmatter is the source: "
        f"a skill sets `disable-model-invocation: true` and the table follows it, "
        f"never the other way round."
    )


def test_every_invocation_cell_holds_a_legal_value() -> None:
    """Catches a DELETED cell and a mislabelled row, which the set match cannot.

    Dropping the Invoked by cell from an unmarked row, or relabelling a real
    skill `n/a — dispatched`, leaves both marked sets untouched — so without
    this the table can misalign or lie about 21 of its 23 rows in silence.

    Counted with this module's own `phase_table_rows()`: 23 body rows, of which
    `_row_skill_name` reads 21 as naming a shipped skill and 2 as non-skill
    rows; the Invoked by column holds 13 `you or Claude`, 8 `**you only**`,
    1 `n/a — vendored` and 1 `n/a — dispatched`. The set match above pins only
    the 8 marked cells, which is where the other 15 come from.
    """
    for row in phase_table_rows():
        assert len(row) == 4, f"phase-table row has {len(row)} cells, expected 4: {row}"
        assert row[2] in _LEGAL_INVOCATION_CELLS, (
            f"row {row[1]!r} has Invoked by {row[2]!r}, which is not one of "
            f"{sorted(_LEGAL_INVOCATION_CELLS)}."
        )
        # The value has to agree with WHAT THE ROW IS, or `n/a` becomes a way to
        # opt a real skill out of the column: relabelling `annotate` as
        # `n/a — dispatched` kept every marked set identical and survived as a
        # mutant until this pair was added.
        names_a_skill = bool(_row_skill_name(row))
        if names_a_skill:
            assert not row[2].startswith("n/a"), (
                f"row {row[1]!r} names a shipped skill but its Invoked by cell "
                f"is {row[2]!r}. `n/a` is for the two rows that are not CLA "
                f"skills; a skill has a real invocation model."
            )
        else:
            assert row[2].startswith("n/a"), (
                f"row {row[1]!r} is not a CLA skill but its Invoked by cell is "
                f"{row[2]!r}. Its invocation model is not CLA's to state."
            )


def _shipped_skill_names(skills_dir: Path | None = None) -> set[str]:
    """Every skill that ships a SKILL.md — the population the docs describe."""
    skills_dir = (_PLUGIN_ROOT / "skills") if skills_dir is None else skills_dir
    return {p.parent.name for p in skills_dir.glob("*/SKILL.md")}


def test_the_phase_table_names_every_shipped_skill() -> None:
    """A skill added with no row, or a row left behind for a deleted skill."""
    tabled = {n for row in phase_table_rows() if (n := _row_skill_name(row))}
    on_disk = _shipped_skill_names()
    assert tabled == on_disk, (
        f"the phase table names {sorted(tabled - on_disk)} which ship no SKILL.md, "
        f"and omits {sorted(on_disk - tabled)} which do."
    )


# The two tests above run against the live tree, where the defect is absent by
# construction — so neither has been SHOWN able to fire. These feed the helpers
# a synthetic tree instead, which `test-quality-gates.md` calls the better of the two
# ways out: a planted failure is evidence at one moment, a test supplying bad
# state keeps holding after a refactor turns the check into a no-op.


def _write_skill(root: Path, name: str, frontmatter: str) -> None:
    (root / name).mkdir(parents=True)
    (root / name / "SKILL.md").write_text(
        f"---\nname: {name}\n{frontmatter}---\n\n# {name}\n", encoding="utf-8"
    )


def test_the_frontmatter_reader_accepts_every_yaml_spelling_of_true(tmp_path) -> None:
    """The Critical this guard shipped with: one spelling of six was matched."""
    for i, value in enumerate(
        ["true", "True", '"true"', "yes", "true  # unattended orchestrator", " true"]
    ):
        _write_skill(tmp_path, f"skill{i}", f"disable-model-invocation:{value}\n")
    _write_skill(tmp_path, "ordinary", "argument-hint: something\n")
    found = skills_declaring_user_only(tmp_path)
    assert found == {f"skill{i}" for i in range(6)}, (
        f"a legal YAML spelling of true went unread: got {sorted(found)}. A skill "
        f"this misses is one the table is never forced to label."
    )


def test_the_frontmatter_reader_is_not_fooled_by_the_body(tmp_path) -> None:
    """A `---` rule in the body must not open a second frontmatter block."""
    (tmp_path / "prose").mkdir(parents=True)
    (tmp_path / "prose" / "SKILL.md").write_text(
        "---\nname: prose\n---\n\n# prose\n\n---\n\ndisable-model-invocation: true\n",
        encoding="utf-8",
    )
    assert skills_declaring_user_only(tmp_path) == set()


def test_the_table_reader_ignores_a_mark_outside_the_invocation_cell(tmp_path) -> None:
    """The Important this guard shipped with: `mark in line`, not `in the cell`."""
    readme = tmp_path / "README.md"
    readme.write_text(
        f"{_TABLE_HEADER}\n|---|---|---|---|\n"
        f"| | `multi-lite` | you or Claude | start it {_USER_ONLY_MARK} |\n",
        encoding="utf-8",
    )
    assert skills_marked_user_only_in_the_table(readme) == set(), (
        "a marker in the description cell was counted as an invocation mark, so "
        "the column could say the opposite of the frontmatter and still agree."
    )


def test_the_table_reader_stops_at_the_end_of_the_phase_table(tmp_path) -> None:
    """A later table's rows must not be read as phase-table rows."""
    readme = tmp_path / "README.md"
    readme.write_text(
        f"{_TABLE_HEADER}\n|---|---|---|---|\n"
        f"| | `multi-pr` | {_USER_ONLY_MARK} | chains spec-to-pr |\n"
        "\n## Another section\n\n"
        f"| Dependency | Reached by | How hard |\n|---|---|---|\n"
        f"| **OpenSpec** | `spec-to-pr` | {_USER_ONLY_MARK} |\n",
        encoding="utf-8",
    )
    assert skills_marked_user_only_in_the_table(readme) == {"multi-pr"}


# The same derived fact, in the two docs that are not the table.
#
# `CLAUDE.md` and `DEVELOPER-GUIDE.md` each qualify their "invocable by natural
# language" sentence by NAMING the user-only skills. That is the same copied
# derived value the assertions above exist for, and without these the guard's own
# headline failure mode — another skill sets the key, the copy still names the old set —
# stays alive in two files, in the commit that added the guard against it.

_INVOCATION_CLAIM_PHRASE = "disable-model-invocation"

# A block break: a blank line, a list marker, or a heading. Bounding the claim to
# ONE bullet or ONE paragraph is what makes reading skill names out of it sound —
# the whole bullet list, or a section, would sweep in names from prose that makes
# no claim about invocation, and the assertion would fail on unrelated edits.
_BLOCK_BREAK = re.compile(r"^(?:[-*+] |\d+\. |#)")


def _claim_blocks(text: str, phrase: str) -> list[str]:
    """Every block of `text` that mentions `phrase`, as joined text."""
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or _BLOCK_BREAK.match(stripped):
            if current:
                blocks.append(current)
            current = []
        if stripped:
            current.append(line)
    if current:
        blocks.append(current)
    return ["\n".join(b) for b in blocks if phrase in "\n".join(b)]


def _skills_named_in(block: str, skills_dir: Path | None = None) -> set[str]:
    """The shipped skills a block of prose names in backticks."""
    on_disk = _shipped_skill_names(skills_dir)
    return {t for t in re.findall(r"`([^`]+)`", block) if t in on_disk}


@pytest.mark.parametrize("name", ["CLAUDE.md", "DEVELOPER-GUIDE.md"])
def test_every_doc_naming_the_user_only_skills_names_the_real_ones(name) -> None:
    """The third and fourth copies of the fact the phase table restates."""
    blocks = _claim_blocks(
        _DOCS[name].read_text(encoding="utf-8"), _INVOCATION_CLAIM_PHRASE
    )
    assert len(blocks) == 1, (
        f"{name} has {len(blocks)} passage(s) mentioning "
        f"`{_INVOCATION_CLAIM_PHRASE}`, expected exactly 1. Zero means the "
        f"qualification was dropped and the doc is back to claiming every skill "
        f"is model-invocable; more than one means two copies that can disagree, "
        f"and this guard cannot know which one a reader trusts."
    )
    named = _skills_named_in(blocks[0])
    assert named == skills_declaring_user_only(), (
        f"{name} names {sorted(named)} as the skills Claude may not invoke, but "
        f"the frontmatter declares {sorted(skills_declaring_user_only())}. The "
        f"frontmatter is the source; every doc that restates it follows."
    )


def test_the_claim_block_is_bounded_by_its_own_bullet(tmp_path) -> None:
    """A neighbouring bullet's skill names must not be read into the claim.

    The live docs pass by construction, so this feeds the reader prose whose
    neighbouring bullet names a skill the claim does not. An unbounded reader
    returns `annotate` too and the assertion above fails on an edit that is
    correct — which is how a guard gets loosened rather than fixed.
    """
    skills = tmp_path / "skills"
    for skill in ("multi-lite", "multi-pr", "annotate"):
        _write_skill(skills, skill, "argument-hint: x\n")
    doc = (
        "- **Skills** — all but `multi-lite` and `multi-pr`, which set\n"
        "  `disable-model-invocation: true`, answer to natural language.\n"
        "- **Pages** — `annotate` renders one.\n"
    )
    blocks = _claim_blocks(doc, _INVOCATION_CLAIM_PHRASE)
    assert len(blocks) == 1
    assert _skills_named_in(blocks[0], skills) == {"multi-lite", "multi-pr"}
