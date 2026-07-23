"""Conformance guard: no project-specific tokens in synced core.

A generic, repo-agnostic checker enforcing the cla plugin's fact/procedure
separation (``cla-overlay-convention`` + ``cla-skill-context-extraction``): a
project-specific token must live behind an overlay (``project-context.md`` /
``*.local.md``), never baked into a synced-core ``SKILL.md`` or
``references/**/*.md``, or ``update-cla``'s sync would carry it verbatim into
every destination repo. The token list itself is a per-repo overlay
(``project-tokens.local.md``) read as data — the checker hard-codes no token.

The checker obeys the same split it enforces: generic *procedure* (this file,
synced to every repo) + a repo-specific *fact* (the token list, never synced).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

OVERLAY_FILE_NAME = "project-context.md"
OVERLAY_LOCAL_SUFFIX = ".local.md"
EXCLUDED_SUBTREES = frozenset({"tests", "scripts"})
# Token-list overlay, relative to the skills/ root. Its ``.local.md`` leaf also
# makes it a recognized overlay, so the scan below never flags its own contents.
TOKEN_LIST_RELPATH = Path("update-cla") / "references" / "project-tokens.local.md"
MAX_EXCERPT = 120


def _plugin_root() -> Path:
    """Resolve the ``.claude/plugins/cla`` root from this file's own location — a
    fixed internal layout identical in every repo, with no repo-specific absolute
    path or repository name baked in."""
    for parent in Path(__file__).resolve().parents:
        if parent.name == "cla" and parent.parent.name == "plugins":
            return parent
    # Fallback for an unexpected layout: tests/ -> update-cla/ -> skills/ -> cla/
    return Path(__file__).resolve().parents[3]


def load_tokens(path: Path) -> list[str]:
    """Parse the markdown token-list overlay into a list of tokens.

    One token per ``- ``/``* `` bullet (the text after the marker, trimmed, with
    an optional trailing `` # comment`` and surrounding backticks stripped).
    ``#`` headings, blank lines, and ``<!-- ... -->`` comment lines are ignored.
    A missing file yields ``[]`` (trivial pass — see the main test)."""
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    # Strip HTML comment spans FIRST — they may span multiple lines and legitimately
    # contain `- `/`* ` bullets (e.g. this overlay's "excluded candidates" block),
    # which MUST NOT be parsed as tokens. Line-by-line skipping alone can't do this.
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    tokens: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- ") or line.startswith("* "):
            body = line[2:]
            # Strip an inline trailing "token  # why" comment. (A token containing a
            # literal '#' — a hex color, an anchor — is unsupported by this split, but
            # none is needed for the compound repo tokens this list holds.)
            if "#" in body:
                body = body.split("#", 1)[0]
            body = body.strip().strip("`").strip()
            if body:
                tokens.append(body)
    return tokens


def _is_overlay(path: Path) -> bool:
    leaf = path.name.lower()
    return leaf == OVERLAY_FILE_NAME or leaf.endswith(OVERLAY_LOCAL_SUFFIX)


def _iter_scanned_files(skills_root: Path):
    """Yield every ``SKILL.md`` + ``references/**/*.md`` under ``skills/**``,
    excluding overlay files and the ``tests/``/``scripts/`` subtrees."""
    if not skills_root.is_dir():
        return
    for path in sorted(skills_root.rglob("*.md")):
        if not path.is_file() or _is_overlay(path):
            continue
        ancestors = path.relative_to(skills_root).parts[:-1]
        if any(part in EXCLUDED_SUBTREES for part in ancestors):
            continue
        if path.name == "SKILL.md" or "references" in ancestors:
            yield path


def _body_lines(text: str, strip_frontmatter: bool):
    """Yield ``(1-based line number, line text)`` for a file's body, optionally
    skipping a leading YAML frontmatter block (``---`` ... ``---``) for MATCHING
    while keeping line numbers accurate. A skill's ``description:``/``argument-hint:``
    frontmatter legitimately names the host repo so the skill triggers — it is
    metadata, not portable procedure prose. ``strip_frontmatter`` is True ONLY for
    ``SKILL.md`` (the only file type that carries frontmatter); for a ``references``
    ``.md`` a leading ``---`` is a Markdown horizontal rule, never a frontmatter
    fence, so its body must not be silently exempted."""
    lines = text.splitlines()
    start = 0
    if strip_frontmatter and lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                start = i + 1
                break
    for idx in range(start, len(lines)):
        yield idx + 1, lines[idx]


def find_violations(skills_root: Path, report_root: Path, tokens: list[str]):
    """Return ``(rel_path, token, line_number, excerpt)`` for every case-insensitive
    literal-substring token hit in a scanned file's body. ``rel_path`` is reported
    relative to ``report_root`` (the plugin root in the real run)."""
    lowered = [(tok, tok.lower()) for tok in tokens]
    violations: list[tuple[str, str, int, str]] = []
    for path in _iter_scanned_files(skills_root):
        rel = path.relative_to(report_root).as_posix()
        strip_fm = path.name == "SKILL.md"
        for lineno, line in _body_lines(path.read_text(encoding="utf-8"), strip_fm):
            haystack = line.lower()
            for tok, tok_l in lowered:
                if tok_l in haystack:
                    excerpt = line.strip()
                    if len(excerpt) > MAX_EXCERPT:
                        excerpt = excerpt[: MAX_EXCERPT - 3] + "..."
                    violations.append((rel, tok, lineno, excerpt))
    return violations


# ---------- the guard ----------


def test_no_project_tokens_in_synced_core():
    """Fail if any non-overlay synced-core file leaks a listed project token."""
    plugin_root = _plugin_root()
    skills_root = plugin_root / "skills"
    token_path = skills_root / TOKEN_LIST_RELPATH
    if not token_path.is_file():
        # A fresh destination repo has synced the guard but not curated a token list
        # yet (the overlay is never seeded by sync) — trivial pass, not a red CI.
        pytest.skip(
            "no project-tokens.local.md overlay present — trivial pass; each "
            "destination repo curates its own token list"
        )
    tokens = load_tokens(token_path)
    if not tokens:
        # The file EXISTS but parses to zero tokens. That is a defect (a broken/
        # reformatted list), not a fresh repo — fail loudly rather than silently
        # disabling the guard. To intentionally disable it, DELETE the file.
        pytest.fail(
            f"{token_path.name} exists but yields no tokens — likely a formatting "
            "error (each token must be a `- token` / `* token` bullet). Delete the "
            "file to intentionally disable the guard."
        )
    scanned = list(_iter_scanned_files(skills_root))
    assert scanned, (
        f"guard scanned zero files under {skills_root} — the scan root or filters "
        "may be broken (a populated token list with nothing to scan is a silent no-op)"
    )
    violations = find_violations(skills_root, plugin_root, tokens)
    if violations:
        detail = "\n".join(
            f"{rel}:{lineno}  token {tok!r}  → {excerpt}"
            for rel, tok, lineno, excerpt in violations
        )
        pytest.fail(
            f"{len(violations)} project-token leak(s) in synced core "
            f"(move the fact behind an overlay, or curate the token out):\n{detail}"
        )


# ---------- self-tests of the checker's own machinery ----------


def test_load_tokens_parses_bullets_strips_comments_and_backticks(tmp_path):
    p = tmp_path / "project-tokens.local.md"
    p.write_text(
        "# Tokens\n\n"
        "- `agentic-air`  # repo name\n"
        "* packages/engine # a package path\n"
        "- 5173\n"
        "<!-- excluded: apps/ pnpm -->\n"
        "not-a-bullet-is-ignored\n",
        encoding="utf-8",
    )
    assert load_tokens(p) == ["agentic-air", "packages/engine", "5173"]


def test_absent_or_empty_token_list_yields_no_tokens(tmp_path):
    assert load_tokens(tmp_path / "missing.local.md") == []
    empty = tmp_path / "project-tokens.local.md"
    empty.write_text("# heading only\n<!-- a comment -->\n\n", encoding="utf-8")
    assert load_tokens(empty) == []


def test_body_token_is_flagged_with_accurate_line(tmp_path):
    skills = tmp_path / "skills"
    (skills / "demo").mkdir(parents=True)
    (skills / "demo" / "SKILL.md").write_text(
        "# Demo\n\nThis names funnel-demo in the body.\n", encoding="utf-8"
    )
    violations = find_violations(skills, tmp_path, ["funnel-demo"])
    assert violations == [("skills/demo/SKILL.md", "funnel-demo", 3,
                           "This names funnel-demo in the body.")]


def test_overlay_files_are_not_flagged(tmp_path):
    skills = tmp_path / "skills"
    refs = skills / "demo" / "references"
    refs.mkdir(parents=True)
    (refs / "project-context.md").write_text("funnel-demo everywhere\n", encoding="utf-8")
    (refs / "project-tokens.local.md").write_text("- funnel-demo\n", encoding="utf-8")
    assert find_violations(skills, tmp_path, ["funnel-demo"]) == []


def test_frontmatter_is_excluded_but_body_is_flagged(tmp_path):
    skills = tmp_path / "skills"
    (skills / "demo").mkdir(parents=True)
    # line 1 ---, 2 description (frontmatter, exempt), 3 ---, 4 blank,
    # 5 body, 6 body-with-token
    (skills / "demo" / "SKILL.md").write_text(
        "---\n"
        "description: all about the funnel-demo repo\n"
        "---\n"
        "\n"
        "Portable prose here.\n"
        "But funnel-demo in the body leaks.\n",
        encoding="utf-8",
    )
    violations = find_violations(skills, tmp_path, ["funnel-demo"])
    assert len(violations) == 1
    assert violations[0][2] == 6  # accurate line number despite skipped frontmatter


def test_references_md_scanned_but_stray_md_and_subtrees_ignored(tmp_path):
    skills = tmp_path / "skills"
    (skills / "demo" / "references").mkdir(parents=True)
    (skills / "demo" / "tests").mkdir(parents=True)
    (skills / "demo" / "scripts").mkdir(parents=True)
    (skills / "demo" / "references" / "note.md").write_text("has funnel-demo\n", encoding="utf-8")
    (skills / "demo" / "random.md").write_text("has funnel-demo\n", encoding="utf-8")  # not SKILL.md / references
    (skills / "demo" / "tests" / "note.md").write_text("has funnel-demo\n", encoding="utf-8")
    (skills / "demo" / "scripts" / "note.md").write_text("has funnel-demo\n", encoding="utf-8")
    violations = find_violations(skills, tmp_path, ["funnel-demo"])
    assert [v[0] for v in violations] == ["skills/demo/references/note.md"]


def test_matching_is_case_insensitive(tmp_path):
    skills = tmp_path / "skills"
    (skills / "demo").mkdir(parents=True)
    (skills / "demo" / "SKILL.md").write_text("# X\n\nThe Kantar gateway.\n", encoding="utf-8")
    violations = find_violations(skills, tmp_path, ["kantar"])
    assert len(violations) == 1


def test_load_tokens_ignores_bullets_inside_html_comment_blocks(tmp_path):
    # Multi-line <!-- ... --> blocks legitimately contain `- ` bullets (this repo's
    # own token overlay documents its excluded candidates that way) — none may leak in.
    p = tmp_path / "project-tokens.local.md"
    p.write_text(
        "<!--\n"
        "  header note with a bullet:\n"
        "  - funnel-demo  # INSIDE a comment, must be ignored\n"
        "-->\n"
        "- `agentic-air`  # the one real token\n"
        "<!-- excluded candidates:\n"
        "  - apps/  # also inside a comment\n"
        "  - pnpm\n"
        "-->\n",
        encoding="utf-8",
    )
    assert load_tokens(p) == ["agentic-air"]


def test_multiple_violations_all_collected_not_first_hit(tmp_path):
    # Guards the "surface every leak at once, not first-hit-only" promise: multiple
    # hits of one token across lines, plus two tokens on one line, must all report.
    skills = tmp_path / "skills"
    (skills / "demo").mkdir(parents=True)
    (skills / "demo" / "SKILL.md").write_text(
        "# Demo\n\nfunnel-demo here.\nfunnel-demo again.\nboth kantar and funnel-demo.\n",
        encoding="utf-8",
    )
    violations = find_violations(skills, tmp_path, ["funnel-demo", "kantar"])
    assert len(violations) == 4  # lines 3,4,5 (funnel-demo) + line 5 (kantar)
    assert sorted(v[2] for v in violations) == [3, 4, 5, 5]
    assert {v[1] for v in violations} == {"funnel-demo", "kantar"}


def test_frontmatter_skip_applies_only_to_skill_md(tmp_path):
    # A references .md opening with a Markdown horizontal rule (`---`) is NOT
    # frontmatter — its body must be scanned, not silently exempted.
    skills = tmp_path / "skills"
    refs = skills / "demo" / "references"
    refs.mkdir(parents=True)
    (refs / "note.md").write_text(
        "---\nfunnel-demo in a horizontal-rule block, not frontmatter.\n---\nbody.\n",
        encoding="utf-8",
    )
    violations = find_violations(skills, tmp_path, ["funnel-demo"])
    assert len(violations) == 1
    assert violations[0][2] == 2  # scanned, because non-SKILL.md files aren't frontmatter-stripped
