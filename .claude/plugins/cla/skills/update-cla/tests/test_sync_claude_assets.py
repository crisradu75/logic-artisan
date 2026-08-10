"""Tests for update-cla (pull-from-destination shape)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


def _load(module_name: str):
    base = Path(__file__).resolve().parent.parent / "scripts"
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, base / f"{module_name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _seed_lock(repo: Path, entries: dict) -> None:
    """Write a `.cla-sync-lock.json` directly into `repo` for a test's setup."""
    lock_path = repo / ".claude" / "plugins" / "cla" / ".cla-sync-lock.json"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(entries), encoding="utf-8")


# ---------- config ----------


def test_first_run_creates_dict_shape_config(tmp_path, monkeypatch, synthetic_repos):
    repos = synthetic_repos({
        "repo-a": {".claude/plugins/cla/skills/foo.md": "A"},
        "repo-b": {".claude/plugins/cla/skills/foo.md": "B"},
    })
    root = repos[0].parent
    config_path = tmp_path / "sync-config.json"
    monkeypatch.setenv("CLAUDE_SYNC_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("CLAUDE_SYNC_ROOT", str(root))

    cfg_mod = _load("config")
    cfg = cfg_mod.resolve()

    assert config_path.exists()
    written = json.loads(config_path.read_text(encoding="utf-8"))
    assert isinstance(written["repos"], dict)
    assert set(written["repos"]) == {"repo-a", "repo-b"}
    assert cfg.first_run is True
    assert cfg.corrupted is False
    assert set(cfg.repos) == {"repo-a", "repo-b"}


def test_legacy_list_shape_config_accepted(tmp_path, monkeypatch, synthetic_repos):
    repos = synthetic_repos({
        "repo-a": {".claude/plugins/cla/skills/foo.md": "A"},
        "repo-b": {".claude/plugins/cla/skills/foo.md": "B"},
    })
    root = repos[0].parent
    config_path = tmp_path / "sync-config.json"
    config_path.write_text(
        json.dumps({"repos": [str(repos[0]), str(repos[1])]}), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_SYNC_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("CLAUDE_SYNC_ROOT", str(root))

    cfg_mod = _load("config")
    cfg = cfg_mod.resolve()

    assert set(cfg.repos) == {"repo-a", "repo-b"}
    assert cfg.first_run is False


def test_corrupted_config_sets_flag_and_warns(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "sync-config.json"
    config_path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_SYNC_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("CLAUDE_SYNC_ROOT", str(tmp_path / "nonexistent"))

    cfg_mod = _load("config")
    cfg = cfg_mod.resolve()

    assert cfg.corrupted is True
    assert cfg.repos == {}
    assert "is corrupted" in capsys.readouterr().err


def test_resolve_repo_arg_short_name(tmp_path, monkeypatch, synthetic_repos):
    repos = synthetic_repos({"repo-a": {".claude/plugins/cla/skills/foo.md": "A"}})
    root = repos[0].parent
    config_path = tmp_path / "sync-config.json"
    config_path.write_text(
        json.dumps({"repos": {"repo-a": str(repos[0])}}), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_SYNC_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("CLAUDE_SYNC_ROOT", str(root))

    cfg_mod = _load("config")
    cfg = cfg_mod.resolve()

    resolved = cfg_mod.resolve_repo_arg("repo-a", cfg)
    assert resolved == repos[0].resolve()


def test_resolve_repo_arg_absolute_path(tmp_path, monkeypatch, synthetic_repos):
    repos = synthetic_repos({"repo-a": {".claude/plugins/cla/skills/foo.md": "A"}})
    root = repos[0].parent
    config_path = tmp_path / "sync-config.json"
    monkeypatch.setenv("CLAUDE_SYNC_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("CLAUDE_SYNC_ROOT", str(root))

    cfg_mod = _load("config")
    cfg = cfg_mod.resolve()

    resolved = cfg_mod.resolve_repo_arg(str(repos[0]), cfg)
    assert resolved == repos[0].resolve()


def test_resolve_repo_arg_raises_when_corrupted_and_short_name(tmp_path, monkeypatch):
    config_path = tmp_path / "sync-config.json"
    config_path.write_text("garbage", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_SYNC_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("CLAUDE_SYNC_ROOT", str(tmp_path / "nonexistent"))

    cfg_mod = _load("config")
    cfg = cfg_mod.resolve()

    with pytest.raises(cfg_mod.ConfigError):
        cfg_mod.resolve_repo_arg("some-short-name", cfg)


# ---------- discover ----------


def test_identical_files_skipped(synthetic_repos):
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/foo.md": "same\n"},
        "dst": {".claude/plugins/cla/skills/foo.md": "same\n"},
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    assert result.files == []
    assert result.skipped == []


def test_divergent_file_detected(synthetic_repos):
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/foo.md": "A\n"},
        "dst": {".claude/plugins/cla/skills/foo.md": "B\n"},
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    assert len(result.files) == 1
    r = result.files[0]
    assert r.asset_path == ".claude/plugins/cla/skills/foo.md"
    assert r.status == "divergent"
    assert r.source_content == "A\n"
    assert r.local_content == "B\n"


def test_new_file_in_source_only(synthetic_repos):
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/new.md": "fresh\n"},
        "dst": {".claude/plugins/cla/skills/other.md": "exists\n"},
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    new_files = [r for r in result.files if r.status == "new"]
    assert len(new_files) == 1
    assert new_files[0].asset_path == ".claude/plugins/cla/skills/new.md"
    assert new_files[0].local_content is None


def test_local_only_files_ignored(synthetic_repos):
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/a.md": "A\n"},
        "dst": {".claude/plugins/cla/skills/a.md": "A\n", ".claude/plugins/cla/skills/local-only.md": "L\n"},
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    assert result.files == []


def test_settings_json_excluded(synthetic_repos):
    repos = synthetic_repos({
        "src": {".claude/settings.json": '{"a": 1}'},
        "dst": {".claude/settings.json": '{"b": 2}'},
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    assert result.files == []


def test_pycache_and_hidden_files_excluded(synthetic_repos):
    repos = synthetic_repos({
        "src": {
            ".claude/plugins/cla/skills/keep.md": "K\n",
            ".claude/plugins/cla/skills/foo/__pycache__/x.pyc": "junk",
            ".claude/plugins/cla/skills/foo/.DS_Store": "noise",
            ".claude/plugins/cla/skills/foo/.gitkeep": "",
        },
        "dst": {
            ".claude/plugins/cla/skills/keep.md": "old\n",
        },
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    paths = sorted(r.asset_path for r in result.files)
    # Only the keep.md is reported. .gitkeep would be in source-only and "new",
    # but only when present in source — it's there, so it shows as "new".
    assert ".claude/plugins/cla/skills/foo/__pycache__/x.pyc" not in paths
    assert ".claude/plugins/cla/skills/foo/.DS_Store" not in paths
    assert ".claude/plugins/cla/skills/keep.md" in paths


def test_binary_file_skipped_with_stderr_warning(synthetic_repos, tmp_path, capsys):
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/a.md": "A\n"},
        "dst": {".claude/plugins/cla/skills/a.md": "A\n"},
    })
    # Inject a binary file directly into source.
    binary_path = repos[0] / ".claude" / "plugins" / "cla" / "skills" / "foo" / "icon.png"
    binary_path.parent.mkdir(parents=True, exist_ok=True)
    binary_path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR\xff\xfe\xfd")

    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    assert len(result.skipped) == 1
    s = result.skipped[0]
    assert s.asset_path == ".claude/plugins/cla/skills/foo/icon.png"
    assert s.reason == "binary"
    err = capsys.readouterr().err
    assert "binary asset" in err


def test_filter_exact_file(synthetic_repos):
    repos = synthetic_repos({
        "src": {
            ".claude/plugins/cla/skills/a.md": "A\n",
            ".claude/plugins/cla/skills/b.md": "B\n",
        },
        "dst": {
            ".claude/plugins/cla/skills/a.md": "old-A\n",
            ".claude/plugins/cla/skills/b.md": "old-B\n",
        },
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1], filter_pattern=".claude/plugins/cla/skills/a.md")
    assert [r.asset_path for r in result.files] == [".claude/plugins/cla/skills/a.md"]


def test_filter_directory_prefix(synthetic_repos):
    repos = synthetic_repos({
        "src": {
            ".claude/plugins/cla/skills/foo/SKILL.md": "foo source\n",
            ".claude/plugins/cla/skills/foo/references/x.md": "ref source\n",
            ".claude/plugins/cla/skills/bar/SKILL.md": "bar source\n",
        },
        "dst": {
            ".claude/plugins/cla/skills/foo/SKILL.md": "foo local\n",
            ".claude/plugins/cla/skills/foo/references/x.md": "ref local\n",
            ".claude/plugins/cla/skills/bar/SKILL.md": "bar local\n",
        },
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1], filter_pattern=".claude/plugins/cla/skills/foo/")
    paths = sorted(r.asset_path for r in result.files)
    assert paths == [
        ".claude/plugins/cla/skills/foo/SKILL.md",
        ".claude/plugins/cla/skills/foo/references/x.md",
    ]


def test_filter_glob(synthetic_repos):
    repos = synthetic_repos({
        "src": {
            ".claude/plugins/cla/skills/a.md": "A\n",
            ".claude/plugins/cla/skills/b.md": "B\n",
            ".claude/plugins/cla/hooks/foo/SKILL.md": "S\n",
        },
        "dst": {
            ".claude/plugins/cla/skills/a.md": "x\n",
            ".claude/plugins/cla/skills/b.md": "x\n",
            ".claude/plugins/cla/hooks/foo/SKILL.md": "x\n",
        },
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1], filter_pattern=".claude/plugins/cla/skills/*.md")
    assert sorted(r.asset_path for r in result.files) == [
        ".claude/plugins/cla/skills/a.md",
        ".claude/plugins/cla/skills/b.md",
    ]


def test_filter_windows_backslashes_normalized(synthetic_repos):
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/foo.md": "A\n"},
        "dst": {".claude/plugins/cla/skills/foo.md": "B\n"},
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(
        repos[0], repos[1], filter_pattern=r".claude\plugins\cla\skills\foo.md"
    )
    assert [r.asset_path for r in result.files] == [".claude/plugins/cla/skills/foo.md"]


def test_summary_counts(synthetic_repos):
    repos = synthetic_repos({
        "src": {
            ".claude/plugins/cla/skills/a.md": "A\n",
            ".claude/plugins/cla/skills/foo/SKILL.md": "S\n",
        },
        "dst": {
            ".claude/plugins/cla/skills/a.md": "old\n",
        },
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    counts = discover_mod.summary_counts(result)
    assert counts["divergent"] == 1
    assert counts["new"] == 1
    assert counts["skills"] == 2
    assert counts["hooks"] == 0
    assert counts["output_styles"] == 0
    assert counts["total"] == 2
    assert counts["skipped"] == 0


def test_overlay_marker_preserved(synthetic_repos):
    """A leaf name that is exactly `project-context.md` (case-insensitively), or
    that ends with `.local.md`, is the repo's local overlay and is NEVER synced
    from the source (cla-overlay-convention); every other core file — INCLUDING
    a non-overlay sibling in the SAME `references/` dir — still syncs.

    The overlay/core files all carry DIFFERENT src-vs-dst content on purpose:
    a broken predicate would surface them as `divergent` in `result.files`, so
    the negative assertions genuinely prove exclusion (not accidental identity-
    skip), and the positive assertions prove non-overlay files are NOT dropped."""
    repos = synthetic_repos({
        "src": {
            "cla.io/overlays/review-change.md": "SOURCE overlay\n",
            ".claude/plugins/cla/skills/review-change/references/notes.local.md": "SOURCE local overlay\n",
            # non-overlay sibling in the SAME references/ dir — must still sync
            # (guards against a regression to directory-level exclusion).
            ".claude/plugins/cla/skills/review-change/references/checklist.md": "SOURCE sibling\n",
            # near-miss of the exact name — must sync (guards `==`, not startswith/in).
            ".claude/plugins/cla/skills/review-change/references/project-context-notes.md": "SOURCE near-miss\n",
            # mixed-case overlay in a different dir — must be excluded (case-insensitive match).
            ".claude/plugins/cla/skills/project-review/references/PROJECT-CONTEXT.md": "SOURCE cased overlay\n",
            ".claude/plugins/cla/skills/spec-to-pr/SKILL.md": "SOURCE core\n",
        },
        "dst": {
            "cla.io/overlays/review-change.md": "LOCAL overlay\n",
            ".claude/plugins/cla/skills/review-change/references/notes.local.md": "LOCAL local overlay\n",
            ".claude/plugins/cla/skills/review-change/references/checklist.md": "LOCAL sibling\n",
            ".claude/plugins/cla/skills/review-change/references/project-context-notes.md": "LOCAL near-miss\n",
            ".claude/plugins/cla/skills/project-review/references/PROJECT-CONTEXT.md": "LOCAL cased overlay\n",
            ".claude/plugins/cla/skills/spec-to-pr/SKILL.md": "LOCAL core\n",
        },
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    paths = [r.asset_path for r in result.files]
    # core + non-overlay files ARE synced
    assert ".claude/plugins/cla/skills/spec-to-pr/SKILL.md" in paths
    assert any(p.endswith("review-change/references/checklist.md") for p in paths)          # sibling still syncs
    assert any(p.endswith("review-change/references/project-context-notes.md") for p in paths)  # near-miss syncs
    # overlay files are NEVER synced
    assert not any(p.endswith("/project-context.md") for p in paths)   # exact-name overlay preserved
    assert not any(p.endswith(".local.md") for p in paths)             # *.local.md overlay preserved
    assert not any("PROJECT-CONTEXT.md" in p for p in paths)           # mixed-case overlay preserved (case-insensitive)


def test_hooks_dir_scanned(synthetic_repos):
    """`.claude/plugins/cla/hooks/` is in SCAN_DIRS: hook files (and their tests) are
    discovered and counted under the `hooks` bucket."""
    repos = synthetic_repos({
        "src": {
            ".claude/plugins/cla/hooks/guard.py": "source\n",
            ".claude/plugins/cla/hooks/tests/test_guard.py": "source test\n",
        },
        "dst": {
            ".claude/plugins/cla/hooks/guard.py": "local\n",
        },
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    paths = sorted(r.asset_path for r in result.files)
    assert paths == [
        ".claude/plugins/cla/hooks/guard.py",
        ".claude/plugins/cla/hooks/tests/test_guard.py",
    ]
    counts = discover_mod.summary_counts(result)
    assert counts["hooks"] == 2
    assert counts["divergent"] == 1  # guard.py
    assert counts["new"] == 1        # tests/test_guard.py


def test_output_styles_dir_scanned(synthetic_repos):
    """`.claude/plugins/cla/output-styles/` is in SCAN_DIRS: a plugin-shipped output
    style syncs the same way a skill or hook does — this is how the writing
    convention itself propagates to a repo that pulls from this one."""
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/output-styles/CLA.md": "source style\n"},
        "dst": {".claude/plugins/cla/output-styles/CLA.md": "local style\n"},
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    assert [r.asset_path for r in result.files] == [
        ".claude/plugins/cla/output-styles/CLA.md",
    ]
    counts = discover_mod.summary_counts(result)
    assert counts["output_styles"] == 1
    assert counts["divergent"] == 1


# ---------- discover: 3-way classification (lockfile ancestor) ----------


def test_an_adapted_file_with_neither_side_moved_is_labelled_adapted(synthetic_repos, fake_gh):
    """The headline round-trip, and the reason `source_sha256` exists.

    Right after an `apply` that wrote ADAPTED content differing from raw source,
    with source unchanged since, NOTHING has actually moved — the only reason
    local and source differ is the adaptation itself. That must read `adapted`.

    It used to read `source-advanced`, which `references/phases.md` defines as
    "local is untouched since the last sync; adopt source freely" — so the next
    Phase 2 was told to overwrite a deliberate divergence, and did.
    """
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/foo.md": "SOURCE raw content\n"},
        "dst": {},
    })
    apply_mod = _load("apply")
    discover_mod = _load("discover")
    asset = ".claude/plugins/cla/skills/foo.md"
    raw_sha = discover_mod._hash_bytes(b"SOURCE raw content\n")
    adaptations = [{
        "asset_path": asset,
        "adapted_content": "LOCAL adapted content\n",
        "change_summary": "adapted",
    }]
    outcomes = apply_mod.apply_worktree(
        repos[1], adaptations, "src", source_shas={asset: raw_sha}
    )
    assert outcomes[0].status == "wrote"

    result = discover_mod.discover(repos[0], repos[1])
    assert len(result.files) == 1
    assert result.files[0].status == "adapted"


def test_a_freshly_synced_file_without_a_source_sha_keeps_the_legacy_label(
    synthetic_repos, fake_gh
):
    """The same scenario through a lockfile written BEFORE `source_sha256`.

    Kept as its own case rather than folded into the test above, because it is
    the one that must NOT change: an existing consuming repo's lockfile has no
    `source_sha256`, and it has to keep reading exactly as it did. Note this
    test would have passed unchanged against the old code — which is precisely
    why the `adapted` assertion above had to be written separately instead of
    edited into it.
    """
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/foo.md": "SOURCE raw content\n"},
        "dst": {},
    })
    apply_mod = _load("apply")
    adaptations = [{
        "asset_path": ".claude/plugins/cla/skills/foo.md",
        "adapted_content": "LOCAL adapted content\n",
        "change_summary": "adapted",
    }]
    # No `source_shas` — the pre-change call shape.
    outcomes = apply_mod.apply_worktree(repos[1], adaptations, "src")
    assert outcomes[0].status == "wrote"

    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    assert len(result.files) == 1
    assert result.files[0].status == "source-advanced"


def test_local_advanced_is_reachable_for_an_adapted_file(synthetic_repos):
    """The reported bug, stated directly.

    An adapted file that local then edited FURTHER, with source unmoved, is
    `local-advanced`. Before `source_sha256` this was unreachable: the label
    required `source_sha == ancestor`, and the ancestor was the adapted bytes,
    so only a verbatim adoption could ever satisfy it.
    """
    discover_mod = _load("discover")
    raw_source = "SOURCE raw\n"
    adapted = "ADAPTED at sync time\n"
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/foo.md": raw_source},
        "dst": {".claude/plugins/cla/skills/foo.md": "ADAPTED then edited again\n"},
    })
    _seed_lock(repos[1], {
        ".claude/plugins/cla/skills/foo.md": {
            "last_synced_sha256": discover_mod._hash_bytes(adapted.encode()),
            "source_sha256": discover_mod._hash_bytes(raw_source.encode()),
            "source": "src",
        },
    })
    result = discover_mod.discover(repos[0], repos[1])
    assert result.files[0].status == "local-advanced"


def test_source_advanced_requires_the_source_to_have_actually_moved(synthetic_repos):
    """The complement: with `source_sha256` recorded, `source-advanced` now means
    what it says — source really did move since the sync — rather than "the
    adaptation changed something", which was true of every adapted file."""
    discover_mod = _load("discover")
    adapted = "ADAPTED at sync time\n"
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/foo.md": "SOURCE moved on\n"},
        "dst": {".claude/plugins/cla/skills/foo.md": adapted},
    })
    _seed_lock(repos[1], {
        ".claude/plugins/cla/skills/foo.md": {
            "last_synced_sha256": discover_mod._hash_bytes(adapted.encode()),
            "source_sha256": discover_mod._hash_bytes(b"SOURCE raw at sync\n"),
            "source": "src",
        },
    })
    result = discover_mod.discover(repos[0], repos[1])
    assert result.files[0].status == "source-advanced"


@pytest.mark.parametrize("bad", [None, "", 42, [], {}])
def test_a_missing_or_non_string_source_sha_degrades_to_the_legacy_path(synthetic_repos, bad):
    """Backward compatibility is by DEFAULTING (S0 := ancestor), not branching.

    Mapping a missing field to `both-diverged` instead would mislabel every
    legacy entry in every consuming repo at once, on the first run after upgrade.
    A junk value must degrade the same way a missing one does.
    """
    discover_mod = _load("discover")
    ancestor = "shared content\n"
    entry = {
        "last_synced_sha256": discover_mod._hash_bytes(ancestor.encode()),
        "source": "src",
    }
    if bad is not None:
        entry["source_sha256"] = bad
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/foo.md": ancestor},
        "dst": {".claude/plugins/cla/skills/foo.md": "LOCAL edited\n"},
    })
    _seed_lock(repos[1], {".claude/plugins/cla/skills/foo.md": entry})
    result = discover_mod.discover(repos[0], repos[1])
    # Legacy semantics: source == ancestor, local moved -> local-advanced.
    assert result.files[0].status == "local-advanced"


def test_a_legacy_lock_entry_can_never_produce_the_adapted_label(synthetic_repos):
    """Non-vacuity partner for the degradation rule.

    With S0 := ancestor, `adapted` requires local == ancestor AND source ==
    ancestor, hence local == source — which is dropped as identical before
    classification is ever consulted. So the new label is structurally
    impossible for an old lockfile, rather than merely unlikely.
    """
    discover_mod = _load("discover")
    ancestor_sha = discover_mod._hash_bytes(b"shared\n")
    for local, source in [("shared\n", "moved\n"), ("moved\n", "shared\n"), ("a\n", "b\n")]:
        entry = {"last_synced_sha256": ancestor_sha, "source": "src"}
        assert discover_mod._classify_status(
            discover_mod._hash_bytes(local.encode()),
            discover_mod._hash_bytes(source.encode()),
            entry,
        ) != "adapted"


def test_discover_source_advanced_when_local_matches_ancestor(synthetic_repos):
    ancestor_content = "shared content\n"
    ancestor_sha = hashlib.sha256(ancestor_content.encode("utf-8")).hexdigest()
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/foo.md": "SOURCE moved on\n"},
        "dst": {".claude/plugins/cla/skills/foo.md": ancestor_content},
    })
    _seed_lock(repos[1], {
        ".claude/plugins/cla/skills/foo.md": {"last_synced_sha256": ancestor_sha, "source": "src"},
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    assert len(result.files) == 1
    assert result.files[0].status == "source-advanced"


def test_discover_local_advanced_when_source_matches_ancestor(synthetic_repos):
    ancestor_content = "shared content\n"
    ancestor_sha = hashlib.sha256(ancestor_content.encode("utf-8")).hexdigest()
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/foo.md": ancestor_content},
        "dst": {".claude/plugins/cla/skills/foo.md": "LOCAL edited\n"},
    })
    _seed_lock(repos[1], {
        ".claude/plugins/cla/skills/foo.md": {"last_synced_sha256": ancestor_sha, "source": "src"},
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    assert len(result.files) == 1
    assert result.files[0].status == "local-advanced"


def test_discover_both_diverged_when_both_differ_from_ancestor(synthetic_repos):
    ancestor_sha = hashlib.sha256(b"original\n").hexdigest()
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/foo.md": "SOURCE changed\n"},
        "dst": {".claude/plugins/cla/skills/foo.md": "LOCAL changed\n"},
    })
    _seed_lock(repos[1], {
        ".claude/plugins/cla/skills/foo.md": {"last_synced_sha256": ancestor_sha, "source": "src"},
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    assert len(result.files) == 1
    assert result.files[0].status == "both-diverged"


def test_discover_divergent_fallback_when_no_lock_entry(synthetic_repos):
    """No lock entry at all for this asset -> today's 2-way `divergent`."""
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/foo.md": "A\n"},
        "dst": {".claude/plugins/cla/skills/foo.md": "B\n"},
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    assert len(result.files) == 1
    assert result.files[0].status == "divergent"


def test_discover_missing_lockfile_does_not_crash(synthetic_repos):
    """No `.cla-sync-lock.json` at all in local repo -> empty ancestor map, no crash,
    same as the no-lock-entry case."""
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/foo.md": "A\n"},
        "dst": {".claude/plugins/cla/skills/foo.md": "B\n"},
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    assert result.files[0].status == "divergent"


# ---------- discover: malformed/corrupt lockfile resilience ----------


def test_discover_corrupt_json_lockfile_does_not_crash(synthetic_repos):
    """Corrupt JSON (fails to parse entirely) -> empty ancestor map, no crash, and
    the affected asset classifies via the 2-way `divergent` fallback."""
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/foo.md": "A\n"},
        "dst": {".claude/plugins/cla/skills/foo.md": "B\n"},
    })
    lock_path = repos[1] / ".claude" / "plugins" / "cla" / ".cla-sync-lock.json"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("not json{", encoding="utf-8")
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    assert len(result.files) == 1
    assert result.files[0].status == "divergent"


def test_discover_non_dict_top_level_lockfile_does_not_crash(synthetic_repos):
    """A lockfile whose top-level JSON value is a list, not a dict -> empty ancestor
    map, no crash, `divergent` fallback."""
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/foo.md": "A\n"},
        "dst": {".claude/plugins/cla/skills/foo.md": "B\n"},
    })
    lock_path = repos[1] / ".claude" / "plugins" / "cla" / ".cla-sync-lock.json"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("[]", encoding="utf-8")
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    assert len(result.files) == 1
    assert result.files[0].status == "divergent"


