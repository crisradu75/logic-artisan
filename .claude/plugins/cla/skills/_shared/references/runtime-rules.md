# runtime-rules — thin-orchestrator runtime disciplines

The standing runtime disciplines that keep `/cla:spec-to-pr`'s per-run context small. Pointed at from the hoisted skill-level rules and every phase that handles bulk raw material. These are the NEW thin-orchestrator disciplines only — the separate correctness-gating sections in `SKILL.md` ("Bash-style discipline", "Continue-on-everything escalation", "Development-only boundary") are NOT part of this file and stay inline.

The governing spec requirement is `cla-plugin`'s **Skill token-efficiency disciplines** (thin-orchestrator runtime execution). The total cost of a run ≈ Σ over turns of the orchestrator's context size, so every raw file/diff/grep dump the orchestrator pulls inline is re-billed on every subsequent turn. Keep raw material OUT of the parent context.

## 1. Delegate raw-material handling — only conclusions return

When a step needs to process bulk raw material (a large diff, a wide file set, verbose command output, a big claim-verification sweep), hand the raw-material handling to a sub-agent and let ONLY its conclusion return to the parent context. The parent never needs the raw bytes — it needs the verdict/finding/fact.

- **Review large-change mechanical verification →** `fact-gatherer` (see the Review section's default).
- **A large fix-set of mechanical edits →** the existing generic coding `Agent(model: sonnet)` (see the Revise fix-delegate default). Delegation covers edit APPLICATION only; the orchestrator keeps its own post-fix re-verification (INT-CAP/INT-SYC/SIR-TEST).
- **Doc-staleness sweeps →** `doc-sweeper`, which returns a hit list, not the files.

## 2. I/O hygiene (standing — applies throughout, not only at a trigger)

- **Read slices, not whole files.** Use `Read` with `offset`/`limit`, or `Grep` to locate the section first, when you only need part of a file. Reading a 600-line file to check one rule wastes ~20k tokens per turn thereafter.
- **`tail`/`head` large command output.** Pipe verbose command output (test logs, `git log`, long `--json`) through `head`/`tail` (or `wc -l` first) rather than letting the full dump land in context.
- **Scratch-file-then-delegate large intermediate material.** When a step produces a large intermediate artifact another step consumes, write it to `temp/` and hand the path to a delegate, rather than carrying the whole artifact inline. (The happy path needs no scratch file — see the "Per-run scratch directory" note in `SKILL.md`.)

## 3. Batch independent tool calls into one message

Independent reads/greps/checks with no data dependency between them MUST go in a single message with multiple tool calls, not one-at-a-time across turns. This is the same rule the Review checklist's "Maximize parallelism in pre-gathering" already states — it is a general orchestrator discipline, not Review-specific.

## 4. Prefer terse, schema'd agent output over prose

Dispatched agents return a structured (schema'd) object — a findings list, a pass/fail table — not a prose essay the parent must re-parse. The Revise round-1 Workflow already pins `FINDINGS_SCHEMA`; Review agents and `doc-sweeper` follow the same shape (see the Review section). A schema'd return is smaller, machine-mergeable, and keeps the parent's triage step cheap.
