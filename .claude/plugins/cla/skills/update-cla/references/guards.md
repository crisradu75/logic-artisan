# guards — conformance guard, project-facts staleness guard, known limitations

## Running the plugin's whole test suite

Each skill *that ships tests* (and the `hooks/` dir) is its own isolated pytest scope with its own `pyproject.toml` — several ship a same-named `scripts/aggregate.py`/`scripts/log_run.py`, so they **cannot** share one pytest process (Python can't import two top-level modules of the same name), and a plain `pytest` from the plugin root fails collection by design. Run every scope at once — as one aggregated pass/fail with a proper exit code — via the stdlib runner at the plugin root, which runs `pytest` once per scope as a subprocess and forwards any extra args:

```
python3 .claude/plugins/cla/run_tests.py         # all scopes
python3 .claude/plugins/cla/run_tests.py -q      # args forwarded to each pytest
```

The per-scope invocations below (`pytest .claude/plugins/cla/skills/<name>/tests`) still work for running one scope in isolation.

## Conformance guard — no project tokens in synced core

**This guard no longer lives here.** It moved to `.claude/plugins/cla/conformance-checks/tests/test_no_project_tokens.py`, its own scope, because it enforces a rule about the WHOLE plugin and must outlive the sync tool. What follows describes it because this skill's sync is what makes the rule load-bearing; the guard's own docstring is the authority.

A pytest guard mechanically enforces the fact/procedure split that makes this skill's sync safe: a project-specific token must live behind an overlay (`project-context.md` / `*.local.md`), never baked into a synced-core `SKILL.md` or `references/**/*.md`, or the sync would carry it verbatim into every destination repo. The guard obeys the same split it enforces — a **generic checker** (portable procedure, synced to every repo) driven by a **per-repo token list** (a fact, never synced).

- **Token list overlay:** `cla.io/project-tokens.local.md` — per-repo data, kept with the rest of it and outside the synced core entirely, so `discover.py` never syncs it (each destination curates its own) and neither of the guard's scans can reach it. It's a plain markdown bullet list; the checker reads each `- `/`* ` bullet as one token (trailing ` # comment` and surrounding backticks stripped). **Curate it with distinctive compound repo tokens only** (package/app paths, product/tool names, fixed ports) — never generic words that legitimately appear in portable prose. Verify a candidate with a grep of the current synced core before adding it; the overlay's own comment block documents the deliberately-excluded candidates (e.g. `apps/`, `pnpm`) so an omission reads as intentional.
- **Scan scope:** every `SKILL.md` + `references/**/*.md` under `skills/**`, EXCLUDING overlay files (leaf `project-context.md` or `*.local.md`), non-markdown assets, the `tests/`/`scripts/` subtrees, and **each file's leading YAML frontmatter** (a skill's `description:` legitimately names the host repo so it triggers — metadata, not portable prose).
- **Failure output:** every violation on its own line — repo-relative path, matched token, 1-based line number, trimmed excerpt — surfaced all at once, not first-hit-only.
- **Absent token list = trivial pass** (a `pytest.skip`): a fresh destination that synced the guard but hasn't curated a list yet must not get a red CI. But a token file that is **present yet yields no tokens** (a list broken by a reformat) **fails** — silently skipping it would disable the safety check with no signal; to intentionally disable the guard, delete the file.

Run it with the rest of the suite: `pytest .claude/plugins/cla/conformance-checks/tests`.

## Project-facts staleness guard — no dead paths in the consolidated fact file or overlays

A sibling pytest guard (`conformance-checks/tests/test_project_facts_paths.py`, `cla-context-refresh`) mechanically checks
the OTHER half of the fact/procedure split's freshness problem: not "is a fact behind an overlay"
(the conformance guard above), but "does a path a fact NAMES still exist." It reads the repo-level
consolidated `cla.io/project-facts.md` (populated by `/cla:sync-context`) plus every per-skill
`cla.io/overlays/<skill>.md` overlay, extracts every token that looks like a repo-relative path
(conservatively — see its own docstring for the extraction rule), and fails when any such path no
longer resolves on disk (as a file or a directory). It resolves the **repo root** (not the plugin root
the conformance guard above walks to), since the paths it checks are repo-relative and
`cla.io/project-facts.md` lives at the repo root, outside the plugin tree. Like the conformance guard,
an absent `cla.io/project-facts.md` is a trivial pass (a fresh repo that hasn't run `/cla:sync-context`
yet). It is a **path-existence backstop only** — it does not validate the non-path mechanical facts
(commands, ports, member counts) `/cla:sync-context` produces, nor does it detect a fact duplicated
between the consolidated file and an overlay; both stay the refresh skill's job. Run it with the rest of
the suite: `pytest .claude/plugins/cla/conformance-checks/tests`.

## Known limitations

- **3-way classification is a label, not an auto-merge.** Since `cla-sync-provenance`, a per-repo `.cla-sync-lock.json` supplies the common ancestor for a real 3-way classification (`adapted` / `source-advanced` / `local-advanced` / `both-diverged`), falling back to today's 2-way `divergent` when no lock entry exists for an asset — that's a *whole-lockfile or whole-entry* absence: never synced, a missing/unreadable lockfile, JSON that fails to parse, a non-dict top level, or (as of this fix) a per-asset entry whose value isn't itself a dict. That fallback is narrower than "any corruption": a lock entry that exists and parses as a dict, but whose `last_synced_sha256` simply doesn't match either side, is not corruption at all — it classifies normally via the real 3-way comparison (most often `both-diverged`). But the classification only *labels* each divergence to guide Phase 2 — it never produces merged content itself; "preserve local strengths" still relies on the adapting Claude's judgment for the actual rewrite. Practical workaround: read the per-file `change_summary` lines before running `apply`.
- **Single source per run.** No multi-source fan-in. If you want to pull from two different repos, run twice with different source repos.
- **No reverse propagation of CONTENT.** This skill pulls *to* the local repo only; no run ever writes into the source repo. What it does propagate backwards is **prose**: Phase 4 records a local improvement that belongs in the portable core as a proposal in `cla-upstream.md` at the local repo root (see `references/upstream-proposals.md`), and the source repo collects from those files by hand when it chooses to. That is a pointer, not a patch — actually moving the code still means running the skill in the source repo with this repo as the source, or porting the change by hand. The gap this closes is discovery: before it, a defect found during a sync was known only to the session that found it, so the same one was diagnosed independently in several repos.
- **Deletions are surfaced, never auto-applied.** A lock-tracked local asset absent from source appears as a `deleted-in-source` record in `divergences.json`'s `deletions` array; `apply.py` has no delete path at all, by design — acting on a deletion is always a manual, deliberate step outside this skill's apply flow.