def test_discover_nested_non_dict_lock_entry_does_not_crash(synthetic_repos):
    """A lockfile whose top level IS a dict, but whose per-asset VALUE is a plain
    string (not a dict) — `{"some/path": "corrupt"}` — must not crash `discover`.
    Before the fix, `_classify_status`/`_detect_deletions` called `.get(...)` on this
    value directly and raised `AttributeError`, crashing the whole run. The fix
    sanitizes `_read_lock` to drop any entry whose value isn't a dict, so the asset
    behaves as "no ancestor" and falls back to `divergent` — this is the one test
    that would have caught that regression."""
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/foo.md": "A\n"},
        "dst": {".claude/plugins/cla/skills/foo.md": "B\n"},
    })
    _seed_lock(repos[1], {".claude/plugins/cla/skills/foo.md": "corrupt"})
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    assert len(result.files) == 1
    assert result.files[0].status == "divergent"


# ---------- discover: source-side deletion detection ----------


def test_deletion_detected_for_lock_tracked_asset_absent_from_source(synthetic_repos):
    ancestor_sha = hashlib.sha256(b"old content\n").hexdigest()
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/keep.md": "K\n"},
        "dst": {
            ".claude/plugins/cla/skills/keep.md": "K\n",
            ".claude/plugins/cla/skills/removed.md": "old content\n",
        },
    })
    _seed_lock(repos[1], {
        ".claude/plugins/cla/skills/removed.md": {"last_synced_sha256": ancestor_sha, "source": "src"},
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    assert result.files == []  # keep.md is identical, dropped
    assert len(result.deletions) == 1
    d = result.deletions[0]
    assert d.asset_path == ".claude/plugins/cla/skills/removed.md"
    assert d.status == "deleted-in-source"
    assert d.local_sha256 == ancestor_sha
    assert d.last_synced_sha256 == ancestor_sha
    assert d.source == "src"


def test_local_only_asset_with_no_lock_entry_not_flagged(synthetic_repos):
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/keep.md": "K\n"},
        "dst": {
            ".claude/plugins/cla/skills/keep.md": "K\n",
            ".claude/plugins/cla/skills/local-only.md": "L\n",
        },
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    assert result.deletions == []


def test_overlay_never_flagged_as_deletion_even_with_lock_entry(synthetic_repos):
    """An overlay file (leaf `project-context.md` or `*.local.md`) is excluded from
    the local-tree deletion walk by `_is_excluded` regardless of a (bogus,
    hand-edited) lock entry — belt and suspenders per Decision D. Overlay files are
    never lock-tracked in real operation (apply never writes one, since discover
    never surfaces one to adapt), but this guards the case anyway."""
    fake_sha = hashlib.sha256(b"whatever\n").hexdigest()
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/keep.md": "K\n"},
        "dst": {
            ".claude/plugins/cla/skills/keep.md": "K\n",
            ".claude/plugins/cla/skills/foo/references/project-context.md": "overlay\n",
            ".claude/plugins/cla/skills/foo/references/notes.local.md": "local overlay\n",
        },
    })
    _seed_lock(repos[1], {
        ".claude/plugins/cla/skills/foo/references/project-context.md":
            {"last_synced_sha256": fake_sha, "source": "src"},
        ".claude/plugins/cla/skills/foo/references/notes.local.md":
            {"last_synced_sha256": fake_sha, "source": "src"},
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    assert result.deletions == []


def test_scoped_run_deletion_walk_respects_filter(synthetic_repos):
    """A lock-tracked asset OUTSIDE the run's `filter_pattern` scope is not surfaced
    as `deleted-in-source` — the local deletion walk applies the same
    `_matches_filter` the source walk uses (Decision D), so a scoped run doesn't
    false-positive the entire rest of the roster as deleted."""
    ancestor_sha = hashlib.sha256(b"out-of-scope old\n").hexdigest()
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/foo/SKILL.md": "S\n"},
        "dst": {
            ".claude/plugins/cla/skills/foo/SKILL.md": "S\n",
            ".claude/plugins/cla/skills/bar/removed.md": "out-of-scope old\n",
        },
    })
    _seed_lock(repos[1], {
        ".claude/plugins/cla/skills/bar/removed.md": {"last_synced_sha256": ancestor_sha, "source": "src"},
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1], filter_pattern=".claude/plugins/cla/skills/foo/")
    assert result.deletions == []


