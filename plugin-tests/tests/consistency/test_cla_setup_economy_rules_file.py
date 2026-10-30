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
def _find_bash() -> str | None:
    """Git Bash on Windows, else the first `bash` on PATH that can read a `C:/`-style path.

    On Windows `shutil.which("bash")` can resolve to the WSL launcher, which cannot read `C:/`
    paths, so the git install's own bash is tried first and every candidate is probed."""
    candidates: list[str] = []
    git = shutil.which("git")
    if git:
        for parent in Path(git).resolve().parents:
            for rel in (("usr", "bin", "bash.exe"), ("bin", "bash.exe")):
                if parent.joinpath(*rel).is_file():
                    candidates.append(str(parent.joinpath(*rel)))
    found = shutil.which("bash")
    if found:
        candidates.append(found)
    for candidate in candidates:
        try:
            probe = subprocess.run([candidate, "-c", f'test -r "{_SKILL.as_posix()}"'], capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            continue
        if probe.returncode == 0:
            return candidate
    return None


_BASH = _find_bash()
# A bash run is slow on Windows and parallel workers multiply it; keep generous headroom.
_BASH_TIMEOUT = 120
_GIT = shutil.which("git")
_RULES = Path(".claude") / "rules" / "cla-economy.md"
_BEGIN = "<!-- economy-rules-file:review-sizing:begin -->"
_END = "<!-- economy-rules-file:review-sizing:end -->"
# Names that mean nothing in a repo with no plugin installed.
_PLUGIN_ONLY = ("/cla:", "lite-pr", "multi-lite", "multi-pr", "multi-spec", "spec-to-pr", "Handoff Issue",
                "revise.md", "model-routing.md", "orchestration-economy.md", "--pr-rounds")

_needs_tools = pytest.mark.skipif(
    _BASH is None or _GIT is None or shutil.which("python3") is None,
    reason="bash, git and python3 are required (Part 1 item 5 runs a python3 script)",
)


def _skill_text() -> str:
    return _SKILL.read_text(encoding="utf-8")


def _block() -> str:
    match = re.search(r"```bash\n(: \"\$\{ROOT:\?[^`]*?cla-economy\.md[^`]*?)```", _skill_text())
    assert match, "cla-setup/SKILL.md: no economy-rules-file block found"
    return match.group(1)


def _plugin(dest: Path, crlf: bool = False, edit=None) -> Path:
    """A copy of the three sources, and the seed script item 5 runs, under `dest`, laid out as the blocks read them."""
    refs = dest / "skills" / "_shared" / "references"
    refs.mkdir(parents=True)
    scripts = dest / "skills" / "cla-setup" / "scripts"
    scripts.mkdir(parents=True)
    shutil.copyfile(_SKILLS / "cla-setup" / "scripts" / "seed_openspec_rules.py", scripts / "seed_openspec_rules.py")
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
        # No CLAUDE_PLUGIN_ROOT: the block gets the plugin path only as text substituted into it.
        env={**{k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"},
             "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
             "ROOT": str(root).replace("\\", "/")},
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=_BASH_TIMEOUT,
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
    assert _run(root, plugin).splitlines()[0] == ".claude/rules/cla-economy.md: replaced"
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
    # Only the lessons log was missing; no overlay and nothing else is created.
    assert set(after) - set(before) == {"cla.io/lessons-learned/lessons-learned.md"}
    assert not (root / "cla.io" / "overlays").exists()
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
    # The one plugin name allowed: the file says which command rewrites it.
    scanned = text.replace("`/cla:cla-setup`", "")
    for name in _PLUGIN_ONLY:
        assert name not in scanned, f"the written file names {name!r}, which means nothing without the plugin"
    assert "`/cla:cla-setup`" in text, "the file does not name the setup step that rewrites it"


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


def _rendered(tmp_path: Path, name: str = "good") -> tuple[Path, Path, bytes]:
    """A repo holding a correctly written rules file, its plugin copy, and the file's bytes."""
    root, plugin = tmp_path / f"{name}-repo", _plugin(tmp_path / f"{name}-plugin")
    root.mkdir()
    assert _run(root, plugin) == ".claude/rules/cla-economy.md: created"
    return root, plugin, (root / _RULES).read_bytes()


def _part_1_block(marker: str) -> str:
    matches = [b for b in _part_1_blocks() if marker in b]
    assert len(matches) == 1, f"{len(matches)} Part 1 blocks hold {marker!r}"
    return matches[0]


# requirement: repo-context / Setting up a repo's cla.io tree and economy rules file
@_needs_tools
def test_a_full_part_1_run_on_an_empty_repo_builds_the_tree_and_creates_no_overlay(tmp_path: Path) -> None:
    root, plugin = tmp_path / "repo", _plugin(tmp_path / "plugin")
    root.mkdir()
    subprocess.run([_GIT, "init", "-q", str(root)], check=True, capture_output=True)
    for block in _part_1_blocks():
        out = _bash(block.replace("${CLAUDE_PLUGIN_ROOT}", plugin.as_posix()), root)
        assert out.returncode == 0, out.stderr
    files = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and ".git" not in p.relative_to(root).parts}
    assert files == {
        "cla.io/retro/spec-to-pr-runs.jsonl", "cla.io/feedback/notes.md",
        "cla.io/lessons-learned/lessons-learned.md", ".gitignore", ".claude/rules/cla-economy.md",
    }, files
    for directory in ("decisions", "feedback", "retro", "lessons-learned"):
        assert (root / "cla.io" / directory).is_dir()
    assert (root / "cla.io" / "retro" / "spec-to-pr-runs.jsonl").stat().st_size == 0
    assert (root / ".gitignore").read_text(encoding="utf-8").splitlines() == ["cla.io/retro/*-run-notes-*.md"]
    assert not (root / "cla.io" / "overlays").exists()
    assert not (root / "openspec").exists()


# requirement: repo-context / Setting up a repo's cla.io tree and economy rules file
@_needs_tools
def test_a_clone_local_or_machine_wide_ignore_of_the_notes_still_gets_the_gitignore_line(tmp_path: Path) -> None:
    """Only a committed `.gitignore` protects other clones, so a hidden-here pattern does not count."""
    block = _part_1_block("created: .gitignore run-notes line")
    pattern = "cla.io/retro/*-run-notes-*.md\n"
    for where in ("info-exclude", "excludes-file"):
        root = tmp_path / where
        root.mkdir()
        subprocess.run([_GIT, "init", "-q", str(root)], check=True, capture_output=True)
        if where == "info-exclude":
            (root / ".git" / "info").mkdir(exist_ok=True)
            (root / ".git" / "info" / "exclude").write_text(pattern, encoding="utf-8")
        else:
            excludes = tmp_path / "excludes-file.txt"
            excludes.write_text(pattern, encoding="utf-8")
            subprocess.run([_GIT, "-C", str(root), "config", "core.excludesFile", excludes.as_posix()],
                           check=True, capture_output=True)
        out = _bash(block, root)
        assert out.returncode == 0, out.stderr
        assert out.stdout.strip() == "created: .gitignore run-notes line", where
        assert (root / ".gitignore").read_bytes() == b"cla.io/retro/*-run-notes-*.md\n", where


# requirement: repo-context / Setting up a repo's cla.io tree and economy rules file
@_needs_tools
def test_an_existing_file_with_crlf_endings_that_equals_the_render_is_unchanged(tmp_path: Path) -> None:
    root, plugin, fresh = _rendered(tmp_path)
    crlf = fresh.replace(b"\n", b"\r\n")
    (root / _RULES).write_bytes(crlf)
    assert _run(root, plugin) == ".claude/rules/cla-economy.md: unchanged"
    assert (root / _RULES).read_bytes() == crlf, "an unchanged file must not be rewritten"


# requirement: repo-context / Setting up a repo's cla.io tree and economy rules file
@_needs_tools
def test_a_file_differing_only_in_trailing_blank_lines_is_replaced_not_unchanged(tmp_path: Path) -> None:
    root, plugin, fresh = _rendered(tmp_path)
    (root / _RULES).write_bytes(fresh + b"\n\n")
    out = _run(root, plugin)
    assert out.splitlines()[0] == ".claude/rules/cla-economy.md: replaced"
    assert (root / _RULES).read_bytes() == fresh


# requirement: repo-context / Setting up a repo's cla.io tree and economy rules file
@_needs_tools
def test_a_replaced_file_says_local_edits_were_overwritten(tmp_path: Path) -> None:
    root, plugin, fresh = _rendered(tmp_path)
    (root / _RULES).write_bytes(fresh + b"a hand edit\n")
    out = _run(root, plugin)
    assert out.splitlines()[0] == ".claude/rules/cla-economy.md: replaced"
    assert "local edits" in out and "overwritten" in out


def _without(name: str, text_edit):
    return lambda n, text: text_edit(text) if n == name else text


def _unlink(name: str):
    return lambda plugin: (plugin / "skills" / "_shared" / "references" / name).unlink()


def _empty(name: str):
    return lambda plugin: (plugin / "skills" / "_shared" / "references" / name).write_bytes(b"")


_BAD_SOURCES = {
    "end marker missing alone": (_without("model-routing.md", lambda t: t.replace(_END, "")), None),
    "begin marker missing alone": (_without("model-routing.md", lambda t: t.replace(_BEGIN, "")), None),
    "duplicate begin marker": (_without("model-routing.md", lambda t: t.replace(_BEGIN, _BEGIN + "\n" + _BEGIN)), None),
    "duplicate end marker": (_without("model-routing.md", lambda t: t.replace(_END, _END + "\n" + _END)), None),
    "end marker before begin marker": (_without("model-routing.md", lambda t: (
        t.replace(_BEGIN, "@@B@@").replace(_END, _BEGIN).replace("@@B@@", _END))), None),
    "marker with a trailing space": (_without("model-routing.md", lambda t: t.replace(_END, _END + " ")), None),
    "empty span between the markers": (_without("model-routing.md", lambda t: (
        t.split(_BEGIN)[0] + _BEGIN + "\n" + _END + t.split(_END)[1])), None),
    "cost-rules include marker deleted": (_without("economy-rules-file.md",
                                                   lambda t: t.replace("<!-- include: cost-rules -->\n", "")), None),
    "review-sizing include marker deleted": (_without("economy-rules-file.md",
                                                      lambda t: t.replace("<!-- include: review-sizing -->\n", "")), None),
    "include marker with a trailing space": (_without("economy-rules-file.md", lambda t: t.replace(
        "<!-- include: cost-rules -->", "<!-- include: cost-rules --> ")), None),
    "include marker twice": (_without("economy-rules-file.md", lambda t: t.replace(
        "<!-- include: cost-rules -->", "<!-- include: cost-rules -->\n\n<!-- include: cost-rules -->")), None),
    "stray comment in the frame": (_without("economy-rules-file.md", lambda t: t + "\n<!-- note -->\n"), None),
    "frame missing": (None, _unlink("economy-rules-file.md")),
    "frame empty": (None, _empty("economy-rules-file.md")),
    "cost rules missing": (None, _unlink("orchestration-economy.md")),
    "cost rules empty": (None, _empty("orchestration-economy.md")),
    "routing missing": (None, _unlink("model-routing.md")),
    "routing empty": (None, _empty("model-routing.md")),
}


# requirement: repo-context / Setting up a repo's cla.io tree and economy rules file
@_needs_tools
@pytest.mark.parametrize("case", sorted(_BAD_SOURCES))
def test_a_bad_source_writes_nothing_and_leaves_a_good_file_untouched(tmp_path: Path, case: str) -> None:
    edit, post = _BAD_SOURCES[case]
    bad = _plugin(tmp_path / "bad-plugin", edit=edit)
    if post is not None:
        post(bad)
    script = _block().replace("${CLAUDE_PLUGIN_ROOT}", bad.as_posix())
    fresh_root = tmp_path / "fresh-repo"
    fresh_root.mkdir()
    out = _bash(script, fresh_root)
    assert out.returncode != 0 and "NOT written" in out.stdout, (out.stdout, out.stderr)
    assert not (fresh_root / ".claude").exists(), "a failed run created the rules directory or file"
    root, _plugin_ok, good = _rendered(tmp_path)
    out = _bash(script, root)
    assert out.returncode != 0 and "NOT written" in out.stdout, (out.stdout, out.stderr)
    assert (root / _RULES).read_bytes() == good
    assert sorted(p.name for p in (root / ".claude" / "rules").iterdir()) == ["cla-economy.md"], "a temp file was left behind"


# requirement: repo-context / Setting up a repo's cla.io tree and economy rules file
@_needs_tools
def test_a_failed_write_says_not_written_and_keeps_the_existing_file(tmp_path: Path) -> None:
    """The text is rendered to a temp file first: a failure there never truncates a good file.
    A read-only directory is unreliable on Windows, so the failures are planted by shape:
    a directory where the temp file goes, and a plain file where `.claude` goes."""
    root, plugin, good = _rendered(tmp_path)
    (root / _RULES.parent / "cla-economy.md.tmp").mkdir()
    script = _block().replace("${CLAUDE_PLUGIN_ROOT}", plugin.as_posix())
    out = _bash(script, root)
    assert out.returncode != 0 and "NOT written" in out.stdout, (out.stdout, out.stderr)
    assert (root / _RULES).read_bytes() == good
    shutil.rmtree(root / _RULES.parent / "cla-economy.md.tmp", ignore_errors=True)
    # A stale temp entry the redirect cannot write through, while something is still there to be
    # moved: the block must stop at the failed write, not install it. On POSIX it is a symlink into
    # a missing directory, which fails for root too; read-only bits do not stop root, so a 0o444
    # file passed there only for non-root users. Windows keeps the read-only file, since a symlink
    # needs a privilege there.
    stale = root / _RULES.parent / "cla-economy.md.tmp"
    if os.name == "nt":
        stale.write_bytes(b"stale text\n")
        stale.chmod(0o444)
    else:
        stale.symlink_to(tmp_path / "missing-dir" / "target")
    try:
        out = _bash(script, root)
        assert out.returncode != 0 and "NOT written" in out.stdout, (out.stdout, out.stderr)
        assert (root / _RULES).read_bytes() == good
    finally:
        if stale.exists() and not stale.is_symlink():  # the block removes its own temp file on failure
            stale.chmod(0o644)
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    (blocked / ".claude").write_text("not a directory\n", encoding="utf-8")
    out = _bash(script, blocked)
    assert out.returncode != 0 and "NOT written" in out.stdout, (out.stdout, out.stderr)
    assert (blocked / ".claude").read_text(encoding="utf-8") == "not a directory\n"
