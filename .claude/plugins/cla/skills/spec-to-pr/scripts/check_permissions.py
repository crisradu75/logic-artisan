"""Bootstrap and audit the project's .claude/settings.local.json against the
required-permissions.json bundled with this skill.

Modes:
  --check   (default) print missing patterns and exit non-zero if any missing
  --apply   add missing patterns to settings.local.json (additive-only,
            preserves every other top-level key); read-modify-write
  --audit   grep SKILL.md and scripts/ for invoked command shapes; confirm
            each is covered by a pattern in required-permissions.json
"""

# Spec: spec-to-pr-orchestration#bootstrap-permission-management-on-first-run

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    """Repo root via git (location-independent — works from the plugin, unlike a
    fixed `parents[N]` depth). Falls back to cwd if git is unavailable; tests
    monkeypatch REPO_ROOT directly."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return Path.cwd()


REPO_ROOT = _repo_root()
# The skill's bundled required-permissions*.json travels WITH the skill into the
# plugin, so resolve it skill-relative (scripts/ -> the skill dir), NOT via the
# repo root. SETTINGS_PATH below stays repo-root-relative (permissions are
# project-level state, not part of the plugin).
SKILL_DIR = Path(__file__).resolve().parents[1]
REQUIRED_PATH_DEFAULT = SKILL_DIR / "references" / "required-permissions.json"
REQUIRED_PATH_NARROW = SKILL_DIR / "references" / "required-permissions-narrow.json"
SETTINGS_PATH = REPO_ROOT / ".claude" / "settings.local.json"


def _load_required(narrow: bool = False) -> list[str]:
    path = REQUIRED_PATH_NARROW if narrow else REQUIRED_PATH_DEFAULT
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)["permissions"]["allow"]
    except FileNotFoundError:
        raise SystemExit(f"required-permissions reference file is missing: {path} "
                         f"(skill bundle is incomplete; reinstall or restore from git)")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"required-permissions reference file is not valid JSON ({path}): "
                         f"{exc.msg} at line {exc.lineno}")
    except KeyError as exc:
        raise SystemExit(f"required-permissions reference file missing expected key {exc} "
                         f"({path}); expected shape: {{'permissions': {{'allow': [...]}}}}")


def _load_settings() -> dict:
    if not SETTINGS_PATH.is_file():
        return {"permissions": {"allow": []}}
    try:
        with SETTINGS_PATH.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"settings.local.json is not valid JSON ({SETTINGS_PATH}): "
                         f"{exc.msg} at line {exc.lineno}")


def _present_patterns(settings: dict) -> set[str]:
    perms = settings.get("permissions") or {}  # treat null/missing as empty
    if not isinstance(perms, dict):
        return set()
    allow = perms.get("allow") or []
    if not isinstance(allow, list):
        return set()
    return set(allow)


def _diff(required: list[str], present: set[str]) -> list[str]:
    return [p for p in required if p not in present]


def _save_settings(settings: dict) -> None:
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with SETTINGS_PATH.open("w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
            f.write("\n")
    except OSError as exc:
        raise SystemExit(f"failed to write {SETTINGS_PATH}: {exc.strerror or exc} "
                         f"(check file permissions, disk space, and that the file is not "
                         f"locked by another process)")


def cmd_check(narrow: bool = False) -> int:
    required = _load_required(narrow=narrow)
    settings = _load_settings()
    present = _present_patterns(settings)
    missing = _diff(required, present)
    if not missing:
        print("ok: all required patterns present")
        return 0
    print("missing patterns:")
    for p in missing:
        print(f"  {p}")
    return 1


def cmd_apply(narrow: bool = False, replace: bool = False) -> int:
    required = _load_required(narrow=narrow)
    settings = _load_settings()
    present = _present_patterns(settings)

    # When tightening to the narrow set, refuse silent no-ops: if any wildcard
    # patterns from the default set are already present, --apply --narrow alone
    # would just union them with the narrow set, leaving the broader patterns
    # in place — the user thinks they tightened, but didn't. Either pass
    # --replace (set-difference removes the wildcards) or do a manual edit.
    if narrow:
        default_patterns = set(_load_required(narrow=False))
        broader_present = sorted(default_patterns & present)
        if broader_present and not replace:
            print("refusing: wildcard patterns from required-permissions.json are already present.",
                  file=sys.stderr)
            print("Adding the narrow set without removing them would leave both in place,", file=sys.stderr)
            print("so the apparent tightening would silently no-op. Re-run with --replace", file=sys.stderr)
            print("to drop the wildcard patterns first, or remove them manually.", file=sys.stderr)
            print("", file=sys.stderr)
            print("wildcard patterns currently in settings.local.json:", file=sys.stderr)
            for p in broader_present:
                print(f"  - {p}", file=sys.stderr)
            return 2

    missing = _diff(required, present)
    if not missing and not (narrow and replace):
        print("ok: all required patterns already present, no changes")
        return 0
    # Normalize null/missing into a writable {permissions: {allow: [...]}} shape
    # while preserving every other top-level key.
    perms = settings.get("permissions")
    if not isinstance(perms, dict):
        perms = {}
        settings["permissions"] = perms
    allow = perms.get("allow")
    if not isinstance(allow, list):
        allow = []

    if narrow and replace:
        # Set-difference: remove every wildcard-default pattern, then union the narrow set.
        default_patterns = set(_load_required(narrow=False))
        new_allow = (set(allow) - default_patterns) | set(required)
        removed = sorted(set(allow) & default_patterns)
        perms["allow"] = sorted(new_allow)
        _save_settings(settings)
        print(f"replaced wildcard set with narrow set in {SETTINGS_PATH}:")
        for p in removed:
            print(f"  - {p}")
        for p in missing:
            print(f"  + {p}")
        return 0

    perms["allow"] = sorted(set(allow) | set(required))
    _save_settings(settings)
    print(f"added {len(missing)} pattern(s) to {SETTINGS_PATH}:")
    for p in missing:
        print(f"  + {p}")
    return 0


def _scan_command_shapes() -> set[str]:
    """Scan SKILL.md and reference markdown for `Bash(...)` patterns. The
    .py-side scan was dropped — it greps for quoted bareword tool names but
    cannot see through `_run` indirection, so it produces over-inclusive,
    low-signal entries. The .md scan is precise: it picks up exactly the
    permission grammar the SKILL.md documents emitting."""
    shapes: set[str] = set()
    bash_pat = re.compile(r"Bash\(([^)]+)\)")
    for path in sorted(SKILL_DIR.rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        shapes.update(bash_pat.findall(text))
    return shapes


def _shape_covered(shape: str, patterns: list[str]) -> bool:
    head = shape.split()[0] if shape else ""
    for p in patterns:
        if not p.startswith("Bash("):
            continue
        body = p[5:-1].strip()
        if body == shape:
            return True
        if body.endswith("*"):
            prefix = body[:-1].strip()
            if shape == prefix or shape.startswith(prefix + " ") or head == prefix:
                return True
    return False


def cmd_audit(narrow: bool = False) -> int:
    required = _load_required(narrow=narrow)
    shapes = _scan_command_shapes()
    uncovered = [s for s in sorted(shapes) if not _shape_covered(s, required)]
    if not uncovered:
        print(f"ok: all {len(shapes)} discovered command shape(s) covered")
        return 0
    print("uncovered command shapes (no matching pattern in required-permissions.json):")
    for s in uncovered:
        print(f"  {s}")
    return 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="check_permissions")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", default=True)
    group.add_argument("--apply", action="store_true")
    group.add_argument("--audit", action="store_true")
    parser.add_argument("--narrow", action="store_true",
                        help="Use the per-subcommand narrow pattern set instead of the wildcard default.")
    parser.add_argument("--replace", action="store_true",
                        help="Used with --apply --narrow: remove any wildcard-default patterns "
                             "before adding the narrow set, so tightening actually takes effect.")
    args = parser.parse_args(argv)
    if args.audit:
        return cmd_audit(narrow=args.narrow)
    if args.apply:
        return cmd_apply(narrow=args.narrow, replace=args.replace)
    return cmd_check(narrow=args.narrow)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