def test_deletion_renamed_asset_surfaces_as_deletion_plus_new(synthetic_repos):
    """A rename in source (old path gone, new path added) naturally surfaces as a
    `deleted-in-source` record for the old path PLUS a `new` FileRecord for the new
    path — no special rename-detection code, this falls out of 4.1-4.2 plus the
    existing `new` detection."""
    ancestor_sha = hashlib.sha256(b"content\n").hexdigest()
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/renamed-new.md": "content\n"},
        "dst": {".claude/plugins/cla/skills/old-name.md": "content\n"},
    })
    _seed_lock(repos[1], {
        ".claude/plugins/cla/skills/old-name.md": {"last_synced_sha256": ancestor_sha, "source": "src"},
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    assert [d.asset_path for d in result.deletions] == [".claude/plugins/cla/skills/old-name.md"]
    new_files = [r for r in result.files if r.status == "new"]
    assert [r.asset_path for r in new_files] == [".claude/plugins/cla/skills/renamed-new.md"]


def test_lockfile_never_appears_in_divergences(synthetic_repos):
    """The lockfile itself, even with differing content between repos, is never a
    sync candidate — it lives outside SCAN_DIRS (and would also be dotfile-excluded
    if it did)."""
    repos = synthetic_repos({
        "src": {
            ".claude/plugins/cla/skills/foo.md": "same\n",
            ".claude/plugins/cla/.cla-sync-lock.json": '{"src-only": "entry"}',
        },
        "dst": {
            ".claude/plugins/cla/skills/foo.md": "same\n",
            ".claude/plugins/cla/.cla-sync-lock.json": '{"dst-only": "entry"}',
        },
    })
    discover_mod = _load("discover")
    result = discover_mod.discover(repos[0], repos[1])
    assert result.files == []
    assert result.deletions == []


# ---------- apply: normalization + malformed-content guard (unit) ----------


def test_normalize_line_endings_converts_crlf_and_bare_cr():
    apply_mod = _load("apply")
    assert apply_mod._normalize_line_endings("a\r\nb\rc\n") == "a\nb\nc\n"


def test_normalize_line_endings_is_a_no_op_on_already_lf_content():
    apply_mod = _load("apply")
    content = "a\nb\nc\n"
    assert apply_mod._normalize_line_endings(content) == content


def test_looks_malformed_flags_the_doubled_newline_fingerprint():
    apply_mod = _load("apply")
    real_lines = [f"line {i}" for i in range(apply_mod._MALFORMED_MIN_NON_EMPTY_LINES)]  # exactly the minimum
    corrupted = "".join(f"{line}\n\n" for line in real_lines)
    assert apply_mod._looks_malformed_by_doubled_newlines(corrupted) is True


def test_looks_malformed_flags_a_corrupted_file_missing_its_final_newline():
    # A corrupted file whose last line lacks a trailing newline drops one of
    # its doubled newlines, landing at `2(N-1)/N` (≈1.933 at N=30) rather than
    # a clean `2.0` — the WORST case for this heuristic, and the reason both
    # knobs (ratio AND minimum line count) were tuned together rather than
    # the ratio alone.
    apply_mod = _load("apply")
    n = apply_mod._MALFORMED_MIN_NON_EMPTY_LINES
    real_lines = [f"line {i}" for i in range(n)]
    corrupted = "\n\n".join(real_lines)  # no trailing newline at all
    assert apply_mod._looks_malformed_by_doubled_newlines(corrupted) is True


def test_looks_malformed_does_not_flag_ordinary_single_newline_content():
    apply_mod = _load("apply")
    content = "".join(f"line {i}\n" for i in range(30))
    assert apply_mod._looks_malformed_by_doubled_newlines(content) is False


def test_looks_malformed_does_not_flag_a_realistic_long_reference_doc():
    # Real long docs in this repo mix short and long paragraphs, lists, and
    # headings rather than blanking every single line — the "one paragraph
    # per line, blank between EVERY one" style only shows up in this repo's
    # SHORT reference docs (already excluded by the minimum line count; see
    # `test_looks_malformed_respects_the_minimum_line_count_guard`), and no
    # real file at this length reaches this ratio — pinned directly against
    # the actual synced core by `test_malformed_ratio_never_flags_real_repo_content`
    # below, not by a hand-built approximation of one specific file's shape
    # (a shape that, scaled to this length, is mathematically indistinguishable
    # from corruption by ratio alone — see the constants' own comment).
    apply_mod = _load("apply")
    lines = []
    for i in range(40):
        lines.append(f"- item {i}: a short bullet with no blank line after it")
    lines.append("")
    lines.append("A closing paragraph of ordinary prose, one blank line before it.")
    content = "\n".join(lines) + "\n"
    assert apply_mod._looks_malformed_by_doubled_newlines(content) is False


def test_looks_malformed_respects_the_minimum_line_count_guard():
    # Fewer than `_MALFORMED_MIN_NON_EMPTY_LINES` non-empty lines -> never
    # flagged, even at a clean 2x doubling — guards a short file's natural
    # blank-line spacing from false-positiving.
    apply_mod = _load("apply")
    real_lines = [f"line {i}" for i in range(apply_mod._MALFORMED_MIN_NON_EMPTY_LINES - 1)]
    corrupted = "".join(f"{line}\n\n" for line in real_lines)
    assert apply_mod._looks_malformed_by_doubled_newlines(corrupted) is False


def test_malformed_ratio_never_flags_real_repo_content():
    # The regression this pins directly: an earlier draft of this heuristic
    # (ratio 1.8, minimum 20 lines) flagged a genuine, uncorrupted file in
    # THIS repo's own synced core (`spec-to-pr/references/design-tradeoffs.md`,
    # ratio 1.955) — a real sync would have silently refused it, forever,
    # with no error surfaced (see the orchestrate.py summary printers). Scan
    # every file actually shipped in the synced core so a future doc written
    # in the same blank-line-heavy style can't silently regress this guard.
    apply_mod = _load("apply")
    discover_mod = _load("discover")
    plugin_root = Path(__file__).resolve().parents[3]  # .../.claude/plugins/cla
    # Derived from discover.SCAN_DIRS rather than hand-typed — a hardcoded copy
    # here and a second one in test_no_project_tokens.py both missed
    # `output-styles` when it was added to the real SCAN_DIRS, with every test
    # against the stale copies staying green. See that file's SOURCE_SCAN_ROOTS
    # for the fuller rationale.
    scan_dirs = [d.rsplit("/", 1)[-1] for d in discover_mod.SCAN_DIRS]
    flagged = []
    for scan_dir in scan_dirs:
        base = plugin_root / scan_dir
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if apply_mod._looks_malformed_by_doubled_newlines(content):
                flagged.append(str(path.relative_to(plugin_root)))
    assert flagged == [], (
        f"{len(flagged)} real file(s) would be silently refused as "
        f"'skipped_malformed' by the current threshold: {flagged}"
    )


# ---------- apply: worktree mode ----------


def test_apply_worktree_writes_new_file(synthetic_repos, fake_gh):
    repos = synthetic_repos({"dst": {}})
    apply_mod = _load("apply")
    adaptations = [{
        "asset_path": ".claude/plugins/cla/skills/foo.md",
        "adapted_content": "hello\n",
        "change_summary": "new file",
    }]
    outcomes = apply_mod.apply_worktree(repos[0], adaptations, "src-name")
    assert outcomes[0].status == "wrote"
    assert (repos[0] / ".claude/plugins/cla/skills/foo.md").read_text(encoding="utf-8") == "hello\n"


def test_apply_worktree_overwrites_clean_file(synthetic_repos, fake_gh):
    repos = synthetic_repos({"dst": {".claude/plugins/cla/skills/foo.md": "old\n"}})
    fake_gh["responses"] = []  # default success/empty -> clean
    apply_mod = _load("apply")
    adaptations = [{
        "asset_path": ".claude/plugins/cla/skills/foo.md",
        "adapted_content": "new\n",
        "change_summary": "updated",
    }]
    outcomes = apply_mod.apply_worktree(repos[0], adaptations, "src-name")
    assert outcomes[0].status == "wrote"
    assert (repos[0] / ".claude/plugins/cla/skills/foo.md").read_text(encoding="utf-8") == "new\n"


def test_apply_worktree_refuses_dirty_file(synthetic_repos, fake_gh):
    repos = synthetic_repos({"dst": {".claude/plugins/cla/skills/foo.md": "old\n"}})
    fake_gh["responses"] = [
        (("status", "--porcelain", "--", ".claude/plugins/cla/skills/foo.md"), 0,
         " M .claude/plugins/cla/skills/foo.md\n", ""),
    ]
    apply_mod = _load("apply")
    adaptations = [{
        "asset_path": ".claude/plugins/cla/skills/foo.md",
        "adapted_content": "new\n",
        "change_summary": "updated",
    }]
    outcomes = apply_mod.apply_worktree(repos[0], adaptations, "src-name")
    assert outcomes[0].status == "skipped_dirty_worktree"
    assert (repos[0] / ".claude/plugins/cla/skills/foo.md").read_text(encoding="utf-8") == "old\n"


def test_apply_worktree_fails_closed_when_git_unavailable(synthetic_repos, fake_gh):
    repos = synthetic_repos({"dst": {".claude/plugins/cla/skills/foo.md": "old\n"}})
    fake_gh["responses"] = [
        (("status", "--porcelain", "--", ".claude/plugins/cla/skills/foo.md"), 128, "",
         "fatal: not a git repository"),
    ]
    apply_mod = _load("apply")
    adaptations = [{
        "asset_path": ".claude/plugins/cla/skills/foo.md",
        "adapted_content": "new\n",
        "change_summary": "updated",
    }]
    outcomes = apply_mod.apply_worktree(repos[0], adaptations, "src-name")
    assert outcomes[0].status == "failure"
    assert "refusing to overwrite" in outcomes[0].reason
    # File NOT clobbered.
    assert (repos[0] / ".claude/plugins/cla/skills/foo.md").read_text(encoding="utf-8") == "old\n"


def test_apply_worktree_skips_binary_placeholder(synthetic_repos, fake_gh):
    repos = synthetic_repos({"dst": {}})
    apply_mod = _load("apply")
    adaptations = [{
        "asset_path": ".claude/plugins/cla/skills/foo/icon.png",
        "adapted_content": "<binary file, 1024 bytes>",
        "change_summary": "binary",
    }]
    outcomes = apply_mod.apply_worktree(repos[0], adaptations, "src-name")
    assert outcomes[0].status == "skipped_binary"
    assert not (repos[0] / ".claude/plugins/cla/skills/foo/icon.png").exists()


def test_apply_worktree_normalizes_crlf_before_writing(synthetic_repos, fake_gh):
    repos = synthetic_repos({"dst": {}})
    apply_mod = _load("apply")
    adaptations = [{
        "asset_path": ".claude/plugins/cla/skills/foo.md",
        "adapted_content": "line one\r\nline two\r\nline three\r\n",
        "change_summary": "new file",
    }]
    outcomes = apply_mod.apply_worktree(repos[0], adaptations, "src-name")
    assert outcomes[0].status == "wrote"
    written = (repos[0] / ".claude/plugins/cla/skills/foo.md").read_bytes()
    assert b"\r" not in written
    assert written == b"line one\nline two\nline three\n"


def test_apply_worktree_refuses_doubled_newline_corruption(synthetic_repos, fake_gh):
    # The regression this guards: a prior sync silently turned every `\r\n`
    # into `\n\n` in 19 of 37 files. Byte counts stayed identical, so nothing
    # caught it. Simulate the fingerprint directly: N real lines, each
    # followed by a spurious blank line.
    apply_mod = _load("apply")
    real_lines = [f"line {i}" for i in range(30)]
    corrupted = "".join(f"{line}\n\n" for line in real_lines)
    repos = synthetic_repos({"dst": {}})
    adaptations = [{
        "asset_path": ".claude/plugins/cla/skills/foo.md",
        "adapted_content": corrupted,
        "change_summary": "corrupted",
    }]
    outcomes = apply_mod.apply_worktree(repos[0], adaptations, "src-name")
    assert outcomes[0].status == "skipped_malformed"
    assert not (repos[0] / ".claude/plugins/cla/skills/foo.md").exists()


def test_apply_worktree_does_not_flag_a_normal_file_with_some_blank_lines(synthetic_repos, fake_gh):
    # A guard against false positives: ordinary prose with occasional blank
    # lines between paragraphs (not after EVERY line) must not be refused.
    apply_mod = _load("apply")
    lines = []
    for i in range(30):
        lines.append(f"paragraph {i} line one")
        lines.append(f"paragraph {i} line two")
        if i % 3 == 0:
            lines.append("")  # occasional blank line, not after every line
    content = "\n".join(lines) + "\n"
    repos = synthetic_repos({"dst": {}})
    adaptations = [{
        "asset_path": ".claude/plugins/cla/skills/foo.md",
        "adapted_content": content,
        "change_summary": "normal prose",
    }]
    outcomes = apply_mod.apply_worktree(repos[0], adaptations, "src-name")
    assert outcomes[0].status == "wrote"


def test_apply_worktree_does_not_flag_a_short_file(synthetic_repos, fake_gh):
    # A short file naturally blank-line-spaced (e.g. a tiny doc) must not
    # false-positive just because it happens to have a blank line per line —
    # the minimum-line-count guard exists for exactly this.
    apply_mod = _load("apply")
    content = "title\n\nsubtitle\n\nbody\n"
    repos = synthetic_repos({"dst": {}})
    adaptations = [{
        "asset_path": ".claude/plugins/cla/skills/foo.md",
        "adapted_content": content,
        "change_summary": "short file",
    }]
    outcomes = apply_mod.apply_worktree(repos[0], adaptations, "src-name")
    assert outcomes[0].status == "wrote"


def test_apply_worktree_skipped_malformed_leaves_lock_entry_unchanged(synthetic_repos, fake_gh):
    repos = synthetic_repos({"dst": {}})
    seeded = {"last_synced_sha256": "abc", "source": "old-src"}
    _seed_lock(repos[0], {".claude/plugins/cla/skills/foo.md": seeded})
    apply_mod = _load("apply")
    real_lines = [f"line {i}" for i in range(30)]
    corrupted = "".join(f"{line}\n\n" for line in real_lines)
    adaptations = [{
        "asset_path": ".claude/plugins/cla/skills/foo.md",
        "adapted_content": corrupted,
        "change_summary": "corrupted",
    }]
    apply_mod.apply_worktree(repos[0], adaptations, "src-name")
    lock = json.loads(
        (repos[0] / ".claude/plugins/cla/.cla-sync-lock.json").read_text(encoding="utf-8")
    )
    # Full-dict comparison, not just one field — a future refactor that
    # started calling `_update_lock` unconditionally (rather than only for
    # `written` entries) could otherwise still rewrite `last_synced_sha256`
    # while leaving `source` untouched, and a single-field check wouldn't
    # catch it.
    assert lock[".claude/plugins/cla/skills/foo.md"] == seeded


def test_apply_pr_normalizes_crlf_before_writing(synthetic_repos, fake_gh, tmp_path):
    repos = synthetic_repos({"dst": {}})
    fake_gh["responses"] = [
        (("status", "--porcelain"), 0, "", ""),
        (("repo", "view", "--json"), 0, "main\n", ""),
        (("checkout", "-b"), 0, "", ""),
        (("add", "-A"), 0, "", ""),
        (("commit", "-F"), 0, "", ""),
        (("push", "-u", "origin"), 0, "", ""),
        (("pr", "create"), 0, "https://example.com/pr/1\n", ""),
    ]
    apply_mod = _load("apply")
    adaptations = [{
        "asset_path": ".claude/plugins/cla/skills/foo.md",
        "adapted_content": "line one\r\nline two\r\n",
        "change_summary": "new file",
    }]
    outcomes, pr_result = apply_mod.apply_pr(repos[0], adaptations, "src-name", tmp_path)
    assert outcomes[0].status == "wrote"
    assert outcomes[0].reason == "line endings normalized (CRLF/CR → LF)"
    assert pr_result.pr_url is not None
    written = (repos[0] / ".claude/plugins/cla/skills/foo.md").read_bytes()
    assert b"\r" not in written
    assert written == b"line one\nline two\n"


def test_apply_pr_mixed_batch_writes_the_clean_file_and_refuses_the_malformed_one(
    synthetic_repos, fake_gh, tmp_path,
):
    # The real-world shape this hardening is for: NOT every file in a sync is
    # corrupted (19 of 37, not 37 of 37). One malformed asset must not abort
    # the whole PR — the clean one still lands.
    repos = synthetic_repos({"dst": {}})
    fake_gh["responses"] = [
        (("status", "--porcelain"), 0, "", ""),
        (("repo", "view", "--json"), 0, "main\n", ""),
        (("checkout", "-b"), 0, "", ""),
        (("add", "-A"), 0, "", ""),
        (("commit", "-F"), 0, "", ""),
        (("push", "-u", "origin"), 0, "", ""),
        (("pr", "create"), 0, "https://example.com/pr/1\n", ""),
    ]
    apply_mod = _load("apply")
    real_lines = [f"line {i}" for i in range(30)]
    corrupted = "".join(f"{line}\n\n" for line in real_lines)
    adaptations = [
        {"asset_path": ".claude/plugins/cla/skills/clean.md",
         "adapted_content": "hello\n", "change_summary": "clean"},
        {"asset_path": ".claude/plugins/cla/skills/corrupted.md",
         "adapted_content": corrupted, "change_summary": "corrupted"},
    ]
    outcomes, pr_result = apply_mod.apply_pr(repos[0], adaptations, "src-name", tmp_path)
    statuses = {o.asset_path: o.status for o in outcomes}
    assert statuses[".claude/plugins/cla/skills/clean.md"] == "wrote"
    assert statuses[".claude/plugins/cla/skills/corrupted.md"] == "skipped_malformed"
    assert pr_result.pr_url is not None
    assert (repos[0] / ".claude/plugins/cla/skills/clean.md").exists()
    assert not (repos[0] / ".claude/plugins/cla/skills/corrupted.md").exists()
    lock = json.loads(
        (repos[0] / ".claude/plugins/cla/.cla-sync-lock.json").read_text(encoding="utf-8")
    )
    assert ".claude/plugins/cla/skills/clean.md" in lock
    assert ".claude/plugins/cla/skills/corrupted.md" not in lock


def test_apply_pr_refuses_doubled_newline_corruption(synthetic_repos, fake_gh, tmp_path):
    apply_mod = _load("apply")
    real_lines = [f"line {i}" for i in range(30)]
    corrupted = "".join(f"{line}\n\n" for line in real_lines)
    repos = synthetic_repos({"dst": {}})
    fake_gh["responses"] = [
        (("status", "--porcelain"), 0, "", ""),
        (("repo", "view", "--json"), 0, "main\n", ""),
        (("checkout", "-b"), 0, "", ""),
    ]
    adaptations = [{
        "asset_path": ".claude/plugins/cla/skills/foo.md",
        "adapted_content": corrupted,
        "change_summary": "corrupted",
    }]
    outcomes, pr_result = apply_mod.apply_pr(repos[0], adaptations, "src-name", tmp_path)
    assert outcomes[0].status == "skipped_malformed"
    # Nothing else to write -> apply_pr's "no files written; aborting PR" path.
    assert pr_result.pr_url is None


def test_apply_worktree_null_adapted_content_fails(synthetic_repos, fake_gh):
    repos = synthetic_repos({"dst": {}})
    apply_mod = _load("apply")
    adaptations = [{
        "asset_path": ".claude/plugins/cla/skills/foo.md",
        "adapted_content": None,
        "change_summary": "",
    }]
    outcomes = apply_mod.apply_worktree(repos[0], adaptations, "src-name")
    assert outcomes[0].status == "failure"
    assert "null" in outcomes[0].reason


def test_apply_worktree_per_file_isolation(synthetic_repos, fake_gh):
    repos = synthetic_repos({"dst": {".claude/plugins/cla/skills/dirty.md": "old\n"}})
    fake_gh["responses"] = [
        (("status", "--porcelain", "--", ".claude/plugins/cla/skills/dirty.md"), 0,
         " M .claude/plugins/cla/skills/dirty.md\n", ""),
    ]
    apply_mod = _load("apply")
    adaptations = [
        {"asset_path": ".claude/plugins/cla/skills/dirty.md",
         "adapted_content": "new\n", "change_summary": ""},
        {"asset_path": ".claude/plugins/cla/skills/clean.md",
         "adapted_content": "fresh\n", "change_summary": ""},
        {"asset_path": ".claude/plugins/cla/skills/foo/icon.png",
         "adapted_content": "<binary file, 50 bytes>", "change_summary": ""},
    ]
    outcomes = apply_mod.apply_worktree(repos[0], adaptations, "src-name")
    statuses = {o.asset_path: o.status for o in outcomes}
    assert statuses[".claude/plugins/cla/skills/dirty.md"] == "skipped_dirty_worktree"
    assert statuses[".claude/plugins/cla/skills/clean.md"] == "wrote"
    assert statuses[".claude/plugins/cla/skills/foo/icon.png"] == "skipped_binary"


# ---------- apply: pr mode ----------


def test_apply_pr_refuses_dirty_tree(synthetic_repos, fake_gh, tmp_path):
    repos = synthetic_repos({"dst": {".claude/plugins/cla/skills/foo.md": "x\n"}})
    fake_gh["responses"] = [
        (("status", "--porcelain"), 0, " M dirty.txt\n", ""),
    ]
    apply_mod = _load("apply")
    adaptations = [{"asset_path": ".claude/plugins/cla/skills/foo.md",
                    "adapted_content": "new\n", "change_summary": ""}]
    _, pr_result = apply_mod.apply_pr(repos[0], adaptations, "src-name", tmp_path)
    assert pr_result.pr_url is None
    assert "dirty working tree" in pr_result.reason


def test_apply_pr_default_branch_detection_failure(synthetic_repos, fake_gh, tmp_path):
    repos = synthetic_repos({"dst": {".claude/plugins/cla/skills/foo.md": "x\n"}})
    fake_gh["responses"] = [
        (("status", "--porcelain"), 0, "", ""),
        (("repo", "view", "--json"), 1, "", "auth failed"),
    ]
    apply_mod = _load("apply")
    adaptations = [{"asset_path": ".claude/plugins/cla/skills/foo.md",
                    "adapted_content": "new\n", "change_summary": ""}]
    _, pr_result = apply_mod.apply_pr(repos[0], adaptations, "src-name", tmp_path)
    assert pr_result.pr_url is None
    assert "default branch" in pr_result.reason


def test_apply_pr_push_failure_rolls_back_branch(synthetic_repos, fake_gh, tmp_path):
    repos = synthetic_repos({"dst": {}})
    fake_gh["responses"] = [
        (("status", "--porcelain"), 0, "", ""),
        (("repo", "view", "--json"), 0, "main\n", ""),
        (("checkout", "-b"), 0, "", ""),
        (("add", "-A"), 0, "", ""),
        (("commit", "-F"), 0, "", ""),
        (("push", "-u", "origin"), 1, "", "push rejected"),
    ]
    apply_mod = _load("apply")
    adaptations = [{"asset_path": ".claude/plugins/cla/skills/foo.md",
                    "adapted_content": "new\n", "change_summary": ""}]
    outcomes, pr_result = apply_mod.apply_pr(repos[0], adaptations, "src", tmp_path)
    assert pr_result.pr_url is None
    assert "push" in pr_result.reason
    # rollback `git checkout main` should appear in calls
    rollback_calls = [c for c in fake_gh["calls"] if c[:2] == ["git", "checkout"] and "main" in c]
    assert rollback_calls, "expected a rollback `git checkout main` call after push failure"


def test_apply_pr_commit_failure_rolls_back_branch(synthetic_repos, fake_gh, tmp_path):
    repos = synthetic_repos({"dst": {}})
    fake_gh["responses"] = [
        (("status", "--porcelain"), 0, "", ""),
        (("repo", "view", "--json"), 0, "main\n", ""),
        (("checkout", "-b"), 0, "", ""),
        (("add", "-A"), 0, "", ""),
        (("commit", "-F"), 1, "", "nothing to commit"),
    ]
    apply_mod = _load("apply")
    adaptations = [{"asset_path": ".claude/plugins/cla/skills/foo.md",
                    "adapted_content": "new\n", "change_summary": ""}]
    _, pr_result = apply_mod.apply_pr(repos[0], adaptations, "src", tmp_path)
    assert pr_result.pr_url is None
    assert "commit" in pr_result.reason


def test_apply_pr_gh_pr_create_failure_rolls_back(synthetic_repos, fake_gh, tmp_path):
    repos = synthetic_repos({"dst": {}})
    fake_gh["responses"] = [
        (("status", "--porcelain"), 0, "", ""),
        (("repo", "view", "--json"), 0, "main\n", ""),
        (("checkout", "-b"), 0, "", ""),
        (("add", "-A"), 0, "", ""),
        (("commit", "-F"), 0, "", ""),
        (("push", "-u", "origin"), 0, "", ""),
        (("pr", "create"), 1, "", "auth required"),
    ]
    apply_mod = _load("apply")
    adaptations = [{"asset_path": ".claude/plugins/cla/skills/foo.md",
                    "adapted_content": "new\n", "change_summary": ""}]
    _, pr_result = apply_mod.apply_pr(repos[0], adaptations, "src", tmp_path)
    assert pr_result.pr_url is None
    assert "pr create" in pr_result.reason


def test_apply_pr_happy_path(synthetic_repos, fake_gh, tmp_path):
    repos = synthetic_repos({"dst": {}})
    fake_gh["responses"] = [
        (("status", "--porcelain"), 0, "", ""),
        (("repo", "view", "--json"), 0, "main\n", ""),
        (("checkout", "-b"), 0, "", ""),
        (("add", "-A"), 0, "", ""),
        (("commit", "-F"), 0, "", ""),
        (("push", "-u", "origin"), 0, "", ""),
        (("pr", "create"), 0, "https://github.com/x/y/pull/42\n", ""),
    ]
    apply_mod = _load("apply")
    adaptations = [{"asset_path": ".claude/plugins/cla/skills/foo.md",
                    "adapted_content": "new\n", "change_summary": "new file"}]
    outcomes, pr_result = apply_mod.apply_pr(repos[0], adaptations, "src-name", tmp_path)
    assert pr_result.pr_url == "https://github.com/x/y/pull/42"
    assert outcomes[0].status == "wrote"
    assert (repos[0] / ".claude/plugins/cla/skills/foo.md").read_text(encoding="utf-8") == "new\n"


# ---------- apply: lockfile round-trip (cla-sync-provenance) ----------


def _read_test_lock(repo: Path) -> dict:
    lock_path = repo / ".claude" / "plugins" / "cla" / ".cla-sync-lock.json"
    return json.loads(lock_path.read_text(encoding="utf-8"))


def test_lockfile_gains_entry_on_wrote_outcome(synthetic_repos, fake_gh):
    repos = synthetic_repos({"dst": {}})
    apply_mod = _load("apply")
    adaptations = [{
        "asset_path": ".claude/plugins/cla/skills/foo.md",
        "adapted_content": "hello\n",
        "change_summary": "new",
    }]
    outcomes = apply_mod.apply_worktree(repos[0], adaptations, "src-name")
    assert outcomes[0].status == "wrote"
    lock = _read_test_lock(repos[0])
    entry = lock[".claude/plugins/cla/skills/foo.md"]
    assert entry["last_synced_sha256"] == hashlib.sha256(b"hello\n").hexdigest()
    assert entry["source"] == "src-name"


def test_lockfile_records_the_source_commit_when_one_is_known(synthetic_repos, fake_gh):
    """Without this the lock can answer "does this file still match what was
    written?" but not "written from WHAT?" — the source NAME is a moving target,
    since the same repo produces different content on every commit. Recording the
    sha is what makes a sync reproducible after the fact."""
    repos = synthetic_repos({"dst": {}})
    apply_mod = _load("apply")
    adaptations = [{
        "asset_path": ".claude/plugins/cla/skills/foo.md",
        "adapted_content": "hello\n",
        "change_summary": "new",
    }]
    apply_mod.apply_worktree(repos[0], adaptations, "src-name", "a" * 40)
    entry = _read_test_lock(repos[0])[".claude/plugins/cla/skills/foo.md"]
    assert entry["source_commit"] == "a" * 40


def test_lockfile_omits_the_source_commit_when_there_is_none(synthetic_repos, fake_gh):
    """A source that isn't a git checkout (a plain directory, an export) is a
    legitimate sync source. Provenance degrades to the previous shape rather than
    recording a null or failing the run."""
    repos = synthetic_repos({"dst": {}})
    apply_mod = _load("apply")
    adaptations = [{
        "asset_path": ".claude/plugins/cla/skills/foo.md",
        "adapted_content": "hello\n",
        "change_summary": "new",
    }]
    apply_mod.apply_worktree(repos[0], adaptations, "src-name")
    entry = _read_test_lock(repos[0])[".claude/plugins/cla/skills/foo.md"]
    assert "source_commit" not in entry
    assert entry["source"] == "src-name"


def test_lockfile_records_written_bytes_not_raw_source_hash(synthetic_repos, fake_gh):
    """The recorded sha is over the ADAPTED content actually written, not whatever a
    (hypothetical) raw source hash would have been — the two differ here on purpose."""
    repos = synthetic_repos({"dst": {}})
    apply_mod = _load("apply")
    raw_source_would_have_been = "RAW SOURCE, never written locally\n"
    adaptations = [{
        "asset_path": ".claude/plugins/cla/skills/foo.md",
        "adapted_content": "ADAPTED, written locally\n",
        "change_summary": "adapted",
    }]
    apply_mod.apply_worktree(repos[0], adaptations, "src-name")
    lock = _read_test_lock(repos[0])
    entry = lock[".claude/plugins/cla/skills/foo.md"]
    assert entry["last_synced_sha256"] == hashlib.sha256(b"ADAPTED, written locally\n").hexdigest()
    assert entry["last_synced_sha256"] != hashlib.sha256(raw_source_would_have_been.encode("utf-8")).hexdigest()


def test_lockfile_untouched_for_skipped_dirty_outcome(synthetic_repos, fake_gh):
    repos = synthetic_repos({"dst": {".claude/plugins/cla/skills/dirty.md": "old\n"}})
    prior_sha = hashlib.sha256(b"prior\n").hexdigest()
    _seed_lock(repos[0], {
        ".claude/plugins/cla/skills/dirty.md": {"last_synced_sha256": prior_sha, "source": "old-src"},
    })
    fake_gh["responses"] = [
        (("status", "--porcelain", "--", ".claude/plugins/cla/skills/dirty.md"), 0,
         " M .claude/plugins/cla/skills/dirty.md\n", ""),
    ]
    apply_mod = _load("apply")
    adaptations = [{
        "asset_path": ".claude/plugins/cla/skills/dirty.md",
        "adapted_content": "new\n",
        "change_summary": "",
    }]
    outcomes = apply_mod.apply_worktree(repos[0], adaptations, "src-name")
    assert outcomes[0].status == "skipped_dirty_worktree"
    lock = _read_test_lock(repos[0])
    entry = lock[".claude/plugins/cla/skills/dirty.md"]
    assert entry["last_synced_sha256"] == prior_sha
    assert entry["source"] == "old-src"


def test_lockfile_untouched_for_failure_outcome(synthetic_repos, fake_gh):
    repos = synthetic_repos({"dst": {".claude/plugins/cla/skills/dirty.md": "old\n"}})
    prior_sha = hashlib.sha256(b"prior\n").hexdigest()
    _seed_lock(repos[0], {
        ".claude/plugins/cla/skills/dirty.md": {"last_synced_sha256": prior_sha, "source": "old-src"},
    })
    fake_gh["responses"] = [
        (("status", "--porcelain", "--", ".claude/plugins/cla/skills/dirty.md"), 128, "",
         "fatal: not a git repository"),
    ]
    apply_mod = _load("apply")
    adaptations = [{
        "asset_path": ".claude/plugins/cla/skills/dirty.md",
        "adapted_content": "new\n",
        "change_summary": "",
    }]
    outcomes = apply_mod.apply_worktree(repos[0], adaptations, "src-name")
    assert outcomes[0].status == "failure"
    lock = _read_test_lock(repos[0])
    entry = lock[".claude/plugins/cla/skills/dirty.md"]
    assert entry["last_synced_sha256"] == prior_sha
    assert entry["source"] == "old-src"


def test_lockfile_staged_in_pr_mode_before_commit(synthetic_repos, fake_gh, tmp_path):
    repos = synthetic_repos({"dst": {}})
    fake_gh["responses"] = [
        (("status", "--porcelain"), 0, "", ""),
        (("repo", "view", "--json"), 0, "main\n", ""),
        (("checkout", "-b"), 0, "", ""),
        (("add", "-A"), 0, "", ""),
        (("commit", "-F"), 0, "", ""),
        (("push", "-u", "origin"), 0, "", ""),
        (("pr", "create"), 0, "https://github.com/x/y/pull/1\n", ""),
    ]
    apply_mod = _load("apply")
    adaptations = [{"asset_path": ".claude/plugins/cla/skills/foo.md",
                    "adapted_content": "new\n", "change_summary": "new file"}]
    outcomes, pr_result = apply_mod.apply_pr(repos[0], adaptations, "src-name", tmp_path)
    assert pr_result.pr_url == "https://github.com/x/y/pull/1"
    lock = _read_test_lock(repos[0])
    assert lock[".claude/plugins/cla/skills/foo.md"]["last_synced_sha256"] == hashlib.sha256(b"new\n").hexdigest()
    assert lock[".claude/plugins/cla/skills/foo.md"]["source"] == "src-name"
    # `git add -A` was actually invoked (the lockfile write happens before it in the
    # code path, so a successful add/commit/push/PR run proves it was staged too).
    add_calls = [c for c in fake_gh["calls"] if c[:2] == ["git", "add"]]
    assert add_calls, "expected a `git add -A` call"


def test_lockfile_written_before_git_add_in_pr_mode(synthetic_repos, fake_gh, tmp_path, monkeypatch):
    """Strengthens `test_lockfile_staged_in_pr_mode_before_commit` above: that test
    only proves the lockfile ENDS UP on disk after a successful PR run — `fake_gh`'s
    call log by itself can't express "did the write happen before `git add -A`", so
    it would NOT catch a regression that moved the lock write to after `git add -A`
    (which would still pass since the lockfile would still exist on disk, just
    unstaged). This test records the actual ORDER of events by having the (real)
    `_update_lock` push a marker into the same `fake_gh["calls"]` list `subprocess.run`
    already appends to, then asserts that marker's index precedes `git add -A`'s."""
    repos = synthetic_repos({"dst": {}})
    fake_gh["responses"] = [
        (("status", "--porcelain"), 0, "", ""),
        (("repo", "view", "--json"), 0, "main\n", ""),
        (("checkout", "-b"), 0, "", ""),
        (("add", "-A"), 0, "", ""),
        (("commit", "-F"), 0, "", ""),
        (("push", "-u", "origin"), 0, "", ""),
        (("pr", "create"), 0, "https://github.com/x/y/pull/1\n", ""),
    ]
    apply_mod = _load("apply")
    real_update_lock = apply_mod._update_lock

    # `**kwargs` deliberately: this wrapper only cares WHEN the lock is written,
    # not with what. Enumerating the parameters made it a second, silent copy of
    # `_update_lock`'s signature that broke the moment the real one grew a
    # keyword — and a TypeError here reads as a bug in apply.py, not in a stub.
    def _recording_update_lock(local_repo, written, source_name, source_commit=None, **kwargs):
        fake_gh["calls"].append(["LOCK_WRITE_MARKER"])
        return real_update_lock(local_repo, written, source_name, **kwargs)

    monkeypatch.setattr(apply_mod, "_update_lock", _recording_update_lock)

    adaptations = [{"asset_path": ".claude/plugins/cla/skills/foo.md",
                    "adapted_content": "new\n", "change_summary": "new file"}]
    outcomes, pr_result = apply_mod.apply_pr(repos[0], adaptations, "src-name", tmp_path)
    assert pr_result.pr_url == "https://github.com/x/y/pull/1"

    calls = fake_gh["calls"]
    lock_idx = next(i for i, c in enumerate(calls) if c == ["LOCK_WRITE_MARKER"])
    add_idx = next(i for i, c in enumerate(calls) if c[:2] == ["git", "add"])
    assert lock_idx < add_idx, (
        "lockfile write must happen BEFORE `git add -A` so it is staged in the "
        "same commit/push/PR — this must fail if that ordering ever regresses"
    )


def test_apply_worktree_lock_write_merges_preserving_other_entries(synthetic_repos, fake_gh):
    """The lockfile write is read-merge-write, not replace: a pre-existing entry for
    file B (untouched by this run) must survive after `apply_worktree` writes a
    DIFFERENT file A — guards against a regression that replaces the whole lockfile
    with just this run's entries instead of merging into it."""
    repos = synthetic_repos({"dst": {}})
    prior_sha = hashlib.sha256(b"B content\n").hexdigest()
    _seed_lock(repos[0], {
        ".claude/plugins/cla/skills/b.md": {"last_synced_sha256": prior_sha, "source": "old-src"},
    })
    apply_mod = _load("apply")
    adaptations = [{
        "asset_path": ".claude/plugins/cla/skills/a.md",
        "adapted_content": "A content\n",
        "change_summary": "new",
    }]
    outcomes = apply_mod.apply_worktree(repos[0], adaptations, "src-name")
    assert outcomes[0].status == "wrote"

    lock = _read_test_lock(repos[0])
    # B's entry survives untouched.
    assert lock[".claude/plugins/cla/skills/b.md"]["last_synced_sha256"] == prior_sha
    assert lock[".claude/plugins/cla/skills/b.md"]["source"] == "old-src"
    # A's entry was added by this run.
    assert lock[".claude/plugins/cla/skills/a.md"]["last_synced_sha256"] == hashlib.sha256(b"A content\n").hexdigest()
    assert lock[".claude/plugins/cla/skills/a.md"]["source"] == "src-name"


def test_lockfile_write_failure_is_nonfatal(synthetic_repos, fake_gh, monkeypatch):
    """A lockfile write failure is reported to stderr but never fails the run whose
    files already landed."""
    repos = synthetic_repos({"dst": {}})
    apply_mod = _load("apply")

    def _boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(apply_mod, "_write_lock", _boom)
    adaptations = [{
        "asset_path": ".claude/plugins/cla/skills/foo.md",
        "adapted_content": "hello\n",
        "change_summary": "new",
    }]
    outcomes = apply_mod.apply_worktree(repos[0], adaptations, "src-name")
    assert outcomes[0].status == "wrote"
    assert (repos[0] / ".claude/plugins/cla/skills/foo.md").read_text(encoding="utf-8") == "hello\n"


# ---------- orchestrate: source-commit provenance ----------


def _init_repo_with_commit(path: Path):
    subprocess.run(["git", "-C", str(path), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "a@b.c"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "a"], check=True)
    (path / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-q", "-m", "seed"],
        check=True, capture_output=True,
    )


def test_source_commit_is_a_bare_sha_when_the_source_is_clean(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    _init_repo_with_commit(src)
    got = _load("orchestrate")._source_commit(src)
    assert got and len(got) == 40 and got.isalnum()


def test_source_commit_is_marked_dirty_when_the_source_has_uncommitted_work(tmp_path):
    """CLA is designed to load live from a working tree, so a dirty source is
    the NORMAL sync case. A bare sha there names a revision that does not
    contain the bytes actually copied — worse than recording nothing, because
    it looks authoritative."""
    src = tmp_path / "src"
    src.mkdir()
    _init_repo_with_commit(src)
    (src / "seed.txt").write_text("edited in the working tree\n", encoding="utf-8")

    got = _load("orchestrate")._source_commit(src)
    assert got and got.endswith("-dirty"), got
    assert len(got.removesuffix("-dirty")) == 40


def test_source_commit_is_none_when_the_source_is_not_a_repo(tmp_path):
    # A plain directory or an export is a legitimate sync source, so this
    # degrades to "no provenance" rather than failing the run.
    plain = tmp_path / "plain"
    plain.mkdir()
    assert _load("orchestrate")._source_commit(plain) is None


# ---------- orchestrate: summary printers surface every outcome status ----------


def test_worktree_summary_surfaces_skipped_malformed(capsys):
    # The refusal this whole PR adds must not be invisible: before this fix,
    # neither summary printer had a bucket for `skipped_malformed` at all, so
    # a refused file printed NOWHERE — a PR could open, or a worktree sync
    # could finish, silently missing a file with zero trace in the summary.
    orchestrate_mod = _load("orchestrate")
    apply_mod = _load("apply")
    outcomes = [
        apply_mod.ApplyOutcome(".claude/plugins/cla/skills/foo.md", "wrote", None),
        apply_mod.ApplyOutcome(
            ".claude/plugins/cla/skills/bad.md", "skipped_malformed",
            "adapted_content's newline count is ~2x its non-empty line count "
            "(doubled-newline corruption fingerprint); not writing",
        ),
    ]
    rc = orchestrate_mod._print_worktree_summary(outcomes)
    out = capsys.readouterr().out
    assert "bad.md" in out
    assert "corruption fingerprint" in out
    assert rc == 0  # a clean file DID write, so this isn't a hard failure


def test_worktree_summary_reports_failure_when_only_malformed_and_nothing_wrote(capsys):
    orchestrate_mod = _load("orchestrate")
    apply_mod = _load("apply")
    outcomes = [
        apply_mod.ApplyOutcome(".claude/plugins/cla/skills/bad.md", "skipped_malformed", "corrupted"),
    ]
    rc = orchestrate_mod._print_worktree_summary(outcomes)
    assert rc == 1


def test_pr_summary_surfaces_skipped_malformed_on_the_happy_path(capsys):
    orchestrate_mod = _load("orchestrate")
    apply_mod = _load("apply")
    outcomes = [
        apply_mod.ApplyOutcome(".claude/plugins/cla/skills/foo.md", "wrote", None),
        apply_mod.ApplyOutcome(".claude/plugins/cla/skills/bad.md", "skipped_malformed", "corrupted"),
    ]
    pr_result = apply_mod.PRResult("sync/from-src", "https://example.com/pr/1", None)
    rc = orchestrate_mod._print_pr_summary(outcomes, pr_result)
    out = capsys.readouterr().out
    assert "bad.md" in out
    assert rc == 0


def test_pr_summary_surfaces_skipped_malformed_on_the_all_refused_path(capsys):
    orchestrate_mod = _load("orchestrate")
    apply_mod = _load("apply")
    outcomes = [
        apply_mod.ApplyOutcome(".claude/plugins/cla/skills/bad.md", "skipped_malformed", "corrupted"),
    ]
    pr_result = apply_mod.PRResult(None, None, "no files written; aborting PR")
    rc = orchestrate_mod._print_pr_summary(outcomes, pr_result)
    out = capsys.readouterr().out
    assert "bad.md" in out
    assert rc == 1


# ---------- orchestrate: end-to-end ----------


def test_orchestrate_discover_writes_state(synthetic_repos, tmp_path, monkeypatch):
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/foo.md": "from-source\n"},
        "dst": {".claude/plugins/cla/skills/foo.md": "from-local\n"},
    })
    monkeypatch.setenv("CLAUDE_SYNC_CONFIG_PATH", str(tmp_path / "cfg.json"))
    monkeypatch.setenv("CLAUDE_SYNC_ROOT", str(repos[0].parent))
    orchestrate_mod = _load("orchestrate")

    rc = orchestrate_mod.main(argv=[
        "discover", str(repos[0]), "--local", str(repos[1])
    ])
    assert rc == 0
    state_root = repos[1] / "temp" / "sync-state"
    assert state_root.exists()
    runs = list(state_root.iterdir())
    assert len(runs) == 1
    divergences = json.loads((runs[0] / "divergences.json").read_text(encoding="utf-8"))
    assert divergences["source"]["name"] == "src"
    assert len(divergences["files"]) == 1
    assert divergences["files"][0]["asset_path"] == ".claude/plugins/cla/skills/foo.md"
    assert "skipped" in divergences


def test_orchestrate_discover_zero_divergences_exit_0(synthetic_repos, tmp_path, monkeypatch, capsys):
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/foo.md": "same\n"},
        "dst": {".claude/plugins/cla/skills/foo.md": "same\n"},
    })
    monkeypatch.setenv("CLAUDE_SYNC_CONFIG_PATH", str(tmp_path / "cfg.json"))
    monkeypatch.setenv("CLAUDE_SYNC_ROOT", str(repos[0].parent))
    orchestrate_mod = _load("orchestrate")
    rc = orchestrate_mod.main(argv=[
        "discover", str(repos[0]), "--local", str(repos[1])
    ])
    assert rc == 0
    assert "Nothing to sync" in capsys.readouterr().out


