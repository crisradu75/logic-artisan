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

- **Choice:** JSON `{"version": 1, "root": ..., "files": {path: sha256 or null}, "overlays": [...]}`,
  written to the session scratchpad or a gitignored folder; `--out` inside the repo and not ignored,
  or at a protected path, exits 2.
- **Why:** writing it into the repo would itself be a change for the run to explain.
- **Rejected, a fixed path under `cla.io/`:** it would show in the user's `git status`.

## What a yes can cover

- **Choice:** `--approved` covers a change or deletion of a `*.local.md` file, the terminology file or
  an existing overlay, and the creation of a `*.local.md` file (item 12). It never covers an instruction
  file, an existing `notes.md`, a new overlay or a new terminology file.
- **Why:** the skill never asks to touch those, so an approval for one can only be a mistake.
- **Rejected, any path approvable:** it would let a wrong `--approved` hide a broken promise.
