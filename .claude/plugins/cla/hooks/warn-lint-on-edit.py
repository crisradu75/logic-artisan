#!/usr/bin/env python3
"""PostToolUse hook — after an Edit/Write to a lintable source file, run oxlint
on JUST that one file and feed any violations back to Claude as non-blocking
context.

Rationale ("Post-Tool Amnesia"): without an immediate lint signal at edit time,
a syntax/lint error introduced by a Write only surfaces much later — at
spec-to-pr's Review phase or a manual `pnpm run lint` — after slop has compounded
across several edits. Running the linter on the single changed file right after
it lands tightens the edit->feedback loop so the model self-corrects on the very
next turn instead of accumulating errors.

NON-BLOCKING BY DESIGN — always exits 0, and lives in the `warn-*` family, not
`block-*`. The harness reserves `block-*` for irreversible/policy violations
(push-to-main, rm -rf, worktree escape). A lint error is none of those: it's
local, recoverable, self-correcting, and code legitimately passes through
lint-dirty intermediate states during a multi-file change (an import used two
edits later, a not-yet-wired function). Hard-blocking those would wedge the agent
for no safety gain — the real "nothing broken ships" gate is spec-to-pr's Review
phase running the FULL workspace lint, at the right altitude.

Cross-platform (Windows + macOS): oxlint is a per-package devDependency with no
root-level binary, so this hook (1) walks up from the edited file to its owning
package's node_modules/.bin, (2) picks a platform shim (oxlint.cmd etc. on
Windows, oxlint on POSIX — see _binary_candidates for the full ordered set) by
ABSOLUTE path — a *relative* .cmd path fails under cmd.exe with "The system
cannot find the path specified" — and (3) runs it with cwd set to that package so
the shared root .oxlintrc.json resolves. Any failure to locate or run oxlint (no
package, no binary, timeout, non-JSON or otherwise malformed output) exits 0
silently: a warning hook must never disrupt the workflow.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Extensions we run oxlint on; edits to .json/.md/.css/etc. are skipped so the
# hook stays silent on non-lintable files rather than emitting empty runs.
LINTABLE_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")

# Cap how many diagnostics we echo back, so a file that lights up the linter
# doesn't flood the parent context with a wall of findings.
_MAX_DIAGS = 10

# Must stay strictly under the `timeout` hooks.json gives this handler
# (_dispatch_lib.HANDLER_TIMEOUT_SECONDS), with room left for interpreter
# startup and the parent-directory walk that finds the oxlint binary. This was
# 20s — longer than the whole handler's budget — so a slow lint could not report at all:
# the handler was killed first, and a killed hook produces nothing.
#
# Deliberately tight rather than generous. Linting ONE file is normally well
# under a second; anything approaching this bound is pathological, and dropping
# an advisory warning is much cheaper than stalling every single edit in the
# session waiting for it.
_LINT_TIMEOUT_SECONDS = 6


def _binary_candidates() -> tuple[str, ...]:
    """node_modules/.bin shim names to try, most-specific first, per platform."""
    if os.name == "nt":
        return ("oxlint.cmd", "oxlint.CMD", "oxlint.exe", "oxlint")
    return ("oxlint",)


def _find_oxlint(file_path: Path, ceiling: Path) -> tuple[Path, Path] | None:
    """Walk up from the edited file toward `ceiling`, returning
    (package_dir, oxlint_bin_abspath) for the NEAREST enclosing package that has
    an oxlint binary in node_modules/.bin — or None if none is found.
    """
    candidates = _binary_candidates()
    current = file_path.parent
    while True:
        bin_dir = current / "node_modules" / ".bin"
        for name in candidates:
            candidate = bin_dir / name
            if candidate.is_file():
                return current, candidate
        if current == ceiling or current == current.parent:
            return None
        current = current.parent


def _run_oxlint(oxlint_bin: Path, package_dir: Path, file_path: Path) -> list[dict] | None:
    """Run oxlint (JSON reporter) on the single file, cwd=package_dir. Returns the
    parsed `diagnostics` list, or None on any failure (fail-open). The file is
    passed relative to package_dir so oxlint's own path display is clean; the
    binary path is absolute because a relative .cmd cannot be launched on Windows.
    """
    try:
        rel = file_path.relative_to(package_dir).as_posix()
    except ValueError:
        rel = str(file_path)
    try:
        result = subprocess.run(
            [str(oxlint_bin), "-f", "json", rel],
            cwd=str(package_dir),
            capture_output=True,
            text=True,
            timeout=_LINT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    # oxlint's exit code is unreliable as a signal (it returns non-zero for "no
    # files found" too), so we key off the parsed diagnostics, not returncode.
    try:
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return None
    # oxlint's top-level payload should be an object; tolerate version/mode drift
    # that hands back a bare array or scalar rather than letting `.get` raise and
    # breach this hook's always-exit-0 contract.
    if not isinstance(payload, dict):
        return None
    diagnostics = payload.get("diagnostics")
    return diagnostics if isinstance(diagnostics, list) else None


def _format_diagnostics(diagnostics: list[dict], rel: str) -> str:
    """Render diagnostics into a compact, model-readable warning block."""
    lines = []
    for diag in diagnostics[:_MAX_DIAGS]:
        if not isinstance(diag, dict):
            continue
        severity = diag.get("severity", "error")
        message = str(diag.get("message", "")).replace("\n", " ").strip()
        labels = diag.get("labels") or []
        span = labels[0].get("span") if labels and isinstance(labels[0], dict) else None
        if not isinstance(span, dict):
            span = {}
        line, col = span.get("line"), span.get("column")
        # Build the location from whatever oxlint supplied — never emit a literal
        # "None" (a line with no column must read as `L5`, not `L5:CNone`).
        if line is not None and col is not None:
            where = f"L{line}:C{col} "
        elif line is not None:
            where = f"L{line} "
        else:
            where = ""
        lines.append(f"  [{severity}] {where}{message}")
    extra = len(diagnostics) - _MAX_DIAGS
    if extra > 0:
        lines.append(f"  …and {extra} more")
    return (
        f"oxlint found {len(diagnostics)} issue(s) in {rel} you just edited. Fix "
        f"them before moving on so they don't compound (this is advisory, not a "
        f"block — the full workspace lint still runs at review):\n" + "\n".join(lines)
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0

    tool_input = payload.get("tool_input")
    raw_path = tool_input.get("file_path", "") if isinstance(tool_input, dict) else ""
    if not isinstance(raw_path, str) or not raw_path.endswith(LINTABLE_EXTS):
        return 0

    project_root = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())).resolve()
    file_path = Path(raw_path)
    if not file_path.is_absolute():
        file_path = (project_root / file_path).resolve()
    else:
        file_path = file_path.resolve()

    if not file_path.is_file():
        return 0

    found = _find_oxlint(file_path, project_root)
    if found is None:
        return 0
    package_dir, oxlint_bin = found

    diagnostics = _run_oxlint(oxlint_bin, package_dir, file_path)
    if not diagnostics:
        return 0

    try:
        rel = file_path.relative_to(project_root).as_posix()
    except ValueError:
        rel = file_path.name

    msg = _format_diagnostics(diagnostics, rel)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": msg,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