def test_orchestrate_discover_same_source_and_local_fails(synthetic_repos, tmp_path, monkeypatch):
    repos = synthetic_repos({"repo": {".claude/plugins/cla/skills/foo.md": "x\n"}})
    monkeypatch.setenv("CLAUDE_SYNC_CONFIG_PATH", str(tmp_path / "cfg.json"))
    monkeypatch.setenv("CLAUDE_SYNC_ROOT", str(repos[0].parent))
    orchestrate_mod = _load("orchestrate")
    rc = orchestrate_mod.main(argv=[
        "discover", str(repos[0]), "--local", str(repos[0])
    ])
    assert rc == 2


def test_orchestrate_apply_missing_adaptations_exit_2(synthetic_repos, tmp_path, monkeypatch, capsys):
    repos = synthetic_repos({"dst": {}})
    monkeypatch.setenv("CLAUDE_SYNC_CONFIG_PATH", str(tmp_path / "cfg.json"))
    monkeypatch.setenv("CLAUDE_SYNC_ROOT", str(repos[0].parent))
    # Write a divergences.json without an adaptations.json.
    state_dir = repos[0] / "temp" / "sync-state" / "run1"
    state_dir.mkdir(parents=True)
    (state_dir / "divergences.json").write_text(
        json.dumps({"source": {"name": "src", "path": "x"},
                    "local": {"path": "y"}, "files": [], "skipped": []}),
        encoding="utf-8",
    )
    orchestrate_mod = _load("orchestrate")
    rc = orchestrate_mod.main(argv=[
        "apply", "--run", "run1", "--local", str(repos[0])
    ])
    assert rc == 2
    assert "adaptations.json" in capsys.readouterr().err


