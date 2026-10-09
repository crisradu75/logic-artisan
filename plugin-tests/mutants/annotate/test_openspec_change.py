"""Mutants for the change model in openspec_change.py.

    python3 plugin-tests/mutate.py plugin-tests/mutants/annotate/test_openspec_change.py
"""
from pathlib import Path

DEV = Path(__file__).resolve().parents[2]                 # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
OC = PLUGIN / "skills" / "annotate" / "scripts" / "openspec_change.py"
TESTS = [DEV / "tests" / "skills" / "annotate" / "test_openspec_change.py",
         DEV / "tests" / "skills" / "annotate" / "test_review_findings.py"]

MUTANTS = [
    # ------------------------------------------------ a capability mentioned
    ("a capability the proposal mentions is never counted as named",
     OC,
     '    return re.search(pattern, text or "", re.I) is not None',
     "    return False",
     TESTS),

    ("a longer name ending in the capability counts as a mention of it",
     OC,
     '    pattern = r"(?<![\\w/-])" + re.escape(name) + r"(?![\\w/-])"',
     '    pattern = re.escape(name) + r"(?![\\w/-])"',
     TESTS),

    ("a longer name starting with the capability counts as a mention of it",
     OC,
     '    pattern = r"(?<![\\w/-])" + re.escape(name) + r"(?![\\w/-])"',
     '    pattern = r"(?<![\\w/-])" + re.escape(name)',
     TESTS),

    ("the last segment of a capability path counts as a mention of another one",
     OC,
     '    pattern = r"(?<![\\w/-])" + re.escape(name) + r"(?![\\w/-])"',
     '    pattern = r"(?<![\\w-])" + re.escape(name) + r"(?![\\w/-])"',
     TESTS),

    ("the first segment of a capability path counts as a mention of another one",
     OC,
     '    pattern = r"(?<![\\w/-])" + re.escape(name) + r"(?![\\w/-])"',
     '    pattern = r"(?<![\\w/-])" + re.escape(name) + r"(?![\\w-])"',
     TESTS),

    # ------------------------------------------------ OpenSpec 1.14 shapes
    ("a nested capability path gets no file, as before",
     OC,
     '        if "spec.md" in names and os.path.abspath(dirpath) != os.path.abspath(specs):',
     '        if "spec.md" in names and os.path.dirname(os.path.abspath(dirpath))'
     ' == os.path.abspath(specs):',
     TESTS),

    ("a folder that cannot be listed is skipped in silence",
     OC,
     "    walk = os.walk(specs, onerror=refuse, followlinks=True) if os.path.isdir(specs) else ()",
     "    walk = os.walk(specs, followlinks=True) if os.path.isdir(specs) else ()",
     TESTS),

    ("a link cycle under specs/ is walked again and again",
     OC,
     "        if real in seen:",
     "        if False:",
     TESTS),

    ("only an upper-case X is done",
     OC,
     '                          done=(m.group(1) or "").lower() == "x", group=group))',
     '                          done=(m.group(1) or "") == "X", group=group))',
     TESTS),

    ("only - and * open a task line again",
     OC,
     'TASK_RE = re.compile(r"^\\s*(?:[-*+]|\\d{1,9}[.)])\\s*\\[',
     'TASK_RE = re.compile(r"^\\s*(?:[-*])\\s*\\[',
     TESTS),

    ("a one-character link reads as a task",
     OC,
     '\\](?![(\\[])|\\s+\\])"',
     '\\]|\\s+\\])"',
     TESTS),

    ("a whitespace-only box followed by a link is not a task",
     OC,
     '\\](?![(\\[])|\\s+\\])"',
     '\\](?![(\\[]))"',
     TESTS),

    ("a promise naming a longer capability links to the shorter one's requirements",
     OC,
     '            if other["kind"] in ("promise",) and _mentions(other.get("raw") or "", cap):',
     '            if other["kind"] in ("promise",) and cap in (other.get("raw") or "").lower():',
     TESTS),

    ("a mention only counts in the exact case the heading spells",
     OC,
     '    return re.search(pattern, text or "", re.I) is not None',
     '    return re.search(pattern, text or "", 0) is not None',
     TESTS),

    # ------------------------------------------------ requirement diffs
    ("a diff deletes the new words and inserts the main spec's",
     OC,
     '        rec["state"], rec["ops"] = "diff", _word_ops(base[1], new)',
     '        rec["state"], rec["ops"] = "diff", _word_ops(new, base[1])',
     TESTS),

    ("an archived change is compared against the main spec it already wrote",
     OC,
     "        if archived:",
     "        if False:",
     TESTS),

    ("a long unchanged run is never collapsed",
     OC,
     "            if len(run) <= DIFF_COLLAPSE or len(run) - len(head) - len(tail) < 2:",
     "            if True:",
     TESTS),

    ("a gap may hide a single word",
     OC,
     "            if len(run) <= DIFF_COLLAPSE or len(run) - len(head) - len(tail) < 2:",
     "            if len(run) <= DIFF_COLLAPSE:",
     TESTS),

    ("a MODIFIED header matches the main spec in any case",
     OC,
     '    return re.sub(r"[ \\t]+#+[ \\t]*$", "", name).strip()',
     '    return re.sub(r"[ \\t]+#+[ \\t]*$", "", name).strip().lower()',
     TESTS),

    ("a MODIFIED header matches the main spec whatever its inner spacing",
     OC,
     '    return re.sub(r"[ \\t]+#+[ \\t]*$", "", name).strip()',
     '    return " ".join(re.sub(r"[ \\t]+#+[ \\t]*$", "", name).split())',
     TESTS),

    ("a closing ### run stays part of the name",
     OC,
     '    return re.sub(r"[ \\t]+#+[ \\t]*$", "", name).strip()',
     "    return name.strip()",
     TESTS),

    ("a # with no space before it is stripped from the name",
     OC,
     '    return re.sub(r"[ \\t]+#+[ \\t]*$", "", name).strip()',
     '    return re.sub(r"[ \\t]*#+[ \\t]*$", "", name).strip()',
     TESTS),

    ("a repeated main-spec requirement compares against the first copy",
     OC,
     "            out[_norm_name(m.group(1))] = (m.group(1), _body_words(_body_at(lines, i)))",
     "            out.setdefault(_norm_name(m.group(1)), (m.group(1), _body_words(_body_at(lines, i))))",
     TESTS),

    ("a requirement's diff stops at its first scenario",
     OC,
     '_BODY_END_RE = re.compile(r"^#{2,3}\\s")',
     '_BODY_END_RE = re.compile(r"^#{2,4}\\s")',
     TESTS),

    # ------------------------------------------------ overview
    ("every promise is reported covered whatever coverage found",
     OC,
     '            bucket[row["claim"]["id"]] = name',
     '            bucket[row["claim"]["id"]] = "covered"',
     TESTS),

    ("a **BREAKING** promise is never marked",
     OC,
     'BREAKING_RE = re.compile(r"\\bBREAKING\\b")',
     'BREAKING_RE = re.compile(r"\\bNEVER_MARKED\\b")',
     TESTS),

    ("a delta opening with ## Purpose does not make its capability new",
     OC,
     '        has_purpose = any(t.lower() == "purpose"',
     '        has_purpose = any(t.lower() == "no such section"',
     TESTS),

    ("a capability listed under New Capabilities is not new",
     OC,
     '        if cap in listed_new or has_purpose or main.get(cap) == "absent":',
     '        if has_purpose or main.get(cap) == "absent":',
     TESTS),

    ("a capability with no main spec is not new",
     OC,
     '        if cap in listed_new or has_purpose or main.get(cap) == "absent":',
     "        if cap in listed_new or has_purpose:",
     TESTS),

    ("a capability whose main spec was never read is called modified",
     OC,
     '        elif main.get(cap) == "present":',
     "        elif True:",
     TESTS),

    ("an empty ## Why reads as a missing one",
     OC,
     '            why_state = "found" if why else "empty"',
     '            why_state = "found" if why else "missing"',
     TESTS),

    ("a change without tasks.md reads as one with no task lines",
     OC,
     '"tasks_file": "tasks" in texts,',
     '"tasks_file": True,',
     TESTS),

    ("a TO with no FROM before it counts as a rename",
     OC,
     "                elif pending:",
     "                else:",
     TESTS),

    ("a ## Purpose heading leaves the group before it open",
     OC,
     '        if re.match(r"^##\\s", line):',
     "        if False:",
     TESTS),

    ("skip_specs no longer quiets a missing delta",
     OC,
     "    if skip_specs:",
     "    if False:",
     TESTS),

    ("a commented-out or nested skip_specs counts as set",
     OC,
     '    return bool(re.search(r"(?m)^skip_specs',
     '    return bool(re.search(r"(?m)skip_specs',
     TESTS),

    ("skip_specs: yes counts as set, which YAML 1.2 reads as a string",
     OC,
     "(?:true|True|TRUE)[ \\t]*(?:#.*)?$",
     "(?:true|True|TRUE|yes)[ \\t]*(?:#.*)?$",
     TESTS),

    ("an unreadable main spec is treated as text",
     OC,
     "        if not isinstance(base_text, str):",
     "        if False:",
     TESTS),
]
