"""This repo's overlays must actually be reached by the code that reads them.

Every overlay reader in the plugin treats an absent overlay as the ordinary
un-configured state and falls back to a default. That is correct behaviour — a
fresh consuming repo has no overlays and must not be punished for it — but it
means a WRONG PATH is indistinguishable from a repo that simply hasn't
configured anything. The reader returns its default, the suite stays green, and
the overlay silently stops mattering.

Measured, not assumed: when the overlays moved from `skills/*/references/` into
`cla.io/overlays/`, two mutants — the staleness guard pointed at a non-existent
overlay dir, and the branch-prefix reader pointed at a non-existent path — both
SURVIVED the whole suite.

These checks live in `tests/consistency/`, which holds this repo's own
source-repo assertions, so the portable readers keep their lenient behaviour
while this repo gets the strict one. Each
asks the READER where it looks rather than recomputing the path here — the same
lesson as `test_token_list_is_curated_here.py`, where a check that computed its
own path passed while the guard it was vouching for was looking elsewhere.

`_import_from` loads BY PATH for the same reason. It used to insert a directory
on `sys.path` and call bare `__import__`, which resolves from `sys.modules`
first — so once pytest had collected a module of that name, or once a
`pythonpath` entry made one importable, the named directory stopped mattering
entirely. Measured: after the dev-tree extraction deleted
`.claude/plugins/cla/conformance-checks/`, `pytest plugin-tests/tests/consistency/`
was 1-failed on `ModuleNotFoundError` while the full `pytest plugin-tests` gate
stayed GREEN, because collecting `tests/conformance/` first put
`test_project_facts_paths` in `sys.modules` and the bare `__import__` picked it
up. A check that names a path and then does not use it is exactly the
looking-somewhere-else failure the rest of this file exists to catch. The two
`_git_common` calls below have the same exposure — this scope's `pythonpath`
carries `skills/spec-to-pr/scripts`, so they would resolve ambiently too — and
are fixed by the same change.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

_DEV_TREE = Path(__file__).resolve().parents[2]
_PLUGIN_ROOT = _DEV_TREE.parent / ".claude" / "plugins" / "cla"
_REPO_ROOT = _PLUGIN_ROOT.parents[2]
_OVERLAYS = _REPO_ROOT / "cla.io" / "overlays"


def _import_from(directory: Path, module: str):
    """Load `directory/module.py` by path, or fail loudly.

    Never falls back to an ambient import: a wrong or deleted directory raises
    here rather than silently handing back whichever same-named module the
    process already happens to hold.
    """
    path = directory / f"{module}.py"
    assert path.is_file(), (
        f"{path} does not exist, so this check has nothing to vouch for. Do not "
        "let it resolve by name — a bare import would return whatever module of "
        "that name the process already loaded and the check would pass while "
        "looking nowhere."
    )
    # A distinct key so this load never displaces (or is displaced by) pytest's
    # own collected module of the same name.
    spec = importlib.util.spec_from_file_location(f"_overlay_reach_{module}", path)
    assert spec is not None and spec.loader is not None, f"cannot load {path}"
    loaded = importlib.util.module_from_spec(spec)
    # Sibling imports inside the loaded module still need its directory on the
    # path; the load itself no longer does.
    sys.path.insert(0, str(directory))
    try:
        spec.loader.exec_module(loaded)
    finally:
        sys.path.pop(0)
    return loaded


_SKILLS = _PLUGIN_ROOT / "skills"
# A concrete overlay name as shipped prose or code spells it. `<skill>` and other
# placeholders do not match, because `<` is not in the class.
_NAMED_OVERLAY = re.compile(r"cla\.io/overlays/([a-z0-9][a-z0-9.-]*\.md)")


def _overlays_named_by_the_plugin() -> set[str]:
    names: set[str] = set()
    for path in _PLUGIN_ROOT.rglob("*"):
        if path.suffix in {".md", ".py", ".mjs"} and path.is_file():
            names |= set(_NAMED_OVERLAY.findall(path.read_text(encoding="utf-8")))
    return names


# requirement: repo-context / Optional per-skill overlays
def test_every_overlay_here_is_one_the_plugin_reads():
    """Overlays are optional, so this repo carries only the ones with content, and
    each must still be READ by something. An overlay whose skill stopped naming
    it is dead text that looks configured. The named set's floor keeps the check
    from passing over a scan that found nothing."""
    named = _overlays_named_by_the_plugin()
    assert "branch-prefix.local.md" in named and len(named) >= 3, named
    present = sorted(p.name for p in _OVERLAYS.glob("*.md"))
    assert "branch-prefix.local.md" in present, present
    orphans = [name for name in present if name not in named]
    assert not orphans, (
        f"{orphans} sit in {_OVERLAYS} but no shipped skill or script names them, "
        "so nothing reads them"
    )
    for name in present:
        text = (_OVERLAYS / name).read_text(encoding="utf-8")
        assert text.strip(), f"{name} is empty; delete it, since an absent overlay means the same"


# A clause that sends a reader to an overlay when a fact is missing elsewhere, in
# the three spellings the plugin used: "falls back to `cla.io/overlays/x.md`",
# "`cla.io/overlays/x.md` when that file is absent", and "(`cla.io/project-facts.md`
# or the overlay)". Matched over whitespace-joined text, since a clause wrapped
# across two lines is still one clause.
_FALLBACK = re.compile(
    r"fall(?:s|ing)? back to (?:the |this |its )?(?:project )?(?:overlay|`cla\.io/overlays)"
    r"|cla\.io/overlays/[a-z0-9.-]+\.md`? when that file is absent"
    r"|project-facts\.md`?,? or (?:from |in )?(?:the|its|this skill's) overlay\b",
    re.IGNORECASE,
)
_MANDATORY = re.compile(r"injection is mandatory", re.IGNORECASE)


# requirement: repo-context / Optional per-skill overlays
def test_no_shipped_text_makes_an_overlay_a_fallback_or_mandatory():
    """Facts have one home, `cla.io/project-facts.md`. A "fall back to the
    overlay" clause gives the same fact a second one, and "mandatory" injection
    from a file that is optional injects nothing in most repos."""
    files = sorted(p for p in _PLUGIN_ROOT.rglob("*.md") if p.is_file())
    assert len(files) > 50, "the scan found too few files to mean anything"
    hits = []
    for p in files:
        text = " ".join(p.read_text(encoding="utf-8").split())
        hits += [f"{p.relative_to(_PLUGIN_ROOT)}: {m.group(0)!r}"
                 for pattern in (_FALLBACK, _MANDATORY) for m in pattern.finditer(text)]
    assert not hits, f"overlay used as a fact fallback or called mandatory: {hits}"


# The one sentence every skill that reads a fact from the facts file carries for a
# repo set up before overlays went rules-only: the fact may still sit in the overlay.
_TRANSITIONAL = (
    'If `cla.io/project-facts.md` lacks a fact this skill needs and this skill\'s overlay exists, '
    'the overlay may still hold it from before the move: tell the user "run /cla:cla-setup to move it".'
)
# Skills that name the facts file without reading a fact from it in the session:
# cla-setup writes it, report-upstream and shape-decision only route or suggest,
# and multi-spec names it only in a brief for a dispatched agent.
_NO_TRANSITIONAL = {"cla-setup", "report-upstream", "shape-decision", "multi-spec", "_shared"}


# requirement: repo-context / Optional per-skill overlays
def test_every_skill_reading_the_facts_file_says_how_to_move_an_old_fact():
    """A skill reads a fact only from the facts file, so in a repo whose old overlay
    still holds it the fact is silently missing. The shared line turns that into an
    instruction the user can act on."""
    readers = sorted({p.relative_to(_SKILLS).parts[0] for p in _SKILLS.rglob("*.md")
                      if "cla.io/project-facts.md" in p.read_text(encoding="utf-8")})
    assert len(readers) >= 8, readers
    missing = []
    for skill in readers:
        if skill in _NO_TRANSITIONAL:
            continue
        text = " ".join(" ".join(p.read_text(encoding="utf-8").split())
                        for p in (_SKILLS / skill).rglob("*.md"))
        if _TRANSITIONAL not in text:
            missing.append(skill)
    assert not missing, f"{missing} read the facts file but never say how to move a fact from an old overlay"


def test_the_staleness_guard_scans_this_repos_overlays():
    guard = _import_from(
        _DEV_TREE / "tests" / "conformance", "test_project_facts_paths"
    )
    scanned = {p.resolve() for p in guard._iter_scanned_files(_REPO_ROOT)}
    missing = [
        p.name for p in sorted(_OVERLAYS.glob("*.md")) if p.resolve() not in scanned
    ]
    assert not missing, (
        f"the staleness guard does not scan {missing} — it is looking somewhere "
        f"other than {_OVERLAYS}, so those overlays are unchecked and the guard "
        "still reports success"
    )
    # Opening the files is not the same as extracting anything from them: a
    # regression in candidate extraction would leave `checked == 0`,
    # `stale == []`, and a green guard. Pin the floor here, where this repo's
    # facts file and overlays are known to name real paths.
    checked, _stale, _unreadable = guard.scan(_REPO_ROOT)
    assert checked > 0, (
        "the staleness guard extracted zero path candidates from this repo's "
        "overlays — it scanned files but checked nothing, which passes green"
    )


def test_the_branch_prefix_reader_resolves_this_repos_overlay():
    gc = _import_from(
        _PLUGIN_ROOT / "skills" / "spec-to-pr" / "scripts", "_git_common"
    )
    resolved = gc.overlay_path()
    assert resolved.is_file(), (
        f"branch_prefix() looks for its overlay at {resolved}, which does not "
        "exist — every repo silently gets the default prefix, and a resume probe "
        "then reports finished work as not started"
    )
    assert resolved.resolve() == (_OVERLAYS / "branch-prefix.local.md").resolve()


def test_the_branch_prefix_overlay_parses_rather_than_warning():
    """A file that EXISTS but yields no value degrades to the default with a
    warning on every run — the state this repo's stub was actually in before the
    overlay format was unified."""
    gc = _import_from(
        _PLUGIN_ROOT / "skills" / "spec-to-pr" / "scripts", "_git_common"
    )
    text = gc.overlay_path().read_text(encoding="utf-8")
    assert gc.prefix_from_text(text), (
        "the branch-prefix overlay does not parse to a usable value; the reader "
        "warns and falls back on every single run"
    )