def test_orchestrate_apply_worktree_happy_path(synthetic_repos, tmp_path, monkeypatch, fake_gh):
    repos = synthetic_repos({"dst": {}})
    monkeypatch.setenv("CLAUDE_SYNC_CONFIG_PATH", str(tmp_path / "cfg.json"))
    monkeypatch.setenv("CLAUDE_SYNC_ROOT", str(repos[0].parent))

    state_dir = repos[0] / "temp" / "sync-state" / "run1"
    state_dir.mkdir(parents=True)
    (state_dir / "divergences.json").write_text(
        json.dumps({"source": {"name": "src", "path": "x"},
                    "local": {"path": str(repos[0])},
                    "files": [], "skipped": []}),
        encoding="utf-8",
    )
    (state_dir / "adaptations.json").write_text(
        json.dumps({"run_id": "run1", "adaptations": [{
            "asset_path": ".claude/plugins/cla/skills/foo.md",
            "adapted_content": "hello\n",
            "change_summary": "new",
        }]}),
        encoding="utf-8",
    )
    orchestrate_mod = _load("orchestrate")
    rc = orchestrate_mod.main(argv=[
        "apply", "--run", "run1", "--mode", "worktree", "--local", str(repos[0])
    ])
    assert rc == 0
    assert (repos[0] / ".claude/plugins/cla/skills/foo.md").read_text(encoding="utf-8") == "hello\n"


