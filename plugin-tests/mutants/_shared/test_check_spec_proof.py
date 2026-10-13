"""Mutation batch for test_check_spec_proof.py.

`check_spec_proof.py` is a checker a consuming repo trusts to say "every changed
requirement has proof". A checker that quietly stopped looking passes every repo,
so each mutant disables one rule or one return path:

  * the facts line (strict match, loose match, repeated line);
  * what counts as a unit (ADDED/MODIFIED sections only, scenarios inside their
    requirement's body, headings inside fences);
  * what counts as changed (the rename rule, the archived-delta fallback);
  * what counts as proof (markers, `manual:`, `(prompt half)`, `waiting:`, the
    touched-change scope);
  * what is reported (dangling, repeated, empty corpus, exit codes).

Mutant 7 is the simple form of the rename rule (a body found anywhere in the base
means "unchanged"). It is the wrong form: a NEW scenario whose text repeats an old
one's is hidden. The test that kills it must be read as protecting the correct,
longer rule, not the shorter one.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/_shared/test_check_spec_proof.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
SCRIPT = PLUGIN / "skills" / "_shared" / "scripts" / "check_spec_proof.py"
TARGETS = [DEV / "tests" / "skills" / "_shared" / "test_check_spec_proof.py"]

MUTANTS = [
    (
        "the strict facts match ignores case, so 'Scenario' is accepted as a value",
        SCRIPT,
        '_FACT_STRICT = re.compile(r"^- Test proof granularity: (requirement|scenario)$")',
        '_FACT_STRICT = re.compile(r"^- Test proof granularity: (requirement|scenario)$", re.I)',
        TARGETS,
    ),
    (
        "the loose facts match stops seeing a '*' bullet, so that malformed line is ignored",
        SCRIPT,
        r'_FACT_LOOSE = re.compile(r"^\s*(?:[-*+]\s*)?[*_`]*test proof granularity", re.I)',
        r'_FACT_LOOSE = re.compile(r"^\s*(?:[-]\s*)?[_`]*test proof granularity", re.I)',
        TARGETS,
    ),
    (
        "two facts lines no longer conflict",
        SCRIPT,
        "    if len(found) > 1:",
        "    if len(found) > 2:",
        TARGETS,
    ),
    (
        "a delta's MODIFIED section is no longer read",
        SCRIPT,
        'title.startswith(("ADDED", "MODIFIED"))',
        'title.startswith(("ADDED",))',
        TARGETS,
    ),
    (
        "a delta's REMOVED section is read as if it were requirements",
        SCRIPT,
        'title.startswith(("ADDED", "MODIFIED"))',
        'title.startswith(("ADDED", "MODIFIED", "REMOVED"))',
        TARGETS,
    ),
    (
        "a requirement's body leaves out its scenarios, so editing a scenario is not a change",
        SCRIPT,
        "                    cur_req[2].append(cur_scn)\n                    cur_req[1].append(line)\n",
        "                    cur_req[2].append(cur_scn)\n",
        TARGETS,
    ),
    (
        "the rename rule is the simple one: any body found in the base means unchanged",
        SCRIPT,
        "        if (u.heading, u.body) not in same and not (u.heading not in old_headings and u.body in renamed_from)",
        "        if u.body not in {o.body for o in old_units}",
        TARGETS,
    ),
    (
        "an archived delta is compared with nothing, so archiving re-demands proof for every requirement",
        SCRIPT,
        '    if text is None and f.kind == "archived":',
        "    if False:",
        TARGETS,
    ),
    (
        "a marker of the other granularity is accepted as proof or ignored",
        SCRIPT,
        "        if kind == other:",
        "        if False:",
        TARGETS,
    ),
    (
        "a marker naming a missing requirement is accepted",
        SCRIPT,
        "        elif heading not in universe.get(spec, set()):",
        "        elif False:",
        TARGETS,
    ),
    (
        "archived deltas count as live, so a marker for a requirement that is gone still resolves",
        SCRIPT,
        '        if f.kind != "archived":\n            universe',
        "        if True:\n            universe",
        TARGETS,
    ),
    (
        "a '(prompt half)' manual line proves the requirement on its own",
        SCRIPT,
        "                whole = [n for n in manual if not n.prompt_half]",
        "                whole = manual",
        TARGETS,
    ),
    (
        "an archived change may keep a waiting line",
        SCRIPT,
        '        if n.kind == "waiting" and n.archived:',
        "        if False:",
        TARGETS,
    ),
    (
        "a waiting line stops covering a changed requirement",
        SCRIPT,
        '                if any(not n.archived for n in notes_for(u.heading, scope, "waiting")):',
        "                if False:",
        TARGETS,
    ),
    (
        "Markdown files are scanned for markers",
        SCRIPT,
        '    ".md", ".markdown", ".txt",',
        '    ".markdown", ".txt",',
        TARGETS,
    ),
    (
        "an empty corpus passes",
        SCRIPT,
        "    if not files:\n",
        "    if False:\n",
        TARGETS,
    ),
    (
        "a branch that archives a change no longer counts that change's tasks as touched",
        SCRIPT,
        r'm = re.match(r"openspec/changes/((?:archive/)?[^/]+)/", p)',
        r'm = re.match(r"openspec/changes/([^/]+)/", p)',
        TARGETS,
    ),
    (
        "untracked files are left out of the changed paths",
        SCRIPT,
        '("diff", "--name-only", "-z", base), ("ls-files", "-o", "--exclude-standard", "-z")',
        '("diff", "--name-only", "-z", base),',
        TARGETS,
    ),
    (
        "the shortest matching heading wins, so a heading containing a colon is mis-split",
        SCRIPT,
        "max((h for h in known if body.startswith(h + \": \")), key=len, default=None)",
        "min((h for h in known if body.startswith(h + \": \")), key=len, default=None)",
        TARGETS,
    ),
    (
        "a template line 'manual: <heading>: <reason>' is read as a note",
        SCRIPT,
        '            if body.startswith("<"):',
        "            if False:",
        TARGETS,
    ),
    (
        "a heading repeated once is not reported",
        SCRIPT,
        "            if n > 1:",
        "            if n > 2:",
        TARGETS,
    ),
    (
        "the --tests glob stops limiting the scan",
        SCRIPT,
        "        if globs and not any(fnmatch.fnmatch(rel, g) for g in globs):",
        "        if False:",
        TARGETS,
    ),
    (
        "a checkbox before 'manual:' hides the note",
        SCRIPT,
        r"(?:\[[ xX]\]\s+)?(?:\d+(?:\.\d+)*\.?\s+)?(manual|waiting)",
        r"(?:\d+(?:\.\d+)*\.?\s+)?(manual|waiting)",
        TARGETS,
    ),
    (
        "the changed-requirement rule never runs",
        SCRIPT,
        "    if base is not None:\n        paths",
        "    if False:\n        paths",
        TARGETS,
    ),
    (
        "problems no longer set a non-zero exit",
        SCRIPT,
        "    return (1 if problems else 0), problems + out",
        "    return 0, problems + out",
        TARGETS,
    ),
    (
        "a failed openspec validate is not a problem",
        SCRIPT,
        "    if r.returncode != 0:\n        tail",
        "    if False:\n        tail",
        TARGETS,
    ),
    (
        "a malformed facts line exits 1 instead of 2",
        SCRIPT,
        "        print(f\"check_spec_proof: {exc}\", file=sys.stderr)\n        return 2",
        "        print(f\"check_spec_proof: {exc}\", file=sys.stderr)\n        return 1",
        TARGETS,
    ),
]
