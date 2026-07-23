"""Discover the correctness-check invocations for a set of changed paths.

agentic-air is a pnpm workspace monorepo (apps/funnel-demo, apps/chat-server,
apps/operator, packages/engine, packages/media-schema, packages/design-system),
but the root `package.json`'s own `build`/`lint`/`test` scripts are themselves
`pnpm -r --if-present run <script>` — a workspace-wide fan-out. So reading just
the root `package.json` and emitting `npm run <script>` for whichever of
`build` (typecheck + build, the primary gate), `lint` (oxlint), `test` (vitest)
it defines already covers every app/package in one invocation each; there is no
need for this script to walk `apps/*`/`packages/*` individually. Discovering
scripts dynamically means it stays correct as the repo gains/loses a suite
without editing this file.

Returns empty when there is no root `package.json`, when the package defines
none of those scripts, or when the change touches nothing source-affecting
(e.g. an openspec-/docs-only change) — the skip-with-warning case.

The Playwright smokes (`apps/funnel-demo/test-app.mjs` etc.) need a running dev
server, so they are intentionally NOT emitted here — they're an optional/manual
check the Test phase mentions but does not gate on.

Output contract (default) is unchanged from the pytest-era version: a JSON list
of argv-style command lists, e.g. `[["npm","run","build"],["npm","run","lint"]]`.

With `--staged`, output is instead a JSON object partitioning the same commands
into a cheap fast-fail tier and the full correctness tier:
`{"smoke": [["npm","run","lint"]], "full": [["npm","run","build"],["npm","run","test"]]}`.
The caller runs `smoke` first and only pays for `full` once it passes — oxlint is
milliseconds; the `tsc -b`/`vite build` typecheck+bundle and the vitest suite are
not. `smoke` is a cheap pre-filter, NOT a correctness proof: a lint pass does not
guarantee the build typechecks, so `full` still runs in full. Whichever tier is
empty (e.g. no `lint` script → empty smoke) is just skipped by the caller.
"""

# Spec: spec-to-pr-orchestration#test-discovery-by-convention-with-override

from __future__ import annotations

import json
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

# Suffixes whose files feed the tsc typecheck / vite build / oxlint / vitest. A
# change touching only `.md` (docs, openspec proposals/specs) is not
# source-affecting.
_SOURCE_SUFFIXES = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".json", ".css", ".scss", ".html",
}

# The npm scripts that gate correctness, in run order: build (typecheck,
# primary gate), then lint, then the test suite. Only those actually present in
# package.json's `scripts` are emitted.
_CHECK_SCRIPTS: tuple[str, ...] = ("build", "lint", "test")

# The cheap fast-fail tier for `--staged`: the checks fast enough to run first as
# a pre-filter before paying for the slow correctness tier. oxlint is the only
# millisecond-scale check here; `build` (tsc + vite) and `test` (vitest) are the
# slow `full` tier. Membership is by script name, so the partition stays correct
# as the repo gains/loses a suite.
_SMOKE_SCRIPTS: frozenset[str] = frozenset({"lint"})


def _is_source_affecting(raw: str) -> bool:
    """True when a (repo-relative or absolute) changed path is something the
    build/lint/test would cover: anything under `src/`, or any file with a
    source/config suffix. Markdown and openspec artifacts are not."""
    p = Path(raw)
    parts = p.parts
    if "src" in parts:
        return True
    return p.suffix.lower() in _SOURCE_SUFFIXES


def _available_checks() -> list[list[str]]:
    """`npm run <script>` for each of _CHECK_SCRIPTS defined in the root
    package.json, in run order. Empty if package.json is unreadable or defines
    none of them."""
    try:
        pkg = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    scripts = pkg.get("scripts") if isinstance(pkg, dict) else None
    if not isinstance(scripts, dict):
        return []
    return [["npm", "run", name] for name in _CHECK_SCRIPTS if name in scripts]


def discover(paths: list[str]) -> list[list[str]]:
    if not (REPO_ROOT / "package.json").is_file():
        return []
    if not any(_is_source_affecting(raw) for raw in paths):
        return []
    return _available_checks()


def discover_staged(paths: list[str]) -> dict[str, list[list[str]]]:
    """Same discovery as `discover`, partitioned into a cheap `smoke` tier and
    the slow `full` tier by script name (`_SMOKE_SCRIPTS`). Each tier preserves
    the canonical run order from `_CHECK_SCRIPTS`. Both tiers are empty when
    `discover` would return nothing (no npm project / no scripts / docs-only
    change), so the caller's "run smoke then full" logic is a no-op there."""
    checks = discover(paths)
    smoke = [c for c in checks if c[-1] in _SMOKE_SCRIPTS]
    full = [c for c in checks if c[-1] not in _SMOKE_SCRIPTS]
    return {"smoke": smoke, "full": full}


def main(argv: list[str]) -> int:
    staged = False
    if argv and argv[0] == "--staged":
        staged = True
        argv = argv[1:]
    if not argv:
        print("usage: discover_tests.py [--staged] <path> [<path>...]", file=sys.stderr)
        return 2
    result: object = discover_staged(argv) if staged else discover(argv)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
