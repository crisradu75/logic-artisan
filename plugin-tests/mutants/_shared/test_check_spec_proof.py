"""Mutation batch for test_check_spec_proof.py.

Status: this batch was extended to 67 mutants but not run to completion, by owner decision on
2026-10-14 (mutation testing is opt-in; see DEVELOPER-GUIDE section 12). It has not been run
against the final code.

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
        r'_FACT_LOOSE = re.compile(r"^[\s>]*(?:(?:[-*+]|\d+[.)])\s*)?[*_`]*test proof granularity", re.I)',
        r'_FACT_LOOSE = re.compile(r"^[\s>]*(?:(?:[-]|\d+[.)])\s*)?[_`]*test proof granularity", re.I)',
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
        "        if cur_req is not None:\n            cur_req[1].append(line)\n            if cur_scn is not None:",
        "        if cur_req is not None:\n            if cur_scn is None:\n                cur_req[1].append(line)\n            if cur_scn is not None:",
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
        "        elif kind == other:",
        "        elif False:",
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
        '("diff", "--name-only", "--relative", "-z", base), ("ls-files", "-o", "--exclude-standard", "-z")',
        '("diff", "--name-only", "--relative", "-z", base),',
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
    (
        "an explicit --base that does not resolve turns the rule off instead of exiting 2",
        SCRIPT,
        '    if explicit:\n        raise CheckerError(f"--base {explicit} does not resolve to a commit")\n',
        "    if explicit:\n        return None, 'x'\n",
        TARGETS,
    ),
    (
        "a run that scanned no file for markers passes",
        SCRIPT,
        "    if scanned == 0:\n",
        "    if False:\n",
        TARGETS,
    ),
    (
        "a spec set that parses to no unit passes",
        SCRIPT,
        "    if not any(f.units for f in files if f.kind != \"archived\"):",
        "    if False:",
        TARGETS,
    ),
    (
        "a marker-like line that misses the format is dropped",
        SCRIPT,
        '            elif _MARKER_LOOSE.match(line) and not line.split(":", 1)[1].lstrip().startswith("<"):',
        "            elif False:",
        TARGETS,
    ),
    (
        "the section title must equal REQUIREMENTS exactly, so '## Requirements (v2)' hides a spec",
        SCRIPT,
        'else title.startswith("REQUIREMENTS")',
        'else title == "REQUIREMENTS"',
        TARGETS,
    ),
    (
        "the facts file is read without -sig, so a byte-order mark hides line 1",
        SCRIPT,
        'facts.read_text(encoding="utf-8-sig")',
        'facts.read_text(encoding="utf-8")',
        TARGETS,
    ),
    (
        "git show reads the path from the repo top, not from a subfolder root",
        SCRIPT,
        'f"{base}:./{rel}"',
        'f"{base}:{rel}"',
        TARGETS,
    ),
    (
        "git diff stops using --relative, so a subfolder root sees repo-top paths",
        SCRIPT,
        '"diff", "--name-only", "--relative", "-z", base',
        '"diff", "--name-only", "-z", base',
        TARGETS,
    ),
    (
        "an undecodable test file is skipped instead of scanned",
        SCRIPT,
        'errors="replace").splitlines()',
        'errors="strict").splitlines()',
        TARGETS,
    ),
    (
        "archived deltas are checked for repeated headings",
        SCRIPT,
        '        if f.kind == "archived":\n            continue  # archives',
        '        if False:\n            continue  # archives',
        TARGETS,
    ),
    (
        "an unexpected crash exits 1 instead of 2",
        SCRIPT,
        '{traceback.format_exc()}", file=sys.stderr)\n        return 2',
        '{traceback.format_exc()}", file=sys.stderr)\n        return 1',
        TARGETS,
    ),
    (
        "a numbered or quoted facts line is no longer seen as malformed",
        SCRIPT,
        r'_FACT_LOOSE = re.compile(r"^[\s>]*(?:(?:[-*+]|\d+[.)])\s*)?[*_`]*test proof granularity", re.I)',
        r'_FACT_LOOSE = re.compile(r"^\s*(?:[-*+]\s*)?[*_`]*test proof granularity", re.I)',
        TARGETS,
    ),
    (
        "the near-miss marker rule drops the slash requirement, so prose comments are flagged",
        SCRIPT,
        r'(?:requirement|scenario):\s*\S[^/]*/\s*\S", re.I)',
        r'(?:requirement|scenario):\s*\S", re.I)',
        TARGETS,
    ),
    (
        "the near-miss marker rule is case-sensitive again",
        SCRIPT,
        r'(?:requirement|scenario):\s*\S[^/]*/\s*\S", re.I)',
        r'(?:requirement|scenario):\s*\S[^/]*/\s*\S")',
        TARGETS,
    ),
    (
        "a '<spec> / <heading>' template line is flagged as a near-miss marker",
        SCRIPT,
        '            elif _MARKER_LOOSE.match(line) and not line.split(":", 1)[1].lstrip().startswith("<"):',
        "            elif _MARKER_LOOSE.match(line):",
        TARGETS,
    ),
    (
        "a UTF-16 file is skipped as binary",
        SCRIPT,
        '        if b"\\0" in raw and not utf16:',
        '        if b"\\0" in raw:',
        TARGETS,
    ),
    (
        "a git-refused repo is read as a non-repo",
        SCRIPT,
        '    return any((p / ".git").exists() for p in [path.resolve(), *path.resolve().parents])',
        "    return False",
        TARGETS,
    ),
    (
        "a git-refused working directory is read as a non-repo when no --root is given",
        SCRIPT,
        "    if _under_git(Path.cwd()):",
        "    if False:",
        TARGETS,
    ),
    (
        "an unborn HEAD with a fetched origin exits 2 instead of turning the rule off",
        SCRIPT,
        '        return None, "no commit on HEAD yet"',
        "        pass",
        TARGETS,
    ),
    (
        "a candidate base whose merge-base fails is skipped without an error",
        SCRIPT,
        "    if failed:\n",
        "    if False:\n",
        TARGETS,
    ),
    (
        "a live spec that parses to nothing is not reported",
        SCRIPT,
        '        if f.kind == "live" and not f.units:',
        "        if False:",
        TARGETS,
    ),
    (
        "an active delta with requirements under no delta heading is not reported",
        SCRIPT,
        '        if f.kind == "active" and not f.units and _REQ_ANYWHERE.search(f.text) and not _DELTA_SECTION.search(f.text):',
        "        if False:",
        TARGETS,
    ),
    (
        "a REMOVED-only delta is reported as empty",
        SCRIPT,
        " and not _DELTA_SECTION.search(f.text):",
        ":",
        TARGETS,
    ),
    (
        "the format guard's problems are dropped from the result",
        SCRIPT,
        "    problems += check_format(files, limits)\n",
        "    check_format(files, limits)\n",
        TARGETS,
    ),
    (
        "limits are read case-sensitively",
        SCRIPT,
        "        hit = re.search(pat, block, re.I)",
        "        hit = re.search(pat, block)",
        TARGETS,
    ),
    (
        "a list at the key's own indent ends the specs block",
        SCRIPT,
        '                    if n_indent < indent or (n_indent == indent and not s.startswith("- ")):',
        "                    if n_indent <= indent:",
        TARGETS,
    ),
    (
        "a number in unknown wording is silently not enforced",
        SCRIPT,
        '            if re.search(rf"(?i)\\b(?:{_NUMBER_WORDS})\\s+(?:\\w+\\s+)?{word}\\b", block):',
        "            if False:",
        TARGETS,
    ),
    (
        "a specs group that states no limit passes",
        SCRIPT,
        '    if not found:\n        raise CheckerError(f"rules.specs',
        '    if False:\n        raise CheckerError(f"rules.specs',
        TARGETS,
    ),
    (
        "config.yml is not read",
        SCRIPT,
        '(root / "openspec" / "config.yaml", root / "openspec" / "config.yml")',
        '(root / "openspec" / "config.yaml",)',
        TARGETS,
    ),
    (
        "the limits are read from the whole config, not only rules.specs",
        SCRIPT,
        "    block = _specs_rules_block(text)\n    if block is None:",
        "    block = text\n    if block is None:",
        TARGETS,
    ),
    (
        "a fence no longer protects a statement from a subsection-like line",
        SCRIPT,
        "        if _FENCE.match(line):\n            fence = not fence\n        elif not fence and _H4.match(line):",
        "        if _FENCE.match(line):\n            pass\n        elif not fence and _H4.match(line):",
        TARGETS,
    ),
    (
        "a subsection heading no longer ends the statement",
        SCRIPT,
        "        elif not fence and _H4.match(line):\n            break",
        "        elif not fence and _SCN.match(line):\n            break",
        TARGETS,
    ),
    (
        "a delta is counted by its own blocks only",
        SCRIPT,
        "                total = len(base | {h for h, _, _ in reqs}) - len(base & _removed_headings(f.text))",
        "                total = len(reqs)",
        TARGETS,
    ),
    (
        "a delta's removals are not subtracted",
        SCRIPT,
        " - len(base & _removed_headings(f.text))",
        "",
        TARGETS,
    ),
    (
        "an active delta is not combined with its live spec",
        SCRIPT,
        '            if f.kind == "active":\n                base',
        "            if False:\n                base",
        TARGETS,
    ),
    (
        "a requirement exactly at the scenario limit is reported",
        SCRIPT,
        '            if "scenarios" in limits and len(scns) > limits["scenarios"]:',
        '            if "scenarios" in limits and len(scns) >= limits["scenarios"]:',
        TARGETS,
    ),
    (
        "a statement exactly at the character limit is reported",
        SCRIPT,
        '                if n > limits["chars"]:',
        '                if n >= limits["chars"]:',
        TARGETS,
    ),
    (
        "a spec exactly at the requirement limit is reported",
        SCRIPT,
        '            if total > limits["requirements"]:',
        '            if total >= limits["requirements"]:',
        TARGETS,
    ),
    (
        "an oversize file is skipped without a problem",
        SCRIPT,
        '        if why != "binary":',
        "        if False:",
        TARGETS,
    ),
    (
        "a crash prints no traceback",
        SCRIPT,
        "\\n{traceback.format_exc()}",
        "",
        TARGETS,
    ),
]