def test_orchestrate_apply_corrupted_adaptations_json_exit_2(synthetic_repos, tmp_path, monkeypatch, capsys):
    repos = synthetic_repos({"dst": {}})
    monkeypatch.setenv("CLAUDE_SYNC_CONFIG_PATH", str(tmp_path / "cfg.json"))
    monkeypatch.setenv("CLAUDE_SYNC_ROOT", str(repos[0].parent))

    state_dir = repos[0] / "temp" / "sync-state" / "run1"
    state_dir.mkdir(parents=True)
    (state_dir / "divergences.json").write_text(
        json.dumps({"source": {"name": "src", "path": "x"},
                    "local": {"path": "y"}, "files": [], "skipped": []}),
        encoding="utf-8",
    )
    (state_dir / "adaptations.json").write_text("{not json", encoding="utf-8")
    orchestrate_mod = _load("orchestrate")
    rc = orchestrate_mod.main(argv=[
        "apply", "--run", "run1", "--local", str(repos[0])
    ])
    assert rc == 2
    assert "not valid JSON" in capsys.readouterr().err


# ---------- adaptation prompt content lock ----------


def test_adaptation_prompt_contains_non_negotiable_rule():
    """Sentinel: the 'preserve local strengths' rule must not be silently removed."""
    prompt_path = (
        Path(__file__).resolve().parent.parent / "references" / "adaptation_prompt.md"
    )
    text = prompt_path.read_text(encoding="utf-8")
    assert "Preserve local strengths" in text
    assert "additive" in text.lower()


