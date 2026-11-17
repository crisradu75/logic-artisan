# mnemo

The source of Mnemo's shared logic: the skills, conventions, check script and hooks that every Mnemo domain repo uses.

Mnemo is a personal "AI recall" second brain:
- **Front end:** the Code tab of the Claude apps, meaning Claude Code cloud sessions on iPhone, web and desktop.
- **Storage:** private Markdown repos, one per domain (work, investments, games), never mixed.
- **This repo:** the single source of the logic. Each domain repo carries a copy of it (architecture decision Q11–Q14).

The design and its sources are in the `crisradu75/research` repo:
- `mnemo/build-guide/build-guide-report.md`
- `cla.io/decisions/2026-11-15-mnemo-design.md`

The decisions for this repo are in `cla.io/decisions/`.

## Layout

There is no plugin packaging, and nothing installs Mnemo as a plugin (architecture Q14).

| Path | What |
|---|---|
| `mnemo-plugin/` | A folder at this repo's root. The name is the owner's choice; it is not a Claude Code plugin, and nothing installs it as one. It holds one shared set of files, identical for every domain: the check script `mnemo/scripts/mnemo_check.py`, the base schema `mnemo/conventions/base-schema.yml`, the hook scripts in `mnemo/hooks/`, and the four domain skills in `skills/` (`mnemo-capture`, `mnemo-recall`, `mnemo-review`, `mnemo-improve`). `mnemo-setup` copies it into each domain repo's `.claude/`. Its folder shape matches the destination path: `mnemo-plugin/skills/mnemo-*` → `.claude/skills/mnemo-*`, `mnemo-plugin/mnemo/` → `.claude/mnemo/`. `mnemo-plugin/skills/README.md` is the one file that is not copied |
| `mnemo-plugin/mnemo/hooks/` | The hook scripts, copied to a domain's `.claude/mnemo/hooks/`: `probe-python.sh`, which finds a real Python 3.8+ (a renamed copy of cla v2.3.0's probe), and `guard_git.py`, the commit and push guard |
| `.claude/skills/mnemo-setup/` | The setup skill, with its copy tool `scripts/mnemo_copy.py` (`apply`, `verify`). It runs only in a session on this repo and is never copied. Its `templates/` generate the per-domain files: `CLAUDE.md`, `AGENTS.md`, `mnemo.schema.yml`, the hook wiring in `.claude/settings.json`, and more |
| `.claude/skills/mnemo-setup/templates/settings-hooks.json.tmpl` | The hook wiring, added early by `add-guard-hooks`: only a `hooks` key, which `mnemo-setup` merges into each domain's `.claude/settings.json` |
| `VERSION` | The release version, one semver line, the same as the tag `v<VERSION>` |
| `tests/` | `unittest` tests, standard library only. Never copied |
| `evals/` | The trigger-eval runner `run_triggers.py` and the prompt set `triggers.jsonl`. It calls the model, so it is not part of the tests. Never copied |
| `openspec/` | Change proposals and specs |
| `cla.io/` | CLA workflow files and the decision records |

## Tests

Run the tests from the repo root with Python 3 (no dependencies):

```
python -m unittest discover -s tests
```

`python -m unittest tests.test_shipped_layout` runs only the shipped-layout test, which checks that `mnemo-plugin/` holds only the files the copy map names. The trigger evals run on the owner's logged-in account with `python evals/run_triggers.py`; each run costs model calls.

## Hooks

A domain repo's `.claude/settings.json` wires two hooks to the copy in `.claude/mnemo/`. Each first checks that the repo it acts on has `mnemo.schema.yml` at its top level, so a non-Mnemo repo is left alone.

- **Commit and push guard** (PreToolUse on Bash and PowerShell): before Claude runs a `git commit` or `git push` aimed at a Mnemo repo, it runs every check of `mnemo_check.py` on the staged and changed files, or on the commits the push sends, and blocks the command when a check reports a problem or cannot run. It fails closed: a command it cannot follow is blocked with a request to rewrite it as a plain git command. A problem in a note gets "fix and retry once, then `inbox/`"; anything else gets "do not use `inbox/`".
- **End-of-turn save** (Stop): when the working tree has changes or a commit waits to be pushed, it runs `mnemo_check.py save`, which checks, commits and pushes. A failed save shows a notice and never blocks the end of the turn; a commit that could not be pushed gets its own notice.

The hooks need a real Python 3.8+. **A missing Python blocks every commit and push in a Mnemo repo** (the end-of-turn save then only shows a notice). The probe tries `python3`, `py`, `python` and the usual install paths, and skips stand-ins such as the Windows Store stub. To name the interpreter, set `MNEMO_PYTHON` to its path or name; a value that is not a working Python 3.8+ is treated as no Python, so a typo shows. The probe caches its answer in `~/.cache/mnemo/pyexe`; `MNEMO_PROBE_NO_CACHE=1` turns the cache off.

## Install into a domain repo

Mnemo is installed only at repo level, never at user or account level, and never as a plugin. Cloud sessions don't install plugins that a repo turns on. They do load what is committed in the repo: skills in `.claude/skills/`, and hooks and permissions in `.claude/settings.json`. So each domain repo carries:

- **A copy of the shared files from `mnemo-plugin/`:**
  - `.claude/skills/mnemo-capture/`, `mnemo-recall/`, `mnemo-review/` and `mnemo-improve/`
  - `.claude/mnemo/`: the check script, the base schema, the Python probe and the hook scripts
- **Per-domain files that setup generates:**
  - `CLAUDE.md`, `mnemo.schema.yml` and the note folders
  - the Mnemo hook entries in `.claude/settings.json`
  - `.claude/mnemo/stamp.json`: the tag the copy came from, a hash per copied file, and the repo that `mnemo-improve` files issues on

To install or refresh, open a Claude Code session on **this** repo and run `/mnemo-setup`:
- **Cloud:** attach the domain repo to the same session.
- **Laptop:** give setup the domain repo's clone path.

Setup copies `mnemo-plugin/` from a named release tag:
- **Empty domain repo:** it installs the copy and the domain files, then commits and pushes.
- **Domain that already has a copy:** a refresh goes on a branch with a pull request in the domain repo. The pull request shows the old and the new version.

Never edit a copied file by hand. Setup reports any copied file that differs from its stamp, and asks before replacing it.

This repo holds no notes, so a setup session never mixes domains.

## Releases

- **What a release is:** a tag `v<VERSION>` on this repo, cut from the Mac or GitHub's web page. Cloud sessions can't create tags.
- **Versions:** every pull request that changes `mnemo-plugin/` or `mnemo-setup` bumps `VERSION`.
- **Tags:** a published tag is never moved.
- **Reaching a domain:** a merge or a tag alone doesn't reach any domain. A domain gets a release when the owner merges that domain's refresh pull request from `mnemo-setup`.
- **Access:** these are private repos, so the Claude GitHub App needs access to this repo and to each domain repo.
