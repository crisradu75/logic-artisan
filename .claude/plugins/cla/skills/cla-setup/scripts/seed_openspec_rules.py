#!/usr/bin/env python3
"""Seed or compare the OpenSpec `rules:` block for /cla:cla-setup, item 5.

    python3 seed_openspec_rules.py <repo-root>

Reads and writes only `<repo-root>/openspec/config.yaml` (or reads `config.yml`):

- `openspec/` exists and neither config file does: writes `config.yaml` with `RULES`
  and prints `openspec/config.yaml: created`.
- `openspec/` is absent: writes nothing and prints `RULES` for the user to add.
- A config exists: leaves it byte-identical and prints, under its artifact, each rule of
  `RULES` the file lacks (`+`) and each earlier wording in `RETIRED` it still carries
  (`-`), also when the file holds that wording inside one pair of quotes; or says the
  rules are current.

`RULES` and `RETIRED` live only here; the skill points at this file and a test checks `RULES`
against this repo's own `openspec/config.yaml`. Each list item that contains `: ` stays
double-quoted, or YAML reads it as a mapping and OpenSpec drops that artifact's rules.

Exit 0 on a report, 2 on bad arguments, 1 when the config could not be written or read
(the message says which, and nothing is reported as current). Output is UTF-8 with LF line
endings on every platform. Standard library only.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RULES = r"""rules:
  proposal:
    - Keep it to about 400 words. Point to the specs and design instead of restating them.
  design:
    - Write design.md only when a stock trigger applies (a cross-cutting change, a new dependency or data model, security, performance or migration complexity, or real ambiguity), and name the trigger.
    - "Keep it to about 800 words: for each decision, the choice, one line of why, and one line per rejected alternative. No history or transcripts."
    - Never restate the proposal or the specs.
  specs:
    - "Specify only outcomes a user or owner would recognise, and interfaces others depend on: a CLI flag, a file or ledger format a consumer reads, an API contract. Leave implementation choices to the implementer; put a detail a reviewer must agree on, such as a security parameter or a data model, in design.md. Internal steps are not spec material."
    - "Write each requirement, ADDED or MODIFIED, as one sentence of 500 characters or fewer in plain words, with at most 3 scenarios. No history, reasons, measurements, coined terms, file paths or code names, unless the name is the interface. A spec holds at most 8 requirements; when one is full, add a new capability rather than a ninth."
    - "One outcome per requirement: a supporting SHALL clause that defines the outcome is fine, but a separate outcome becomes its own requirement or a scenario. Never squeeze a clause out to fit the limit; split the requirement instead, and when the spec already holds 8, put the second outcome in a new capability."
    - "Money, security, personal data, honesty claims and accessibility are protected: a rewrite compresses their requirements and never drops them. A REMOVED entry paired with an ADDED rewrite of the same outcome is not a drop."
    - "The Purpose of a new spec is a `**Serves:**` line naming who or what the capability serves, plus one plain sentence, with no file paths; for example `**Serves:** maintainers who release the plugin.` This is advisory: only a checker note, and older specs keep their plain Purpose until someone edits it. A delta cannot change a Purpose, so edit an existing Purpose directly in the main spec after the change is archived."
    - "Name a configurable value by its config key as configured, never by a number; a default may appear in a scenario."
    - "A MODIFIED block keeps every live scenario. To cut a live requirement's scenarios or bring it within these limits, list it under REMOVED and add the rewrite under ADDED with a new heading. This overrides OpenSpec's instruction to keep an existing requirement whole."
    - "A change with no externally visible behaviour change (a refactor, tooling, docs, or a rule about how a skill file is worded) sets `skip_specs: true` in its .openspec.yaml and writes no spec delta. Never invent a requirement to satisfy validation."
    - "Fix each code and spec mismatch found while writing specs in the same change, with a regression test. File an issue only when the fix is blocked outside the repo, for example in an upstream tool."
    - Read existing specs cheaply first (`openspec list --specs`, then `openspec show <id> --type spec --json --no-scenarios`), and read in full only the specs this change touches.
  tasks:
    - "Give each requirement this change adds or modifies a test task whose test carries a `requirement: <spec> / <heading>` comment line above it, or a line `manual: <heading>: <reason>`. Scenarios are examples, not one test each."
    - "Cite headings, not line numbers. A `measured:` note gives the value; the command that produced it goes in the commit message."
    - "Keep each task to about 40 words, stating one behaviour with an acceptance criterion a test or a command can check, and no file path with a line number. An out-of-scope note per task is allowed."
    - "End tasks.md with one docs task, worded `docs and spec map: <files updated>, or none affected: <reason>` (both parts when it updates some listed docs and leaves others). Name the files from the repo's doc list (`cla.io/project-facts.md`, section Doc-sweep paths, spec map included once a repo has one); without a list, judge which docs a reader of this repo would open for what the change alters. Tick it only after those files are edited."
