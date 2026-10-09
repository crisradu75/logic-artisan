"""Mutants for the change model in openspec_change.py.

    python3 plugin-tests/mutate.py plugin-tests/mutants/annotate/test_openspec_change.py
"""
from pathlib import Path

DEV = Path(__file__).resolve().parents[2]                 # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
OC = PLUGIN / "skills" / "annotate" / "scripts" / "openspec_change.py"
TESTS = [DEV / "tests" / "skills" / "annotate" / "test_openspec_change.py",
         DEV / "tests" / "skills" / "annotate" / "test_review_findings.py"]

def _a(text):
    """A multi-line anchor carrying openspec_change.py's own line separator,
    which is CRLF on disk in a clone with `core.autocrlf` on."""
    nl = "\r\n" if b"\r\n" in OC.read_bytes() else "\n"
    return text.replace("\n", nl)


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
     "        if real in seen or not _inside(real, root_real):",
     "        if not _inside(real, root_real):",
     TESTS),

    ("a link out of specs/ adds another change's delta as a tab",
     OC,
     "        if real in seen or not _inside(real, root_real):",
     "        if real in seen:",
     TESTS),

    ("a link to a folder under specs/ takes the tab's name from the folder",
     OC,
     "        dirs.sort(key=lambda n: (_is_link(os.path.join(dirpath, n)), n))",
     "        dirs.sort()",
     TESTS),

    ("a byte-order mark hides the first line",
     OC,
     '    return (text or "").lstrip(chr(0xFEFF)).replace(',
     '    return (text or "").replace(',
     TESTS),

    ("a requirement header in lower case is not one",
     OC,
     'REQ_RE = re.compile(r"^###\\s*Requirement:\\s*(.+?)\\s*$", re.I)',
     'REQ_RE = re.compile(r"^###\\s*Requirement:\\s*(.+?)\\s*$")',
     TESTS),

    ("a requirement header needs a space after ###",
     OC,
     'REQ_RE = re.compile(r"^###\\s*Requirement:\\s*(.+?)\\s*$", re.I)',
     'REQ_RE = re.compile(r"^###\\s+Requirement:\\s*(.+?)\\s*$", re.I)',
     TESTS),

    ("a group heading in another case keeps its own spelling",
     OC,
     "            group = g.group(1).upper()",
     "            group = g.group(1)",
     TESTS),

    ("a requirement shown in a delta's code fence is read as one",
     OC,
     "        if mask[n - 1]:",
     "        if False:",
     TESTS),

    ("a requirement shown in a main spec's code fence is read as one",
     OC,
     "        if mask[i]:                     # a fenced line is an example, never a heading",
     "        if False:",
     TESTS),

    ("a main spec's requirements are read from every section",
     OC,
     "            inside = bool(_REQUIREMENTS_SECTION_RE.match(line))",
     "            inside = True",
     TESTS),

    ("a ## shown in a fence ends the requirement block",
     OC,
     "        if not mask[i] and (REQ_RE.match(lines[i]) or _BODY_END_RE.match(lines[i])):",
     "        if REQ_RE.match(lines[i]) or _BODY_END_RE.match(lines[i]):",
     TESTS),

    ("a ### heading of another kind ends the requirement block",
     OC,
     '_BODY_END_RE = re.compile(r"^##\\s+")',
     '_BODY_END_RE = re.compile(r"^###?\\s+")',
     TESTS),

    ("a FROM/TO or ## Purpose shown in a fence counts",
     OC,
     _a("    out = []\n    for i, line in enumerate(lines):\n        if mask[i]:\n            continue"),
     _a("    out = []\n    for i, line in enumerate(lines):\n        if False:\n            continue"),
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
     "            out[_norm_name(m.group(1))] = (m.group(1), _body_words(_body_at(lines, i, mask)))",
     "            out.setdefault(_norm_name(m.group(1)), (m.group(1), _body_words(_body_at(lines, i, mask))))",
     TESTS),

    ("a requirement's diff stops at its first scenario",
     OC,
     '_BODY_END_RE = re.compile(r"^##\\s+")',
     '_BODY_END_RE = re.compile(r"^#{2,4}\\s+")',
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
