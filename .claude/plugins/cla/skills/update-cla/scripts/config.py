"""Config layer for update-cla.

The config file at `~/.claude/sync-config.json` is OPTIONAL. Its only purpose
is short-name resolution for the `--source <repo>` arg: the user can pass
`--source claude-plugins` instead of an absolute path.

Schema (preferred — dict):

    {"repos": {"claude-plugins": "~/Code/claude-plugins", "legal-docs": "~/Code/legal-docs"}}

Legacy schema (list) is also accepted:

    {"repos": ["~/Code/claude-plugins", "~/Code/legal-docs"]}

When the list form is loaded, short names are derived from basenames.

On first run (no config file), the file is created automatically, pre-populated
via `auto_discover` under CLAUDE_SYNC_ROOT (default ~/OneDrive/Documents/Code/).
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


DEFAULT_CONFIG_PATH = Path.home() / ".claude" / "sync-config.json"
# Author-personal default layout for the cross-repo sync feature. This is a
# fallback ONLY -- the root is overridable via the CLAUDE_SYNC_ROOT env var
# (see get_root() below). On any machine without a `~/OneDrive/Documents/
# Code` folder, set CLAUDE_SYNC_ROOT rather than relying on this default.
DEFAULT_ROOT = Path.home() / "OneDrive" / "Documents" / "Code"


class ConfigError(Exception):
    """Raised when the config is corrupted and a config lookup is attempted."""


@dataclass
class SyncConfig:
    repos: dict[str, Path] = field(default_factory=dict)
    config_path: Path = DEFAULT_CONFIG_PATH
    root: Path = DEFAULT_ROOT
    first_run: bool = False
    corrupted: bool = False


def get_config_path() -> Path:
    override = os.environ.get("CLAUDE_SYNC_CONFIG_PATH")
    if override:
        return Path(override).expanduser()
    return DEFAULT_CONFIG_PATH


def get_root() -> Path:
    override = os.environ.get("CLAUDE_SYNC_ROOT")
    if override:
        return Path(override).expanduser()
    return DEFAULT_ROOT


def auto_discover(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        (child for child in root.iterdir() if child.is_dir() and (child / ".claude").is_dir()),
        key=lambda p: p.name,
    )


def _normalize_repos(raw) -> dict[str, Path]:
    if isinstance(raw, dict):
        return {name: Path(p).expanduser() for name, p in raw.items()}
    if isinstance(raw, list):
        out: dict[str, Path] = {}
        for entry in raw:
            p = Path(str(entry)).expanduser()
            out[p.name] = p
        return out
    return {}


def load_or_init_config(config_path: Path, root: Path) -> tuple[dict, bool, bool]:
    """Return (config_dict, first_run, corrupted)."""
    if config_path.exists():
        try:
            content = json.loads(config_path.read_text(encoding="utf-8"))
            if not isinstance(content, dict):
                raise ValueError("config root must be an object")
            return content, False, False
        except (json.JSONDecodeError, ValueError) as exc:
            print(
                f"warning: {config_path} is corrupted ({exc}); "
                "short-name resolution disabled — pass absolute paths instead",
                file=sys.stderr,
            )
            return {}, False, True

    discovered = auto_discover(root)
    initial = {"repos": {p.name: str(p) for p in discovered}}
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(initial, indent=2) + "\n", encoding="utf-8")
    print(
        f"update-cla: pre-populated config at {config_path} "
        f"with {len(discovered)} discovered repo(s); edit to use custom short names",
        file=sys.stderr,
    )
    return initial, True, False


def resolve(config_path: Optional[Path] = None, root: Optional[Path] = None) -> SyncConfig:
    cfg_path = config_path or get_config_path()
    cfg_root = root or get_root()
    cfg, first_run, corrupted = load_or_init_config(cfg_path, cfg_root)
    repos = _normalize_repos(cfg.get("repos"))
    return SyncConfig(
        repos=repos,
        config_path=cfg_path,
        root=cfg_root,
        first_run=first_run,
        corrupted=corrupted,
    )


def resolve_repo_arg(arg: str, config: SyncConfig) -> Path:
    """Map a `--source` argument to an absolute path.

    Order:
    1. Short name match in `config.repos` (if any).
    2. Filesystem path: absolute, `~`-prefixed, or relative to CWD.

    When the config is corrupted, short-name resolution is unavailable; raises
    ConfigError if the arg doesn't look like a path (no path separator, no
    matching directory in CWD).
    """
    if arg in config.repos:
        return config.repos[arg].resolve()

    if config.corrupted and "/" not in arg and "\\" not in arg and "~" not in arg:
        if not Path(arg).expanduser().exists():
            raise ConfigError(
                f"config is corrupted; short-name {arg!r} cannot be resolved. "
                f"Pass an absolute path or fix {config.config_path}."
            )

    p = Path(arg).expanduser()
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    else:
        p = p.resolve()
    return p