""".rstrip("\n")

# Earlier wordings of shipped rules: the only lines the update may remove.
RETIRED = r"""rules:
  proposal:
    - Keep it to one page. Point to the specs and design instead of restating them.
  design:
    - "Keep it to one page: for each decision, the choice, one line of why, and one line per rejected alternative. No history or transcripts."
  specs:
    - State one behaviour per ADDED requirement in 500 characters or fewer, and put the detail in scenarios.
    - "State behaviour only, in plain words: one behaviour per ADDED requirement in 500 characters or fewer, with the detail in scenarios. No history, reasons, measurements or coined terms."
    - "A change with no externally visible behaviour change (a refactor, tooling, docs) sets `skip_specs: true` in its .openspec.yaml and writes no spec delta. Never invent a requirement to satisfy validation."
    - "Keep every scenario heading unique within its spec, so `<spec> / <heading>` names exactly one scenario."
  tasks:
    - "Give each ADDED or MODIFIED scenario a test task, or a `manual: <reason>` note."
    - "Give each scenario this change adds, or whose text it changes, a test task or a `manual: <reason>` note. A scenario carried forward unchanged in a MODIFIED block needs neither."
    - "Give each scenario this change adds, or whose text it changes, a test task whose test carries a `scenario: <spec> / <heading>` comment line above it, or a line `manual: <heading>: <reason>`. A pure heading rename, or a scenario carried forward unchanged in a MODIFIED block, needs neither."
""".rstrip("\n")


def _out(text: str) -> None:
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.flush()


def _unquote(rule: str) -> str:
    """Drop one pair of double quotes, then one pair of single quotes, around a `- ` item."""
    for quote in ('"', "'"):
        if len(rule) >= 4 and rule.startswith(f"- {quote}") and rule.endswith(quote):
            rule = "- " + rule[3:-1]
    return rule


def _rule_lines(block: str, mark: str, want: bool, have: set[str], quoted: set[str]) -> list[str]:
    """`mark artifact: - rule` for each rule of `block` the file carries (want) or lacks (not want)."""
    found, key = [], ""
    for line in block.split("\n"):
        if re.fullmatch(r"  [a-z].*:", line):
            key = line[2:]
        elif line.startswith("    - "):
            rule = line[4:]
            has = rule in have or (want and _unquote(rule) in quoted)
            if has == want:
                found.append(f"{mark} {key} {rule}")
    return found


def _compare(old: Path) -> int:
    name = f"openspec/{old.name}"
    try:
        raw = old.read_bytes()
    except OSError as err:
        _out(f"{name}: exists (skipped), rules NOT compared: cannot read it ({err})\n")
        return 1
    # UTF-16 (a PowerShell redirect writes it) or any NUL byte decodes to text no rule matches, which
    # would list every rule as missing; say it cannot be compared instead.
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in raw:
        _out(f"{name}: exists (skipped), rules NOT compared: cannot read it (not UTF-8 text)\n")
        return 1
    # Carriage returns out, then each line trimmed: a CRLF file or a different indent compares equal.
    text = raw.replace(b"\r", b"").decode("utf-8-sig", errors="surrogateescape")
    have = {line.strip(" \t\v\f") for line in text.split("\n")}
    quoted = {_unquote(line) for line in have}
    diff = _rule_lines(RULES, "+", False, have, quoted) + _rule_lines(RETIRED, "-", True, have, quoted)
    if not diff:
        _out(f"{name}: exists (skipped), rules current\n")
    else:
        _out(f"{name}: exists (skipped), missing or outdated rules (+ add, - remove):\n" + "\n".join(diff) + "\n")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not argv[1]:
        sys.stderr.write("usage: seed_openspec_rules.py <repo-root>\n")
        return 2
    spec = Path(argv[1]) / "openspec"
    cfg, yml = spec / "config.yaml", spec / "config.yml"
    if spec.is_dir() and not cfg.exists() and not yml.exists():
        made = False
        try:
            # "x" refuses an existing file or a dangling symlink instead of writing through it.
            with open(cfg, "x", encoding="utf-8", newline="\n") as handle:
                made = True
                handle.write(f"schema: spec-driven\n\n{RULES}\n")
        except OSError as err:
            sys.stderr.write(f"{err}\n")
            # A write that failed after the file was created leaves a partial config, which the next
            # run would read as the repo's own. Remove only a file this run created.
            if made:
                try:
                    cfg.unlink(missing_ok=True)
                except OSError as unlink_err:
                    sys.stderr.write(f"a partial openspec/config.yaml may remain: {unlink_err}\n")
            _out("openspec/config.yaml: write FAILED; add this block by hand:\n" + RULES + "\n")
            return 1
        _out("openspec/config.yaml: created\n")
        return 0
    if not spec.is_dir():
        _out("openspec/config.yaml: not written, no openspec/ (run openspec init, then add this block):\n" + RULES + "\n")
        return 0
    return _compare(cfg if cfg.exists() else yml)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
