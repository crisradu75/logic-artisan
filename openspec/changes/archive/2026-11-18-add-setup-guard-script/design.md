# Design

Trigger: a new data model, the snapshot file the two steps share.

## Snapshot, not git

- **Choice:** `snapshot` hashes each protected file on disk at the start of the run; `verify` hashes
  them again and compares.
- **Why:** git compares with the last commit, not with the start of the run. It cannot tell whether
  the run touched a file the owner had already edited, it sees nothing in a gitignored
  `cla.io/fleet.local.md`, and it shows an overlay that was untracked before the run as `??` either way.
- **Rejected, `git diff` / `git status` on the paths:** false alarms on every dirty file and silence on
  every ignored one. Git is still used to find the top level, nested instruction files it can see and
  whether `--out` is ignored.

## Snapshot file

- **Choice:** JSON `{"version": 1, "root": ..., "created": <unix seconds>, "head": <commit or null>,
  "files": {path: sha256, a not-a-file marker, or null}}`, written to the session scratchpad, a
  gitignored folder or a `mktemp` file. The overlays present at the start are derived from `files`,
  so no second list can disagree with it. `--out` inside a git directory, inside the repo and not
  ignored, at a protected path, or at an existing file that is neither empty nor a snapshot exits 2;
  the write goes through a new `mkstemp` file in the same folder, so no file is ever overwritten.
- **Why:** writing it into the repo would itself be a change for the run to explain, and an `--out`
  that names a user's ignored file (`.env`) must not replace it.
- **Rejected, a fixed path under `cla.io/`:** it would show in the user's `git status`.

## Stale snapshots

- **Choice:** `verify` exits 2 when the snapshot is more than 24 h old or more than 5 min in the
  future, or when `HEAD` moved to a commit that does not descend from the recorded one.
- **Why:** a leftover snapshot from another run, or a checkout that rewrote files, would report
  changes the run never made, or hide ones it did. Exit 2 fails safe: never a pass.
- **Rejected, no age check:** an old snapshot at a reused path would be trusted.

## What a yes can cover

- **Choice:** `--approved` covers a change or deletion of a `*.local.md` file, the terminology file or
  an existing overlay, and the creation of a `*.local.md` file (item 12). It never covers an instruction
  file (any letter case at the root and in `.claude/`), a settings file (`.claude/settings*.json`,
  `.claude-plugin/plugin.json`, a non-goal of the skill), a rules file of the repo's own (the skill
  writes only `cla-economy.md` there, and item 13 writes only under `cla.io/` and the spec map path),
  an existing `notes.md`, a new overlay or a new terminology file.
- **Why:** the skill never asks to touch those, so an approval for one can only be a mistake.
- **Rejected, any path approvable:** it would let a wrong `--approved` hide a broken promise.