# --------------------------------------------------------------------------- #
# Line-ending-insensitive hashing
#
# apply.py writes every asset with newline="\n" and records the sha of those LF
# bytes. Git then checks the same file out with CRLF on a typical Windows
# consumer, so hashing raw bytes in discover could never agree with what was
# recorded — and a lock entry that never matches silently reduces the 3-way
# reconcile to a blind 2-way diff.
#
# Measured across four real consumer repos before the fix: 277 of 527 tracked
# assets matched ONLY after CRLF normalization. The one repo unaffected was the
# one with a repo-wide `.gitattributes eol=lf`, which confirms the mechanism
# from the other direction.
# --------------------------------------------------------------------------- #


def test_crlf_and_lf_of_the_same_content_hash_identically():
    discover_mod = _load("discover")
    lf = b"line one\nline two\n"
    crlf = b"line one\r\nline two\r\n"
    assert discover_mod._hash_bytes(lf) == discover_mod._hash_bytes(crlf)


def test_genuinely_different_content_still_hashes_differently():
    """Non-vacuity: normalizing must not collapse real differences."""
    discover_mod = _load("discover")
    assert discover_mod._hash_bytes(b"a\n") != discover_mod._hash_bytes(b"b\n")
    # A lone CR is not a line ending pair and must not be normalized away.
    assert discover_mod._hash_bytes(b"a\rb") != discover_mod._hash_bytes(b"ab")


