"""cla-setup writes the repo's economy rules file, and the text comes from sources that exist once.

`/cla:cla-setup` item 7a renders `skills/_shared/references/economy-rules-file.md` with two sources
inlined at its include markers (`orchestration-economy.md` whole, and the span of
`model-routing.md` between its review-sizing markers) into `.claude/rules/cla-economy.md` in a
consuming repo. The plugin owns that file whole and replaces it on every run. The block is
extracted from `SKILL.md` and run under bash here, with the plugin root substituted as a literal
(it is text in the skill, not an environment variable). Every test writes only under `tmp_path`.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_SKILLS = _REPO / ".claude" / "plugins" / "cla" / "skills"
_SKILL = _SKILLS / "cla-setup" / "SKILL.md"
_REFS = _SKILLS / "_shared" / "references"
_ROUTING = _REFS / "model-routing.md"
_ECONOMY = _REFS / "orchestration-economy.md"
_FRAME = _REFS / "economy-rules-file.md"
_SOURCES = ("economy-rules-file.md", "orchestration-economy.md", "model-routing.md")
_BASH = shutil.which("bash")
_GIT = shutil.which("git")
_RULES = Path(".claude") / "rules" / "cla-economy.md"
_BEGIN = "<!-- economy-rules-file:review-sizing:begin -->"
_END = "<!-- economy-rules-file:review-sizing:end -->"
# Names that mean nothing in a repo with no plugin installed.
_PLUGIN_ONLY = ("/cla:", "lite-pr", "multi-lite", "multi-pr", "multi-spec", "spec-to-pr", "Handoff Issue",
                "revise.md", "model-routing.md", "orchestration-economy.md", "--pr-rounds")

_needs_tools = pytest.mark.skipif(_BASH is None or _GIT is None, reason="bash and git are required")


def _skill_text() -> str:
    return _SKILL.read_text(encoding="utf-8")


def _block() -> str:
    match = re.search(r"```bash\n(: \"\$\{ROOT:\?[^`]*?cla-economy\.md[^`]*?)```", _skill_text())
    assert match, "cla-setup/SKILL.md: no economy-rules-file block found"
    return match.group(1)


def _plugin(dest: Path, crlf: bool = False, edit=None) -> Path:
    """A copy of the three sources under `dest`, laid out as the block reads them."""
    refs = dest / "skills" / "_shared" / "references"
    refs.mkdir(parents=True)
    for name in _SOURCES:
        text = (_REFS / name).read_bytes().decode("utf-8").replace("\r\n", "\n")
        if edit is not None:
            text = edit(name, text)
        refs.joinpath(name).write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    return dest


def _bash(script: str, root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_BASH, "-c", script],
        # Forward slashes: a POSIX shell reads `C:\...` backslashes as escapes.
        env={**os.environ, "ROOT": str(root).replace("\\", "/")},
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
    )


def _run(root: Path, plugin: Path) -> str:
    script = _block().replace("${CLAUDE_PLUGIN_ROOT}", plugin.as_posix())
    out = _bash(script, root)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def _written(root: Path) -> str:
    return (root / _RULES).read_bytes().decode("utf-8")


# requirement: repo-context / Setting up a repo's cla.io tree and economy rules file
@_needs_tools
def test_a_repo_without_the_file_gets_it_created_with_no_paths_frontmatter(tmp_path: Path) -> None:
    root, plugin = tmp_path / "repo", _plugin(tmp_path / "plugin")
    root.mkdir()
    assert _run(root, plugin) == ".claude/rules/cla-economy.md: created"
    text = _written(root)
    assert text.startswith("# Economy rules"), "the file must open on its heading, not frontmatter"
    assert not re.search(r"^paths:", text, re.M)
    assert not text.startswith("---")


# requirement: repo-context / Setting up a repo's cla.io tree and economy rules file
@_needs_tools
def test_an_edited_copy_is_replaced_and_the_next_run_is_unchanged(tmp_path: Path) -> None:
    root, plugin = tmp_path / "repo", _plugin(tmp_path / "plugin")
    root.mkdir()
    _run(root, plugin)
    fresh = (root / _RULES).read_bytes()
    (root / _RULES).write_bytes(fresh + b"a hand edit\n")
    assert _run(root, plugin) == ".claude/rules/cla-economy.md: replaced"
    assert (root / _RULES).read_bytes() == fresh
    assert _run(root, plugin) == ".claude/rules/cla-economy.md: unchanged"
    assert (root / _RULES).read_bytes() == fresh


def _part_1_blocks() -> list[str]:
    text = _skill_text()
    part_1 = text.split("## Part 1 — Structure", 1)[1].split("## Part 2 — Facts", 1)[0]
    return re.findall(r"```bash\n(.*?)```", part_1, re.S)


def _hashes(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file() and ".git" not in p.relative_to(root).parts}


# requirement: repo-context / Setting up a repo's cla.io tree and economy rules file
@_needs_tools
def test_a_full_part_1_run_changes_no_existing_file_but_the_gitignore_and_the_rules_file(tmp_path: Path) -> None:
    root, plugin = tmp_path / "repo", _plugin(tmp_path / "plugin")
    root.mkdir()
    subprocess.run([_GIT, "init", "-q", str(root)], check=True, capture_output=True)
    existing = {
        "CLAUDE.md": "# the repo's own rules\n",
        "README.md": "readme\n",
        ".gitignore": "node_modules/\n",
        ".claude/rules/cla-economy.md": "a stale copy\n",
        ".claude/rules/own.md": "the repo's own rule file\n",
        "openspec/config.yaml": "schema: spec-driven\n",
        "cla.io/feedback/notes.md": "filled notes\n",
        "cla.io/retro/spec-to-pr-runs.jsonl": '{"a": 1}\n',
    }
    for name, body in existing.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(body, encoding="utf-8", newline="")
    before = _hashes(root)
    blocks = _part_1_blocks()
    assert any("cla-economy.md" in b for b in blocks) and len(blocks) >= 7
    for block in blocks:
        out = _bash(block.replace("${CLAUDE_PLUGIN_ROOT}", plugin.as_posix()), root)
        assert out.returncode == 0, out.stderr
    after = _hashes(root)
    changed = {name for name in before if after.get(name) != before[name]}
    assert changed == {".gitignore", ".claude/rules/cla-economy.md"}
    assert after["CLAUDE.md"] == before["CLAUDE.md"]
    assert (root / ".gitignore").read_text(encoding="utf-8").startswith("node_modules/\n")


# requirement: repo-context / Setting up a repo's cla.io tree and economy rules file
@_needs_tools
def test_the_written_file_holds_both_sources_and_no_plugin_only_name(tmp_path: Path) -> None:
    root, plugin = tmp_path / "repo", _plugin(tmp_path / "plugin")
    root.mkdir()
    _run(root, plugin)
    text = _written(root)
    rules = re.findall(r"^\d+\. \*\*(.+?)\*\*", _ECONOMY.read_text(encoding="utf-8"), re.M)
    assert len(rules) >= 7, "the economy source lost its numbered rules"
    for title in rules:
        assert title in text, f"the economy rule {title!r} is missing from the written file"
    assert "git status --porcelain --ignored --untracked-files=all" in text
    for row in ("| Low risk, docs | `comment-analyzer` | Sonnet |", "| Low risk, code | `code-reviewer` | Sonnet |",
                "| High risk | `code-reviewer` + `silent-failure-hunter` | Opus |"):
        assert row in text, f"the sizing table row {row!r} is missing"
    assert "Unsure means high" in text and "never lower" in text
    assert "Artifact-class override" not in text
    assert "<!--" not in text, "an include or extraction marker leaked into the written file"
    assert "${CLAUDE_PLUGIN_ROOT}" not in text
    for name in _PLUGIN_ONLY:
        assert name not in text, f"the written file names {name!r}, which means nothing without the plugin"


# requirement: repo-context / Setting up a repo's cla.io tree and economy rules file
@_needs_tools
def test_crlf_and_lf_sources_render_the_same_bytes_and_compare_unchanged(tmp_path: Path) -> None:
    crlf_plugin = _plugin(tmp_path / "crlf", crlf=True)
    lf_plugin = _plugin(tmp_path / "lf")
    from_crlf, from_lf = tmp_path / "from_crlf", tmp_path / "from_lf"
    from_crlf.mkdir()
    from_lf.mkdir()
    assert _run(from_crlf, crlf_plugin) == ".claude/rules/cla-economy.md: created"
    assert _run(from_lf, lf_plugin) == ".claude/rules/cla-economy.md: created"
    assert (from_crlf / _RULES).read_bytes() == (from_lf / _RULES).read_bytes()
    assert b"\r" not in (from_crlf / _RULES).read_bytes()
    assert _run(from_crlf, lf_plugin) == ".claude/rules/cla-economy.md: unchanged"
    assert _run(from_lf, crlf_plugin) == ".claude/rules/cla-economy.md: unchanged"


# requirement: repo-context / Setting up a repo's cla.io tree and economy rules file
@_needs_tools
def test_the_markers_occur_once_and_a_footnote_after_the_table_still_extracts(tmp_path: Path) -> None:
    routing = _ROUTING.read_text(encoding="utf-8")
    assert routing.count(_BEGIN) == 1 and routing.count(_END) == 1
    assert routing.index(_BEGIN) < routing.index("## Review sizing by risk") < routing.index(_END)
    assert routing.index(_END) < routing.index("### Artifact-class override")
    footnote = "A footnote added after the sizing table."
    plugin = _plugin(tmp_path / "plugin", edit=lambda name, text: (
        text.replace(_END, footnote + "\n" + _END) if name == "model-routing.md" else text))
    root = tmp_path / "repo"
    root.mkdir()
    _run(root, plugin)
    assert footnote in _written(root)


# requirement: repo-context / Setting up a repo's cla.io tree and economy rules file
@_needs_tools
def test_a_missing_source_or_plugin_root_writes_nothing_and_says_so(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    no_markers = _plugin(tmp_path / "plugin", edit=lambda name, text: (
        text.replace(_BEGIN, "").replace(_END, "") if name == "model-routing.md" else text))
    out = _bash(_block().replace("${CLAUDE_PLUGIN_ROOT}", no_markers.as_posix()), root)
    assert out.returncode != 0 and "NOT written" in out.stdout
    assert not (root / _RULES).exists()
    # An unsubstituted `${CLAUDE_PLUGIN_ROOT}` expands to nothing in the shell.
    unresolved = _bash(_block(), root)
    assert unresolved.returncode != 0 and "plugin root unresolved" in unresolved.stdout
    assert not (root / _RULES).exists()


# requirement: repo-context / Setting up a repo's cla.io tree and economy rules file
@pytest.mark.parametrize("chain", ["multi-lite", "multi-pr", "multi-spec"])
def test_each_chain_names_the_rules_file_reference_and_copies_none_of_its_rules(chain: str) -> None:
    text = (_SKILLS / chain / "SKILL.md").read_text(encoding="utf-8")
    assert "skills/_shared/references/economy-rules-file.md" in text, f"{chain}/SKILL.md does not name the reference"
    own = " ".join(text.split())
    prose = [line for line in _FRAME.read_text(encoding="utf-8").splitlines() if not line.startswith(("#", "<!--"))]
    words = " ".join(prose).split()
    assert len(words) > 100, "the reference lost its authored text"
    for i in range(len(words) - 7):
        window = " ".join(words[i:i + 8])
        assert window not in own, f"{chain}/SKILL.md copies the reference: {window!r}"