def test_a_local_copy_differing_only_in_line_endings_is_not_divergent(synthetic_repos):
    """The end-to-end shape: same content, CRLF locally, LF at source. Before
    the fix this surfaced as a divergence needing adaptation on every sync."""
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/a.md": "alpha\nbeta\n"},
        "dst": {".claude/plugins/cla/skills/a.md": "alpha\r\nbeta\r\n"},
    })
    result = _load("discover").discover(repos[0], repos[1])
    assert result.files == [], (
        "a file identical except for line endings was reported as diverging"
    )


def test_apply_records_a_line_ending_insensitive_hash(tmp_path):
    """The other side of the contract: what apply writes into the lock must be
    comparable with what discover computes, or they drift apart again."""
    apply_mod = _load("apply")
    discover_mod = _load("discover")
    repo = tmp_path / "repo"
    (repo / ".claude" / "plugins" / "cla").mkdir(parents=True)
    apply_mod._update_lock(repo, [("x.md", b"alpha\r\nbeta\r\n")], "src")
    lock = json.loads(
        (repo / ".claude" / "plugins" / "cla" / ".cla-sync-lock.json").read_text(encoding="utf-8")
    )
    recorded = lock["x.md"]["last_synced_sha256"]
    assert recorded == discover_mod._hash_bytes(b"alpha\nbeta\n")
    assert recorded == discover_mod._hash_bytes(b"alpha\r\nbeta\r\n")


# --------------------------------------------------------------------------- #
# SCAN_FILES — the repo-root launchers
#
# They were hand-carried for their whole life, and the cost arrived at once:
# claw.cmd shipped broken on Windows, three consuming repos each diagnosed and
# fixed it independently, and none of those fixes could flow anywhere. Two of
# the three still carry a bug the fourth had already fixed.
# --------------------------------------------------------------------------- #


def test_a_root_launcher_is_discovered(synthetic_repos):
    repos = synthetic_repos({
        "src": {"claw": "#!/usr/bin/env bash\nnew\n"},
        "dst": {"claw": "#!/usr/bin/env bash\nold\n"},
    })
    result = _load("discover").discover(repos[0], repos[1])
    assert [f.asset_path for f in result.files] == ["claw"]


def test_all_four_launchers_are_in_scope(synthetic_repos):
    discover_mod = _load("discover")
    repos = synthetic_repos({
        "src": {n: f"src {n}\n" for n in discover_mod.SCAN_FILES},
        "dst": {n: f"dst {n}\n" for n in discover_mod.SCAN_FILES},
    })
    found = {f.asset_path for f in discover_mod.discover(repos[0], repos[1]).files}
    assert found == set(discover_mod.SCAN_FILES)


def test_a_launcher_absent_locally_is_new_not_ignored(synthetic_repos):
    """A consuming repo with no `claw` at all: it must arrive, not be skipped."""
    repos = synthetic_repos({
        "src": {"claw": "#!/usr/bin/env bash\nx\n"},
        "dst": {".claude/plugins/cla/skills/a.md": "A\n"},
    })
    result = _load("discover").discover(repos[0], repos[1])
    claw = [f for f in result.files if f.asset_path == "claw"]
    assert len(claw) == 1 and claw[0].status == "new"
    assert claw[0].local_content is None


def test_an_unrelated_root_file_is_NOT_swept_in(synthetic_repos):
    """Only the named launchers. A root scan that took everything would drag in
    README, package.json and the consuming repo's own files."""
    repos = synthetic_repos({
        "src": {"claw": "x\n", "README.md": "src readme\n", "package.json": "{}\n"},
        "dst": {"claw": "y\n", "README.md": "dst readme\n", "package.json": "{\"a\":1}\n"},
    })
    found = {f.asset_path for f in _load("discover").discover(repos[0], repos[1]).files}
    assert found == {"claw"}


def test_the_category_counts_sum_to_the_total(synthetic_repos):
    """Root files have no directory prefix, so every existing category missed
    them and the summary silently stopped adding up."""
    discover_mod = _load("discover")
    repos = synthetic_repos({
        "src": {"claw": "a\n", ".claude/plugins/cla/skills/s.md": "s\n",
                ".claude/plugins/cla/hooks/h.py": "h\n"},
        "dst": {"claw": "b\n", ".claude/plugins/cla/skills/s.md": "t\n",
                ".claude/plugins/cla/hooks/h.py": "i\n"},
    })
    counts = discover_mod.summary_counts(discover_mod.discover(repos[0], repos[1]))
    per_category = (counts["skills"] + counts["agents"] + counts["hooks"]
                    + counts["output_styles"] + counts["launchers"])
    assert per_category == counts["total"]
    assert counts["launchers"] == 1


def test_a_launcher_deleted_in_source_is_surfaced(synthetic_repos):
    """`_detect_deletions` reuses the same walker, so this comes for free — but
    only if the root files are actually walked on the LOCAL side too."""
    repos = synthetic_repos({
        "src": {".claude/plugins/cla/skills/a.md": "A\n"},
        "dst": {".claude/plugins/cla/skills/a.md": "A\n", "claw": "local\n"},
    })
    _seed_lock(repos[1], {"claw": {"last_synced_sha256": "deadbeef", "source": "src"}})
    result = _load("discover").discover(repos[0], repos[1])
    assert [d.asset_path for d in result.deletions] == ["claw"]
