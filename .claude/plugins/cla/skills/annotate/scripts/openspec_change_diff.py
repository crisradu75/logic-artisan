"""A change's requirement diffs and its overview, for `openspec_change.py`.

Compares the requirements a delta spec changes against the main spec by word,
and reads the proposal's promises into the overview's buckets. Not a command:
import it, or use `openspec_change.py`.
"""

import difflib
import re

from openspec_change_claims import REQ_RE, _lines, fence_mask, sections_of, strip_md


# ---------------------------------------------------------------- requirement diffs


# A `##` heading ends a requirement block, as it ends OpenSpec's (`^##\s+`, which
# a `###` or `####` heading does not match). Scenarios and other deeper headings
# stay inside the requirement they belong to.
_BODY_END_RE = re.compile(r"^##\s+")
_REQUIREMENTS_SECTION_RE = re.compile(r"^##\s+Requirements\s*$", re.I)

# Unchanged runs longer than this collapse, keeping DIFF_CONTEXT words on each
# side that faces a change.
DIFF_COLLAPSE = 12
DIFF_CONTEXT = 6

DIFF_STATES = ("archived", "no-main-spec", "unreadable", "not-in-main", "same", "diff")


def _norm_name(name):
    """A requirement name as OpenSpec 1.14.1 matches it
    (`normalizeRequirementName` in dist/core/parsers/requirement-blocks.js): a
    closing run of `#` that follows a space or tab is dropped, as an ATX heading
    renders without it, and the ends are trimmed. Nothing else is folded — case
    and inner spacing both count — so a header that differs in either is a
    different requirement, and OpenSpec's archive refuses it."""
    return re.sub(r"[ \t]+#+[ \t]*$", "", name).strip()


def _body_words(lines):
    """The words of a requirement body as a reader sees them: list markers and
    scenario hashes off, inline markup stripped."""
    out = []
    for line in lines:
        line = re.sub(r"^\s*(?:#{1,6}\s+|[-*]\s+)", "", line)
        out += strip_md(line).split()
    return out


def _body_at(lines, start, mask):
    """The lines after the heading on line index `start`, up to the next
    requirement header or `##` heading outside a code fence — where OpenSpec
    ends a requirement block. A `###` heading of another kind, and anything in
    a fence, stays inside the block."""
    body = []
    for i in range(start + 1, len(lines)):
        if not mask[i] and (REQ_RE.match(lines[i]) or _BODY_END_RE.match(lines[i])):
            break
        body.append(lines[i])
    return body


def requirement_bodies(text):
    """`{normalised name: (name, body words)}` for every requirement in a main
    spec, read as OpenSpec reads one (`extractRequirementsSection`): only under
    `## Requirements`, never from a code fence, each block ending at the next
    requirement or `##` heading. If a name repeats, the LAST one wins, as it
    does when OpenSpec builds its name-to-block map (`specs-apply.js`)."""
    lines = _lines(text)
    mask = fence_mask(lines)
    out, inside = {}, False
    for i, line in enumerate(lines):
        if mask[i]:                     # a fenced line is an example, never a heading
            continue
        if _BODY_END_RE.match(line):
            inside = bool(_REQUIREMENTS_SECTION_RE.match(line))
            continue
        m = REQ_RE.match(line) if inside else None
        if m:
            out[_norm_name(m.group(1))] = (m.group(1), _body_words(_body_at(lines, i, mask)))
    return out


def _word_ops(base, new):
    """[(tag, words)] with tag `eq`, `del` or `ins`, and `gap` carrying the number
    of unchanged words a long run collapsed. A run is collapsed only when it is
    longer than DIFF_COLLAPSE and at least two words would be hidden; a gap
    hiding one word costs more to read than the word.

    `autojunk=False`: with it on, once the NEW body is 200 words or more,
    difflib treats every word that makes up more than 1% of it — "the",
    "SHALL" — as junk, and
    the diff then aligns around those words instead of through them."""
    sm = difflib.SequenceMatcher(None, base, new, autojunk=False)
    codes = sm.get_opcodes()
    ops = []
    for k, (tag, i1, i2, j1, j2) in enumerate(codes):
        if tag == "equal":
            run = base[i1:i2]
            first, last = k == 0, k == len(codes) - 1
            head = [] if first else run[:DIFF_CONTEXT]
            tail = [] if last else run[-DIFF_CONTEXT:]
            if len(run) <= DIFF_COLLAPSE or len(run) - len(head) - len(tail) < 2:
                ops.append(("eq", run))
                continue
            if head:
                ops.append(("eq", head))
            ops.append(("gap", len(run) - len(head) - len(tail)))
            if tail:
                ops.append(("eq", tail))
            continue
        if tag in ("delete", "replace"):
            ops.append(("del", base[i1:i2]))
        if tag in ("insert", "replace"):
            ops.append(("ins", new[j1:j2]))
    return ops


def requirement_diffs(claims, texts, main_specs, archived):
    """`{claim id: {"state", "ops", "cap", "why"}}` for every MODIFIED
    requirement: how its new text differs from the main spec's.

    Reads no files — `main_specs` maps a capability to its main spec's text, to
    None when there is none, or to the exception that stopped it being read.
    `archived` wins over everything: archiving writes a change's requirements
    into the main spec, so for an archived change the main spec already holds
    the NEW text and comparing against it would report every requirement
    unchanged, which is false.
    """
    out = {}
    for c in claims:
        if c["kind"] != "requirement" or c.get("group") != "MODIFIED":
            continue
        cap = c["file"][len("spec-"):]
        rec = {"state": "", "ops": [], "cap": cap, "why": ""}
        out[c["id"]] = rec
        if archived:
            rec["state"] = "archived"
            continue
        base_text = main_specs.get(cap)
        if base_text is None:
            rec["state"] = "no-main-spec"
            continue
        if not isinstance(base_text, str):
            rec["state"], rec["why"] = "unreadable", str(base_text)
            continue
        base = requirement_bodies(base_text).get(_norm_name(c["raw"]))
        if base is None:
            rec["state"] = "not-in-main"
            continue
        lines = _lines(texts.get(c["file"], ""))
        new = _body_words(_body_at(lines, c["line"] - 1, fence_mask(lines)))
        if base[1] == new:
            rec["state"] = "same"
            continue
        rec["state"], rec["ops"] = "diff", _word_ops(base[1], new)
    return out


# ---------------------------------------------------------------- overview


# OpenSpec 1.14.1's FROM/TO line (`parseRenamedPairs` in
# dist/core/parsers/requirement-blocks.js): an optional `-`, `*` or `+`, the
# keyword in capitals, and a requirement header, backticked or not.
RENAME_RE = re.compile(r"^\s*[-*+]?\s*(FROM|TO):\s*`?###\s*Requirement:\s*(.+?)`?\s*$")

# The bucket a promise lands in, in the order the overview lists them.
PROMISE_BUCKETS = ("uncovered", "unchecked", "covered")


def _first_paragraph(lines):
    para = []
    for _n, line in lines:
        if not line.strip():
            if para:
                break
            continue
        para.append(line.strip())
    return strip_md(" ".join(para))


BREAKING_RE = re.compile(r"\bBREAKING\b")


def _delta_sections(text):
    """`[(title, lines)]` for each `##` section of a delta, one entry per
    occurrence and in file order, with fenced lines left out — as OpenSpec's
    `splitTopLevelSections` and `parseRenamedPairs` read it. A RENAMED pair is
    therefore read within one copy of its section, and a `## Purpose` or a
    FROM/TO shown in an example does not count."""
    lines = _lines(text)
    mask = fence_mask(lines)
    out = []
    for i, line in enumerate(lines):
        if mask[i]:
            continue
        m = re.match(r"^##\s+(.+)$", line)
        if m:
            out.append((m.group(1).strip(), []))
        elif out:
            out[-1][1].append(line)
    return out


def overview(model, texts):
    """The change's shape, derived from what `build` already parsed: no file is
    read and nothing new is inferred.

    `{why, why_state, promises: [(claim, bucket)], breaking: {claim id}, reqs:
    {cap: {group: n}}, renamed: {cap: n}, status: {cap: str}, tasks: (done,
    total), tasks_file, skip_specs}`.

    `why` is the first paragraph of the proposal's `## Why`, and `why_state`
    says whether there was one: `found`, `empty` or `missing`. `tasks_file` says
    whether the change has a tasks.md at all, so "no tasks" can say which kind
    of nothing it is. `breaking` holds the promises carrying the word
    **BREAKING**, the schema's mark. `renamed` counts FROM/TO pairs under
    `## RENAMED Requirements` — a FROM followed by a TO within one copy of the
    section, fenced lines skipped, as OpenSpec pairs them — which
    `requirements()` never sees because they are bullets. A delta's
    `## Purpose` is found the same way, outside fences.

    A capability's `status` is `new` when the proposal lists it under
    `### New Capabilities`, its delta opens with `## Purpose` (the schema's
    mark of a new capability), or it has no main spec; `modified` when its main
    spec was read; and `unknown` otherwise — an archived change's main specs
    are never read, nor are those of a change folder outside `changes/`, and
    an unreadable one says nothing either way.
    """
    why, why_state = "", "missing"
    for title, lines in sections_of(texts.get("proposal", "")).items():
        if title.lower() == "why":
            why = _first_paragraph(lines)
            why_state = "found" if why else "empty"
            break

    cov = model["coverage"]
    bucket = {}
    for name in PROMISE_BUCKETS:
        for row in cov.get(name, []):
            bucket[row["claim"]["id"]] = name
    promises_ = [(c, bucket.get(c["id"], "unchecked"))
                 for c in model["claims"] if c["kind"] == "promise"]

    reqs, renamed = {}, {}
    for key in sorted(k for k in texts if k.startswith("spec-")):
        cap = key[len("spec-"):]
        reqs[cap] = {g: 0 for g in ("ADDED", "MODIFIED", "REMOVED")}
        pairs = 0
        for title, lines in _delta_sections(texts[key]):
            if title.upper() != "RENAMED REQUIREMENTS":
                continue
            pending = False
            for line in lines:
                m = RENAME_RE.match(line)
                if not m:
                    continue
                if m.group(1) == "FROM":
                    pending = True
                elif pending:
                    pairs, pending = pairs + 1, False
        renamed[cap] = pairs
    for c in model["claims"]:
        if c["kind"] == "requirement" and c.get("group") in ("ADDED", "MODIFIED", "REMOVED"):
            reqs[c["file"][len("spec-"):]][c["group"]] += 1

    listed_new = {c["name"] for c in model["capabilities"] if c["new"]}
    main = model.get("main_spec", {})
    status = {}
    for cap in reqs:
        has_purpose = any(t.lower() == "purpose"
                          for t, _l in _delta_sections(texts.get("spec-" + cap, "")))
        if cap in listed_new or has_purpose or main.get(cap) == "absent":
            status[cap] = "new"
        elif main.get(cap) == "present":
            status[cap] = "modified"
        else:
            status[cap] = "unknown"

    breaking = {c["id"] for c in model["claims"]
                if c["kind"] == "promise" and BREAKING_RE.search(c.get("raw") or "")}

    st = cov["stats"]
    return {"why": why, "why_state": why_state, "promises": promises_,
            "breaking": breaking, "reqs": reqs, "renamed": renamed, "status": status,
            "tasks": (st["tasks_done"], st["tasks"]), "tasks_file": "tasks" in texts,
            "skip_specs": bool(model.get("skip_specs"))}


def skip_specs_set(yaml_text):
    """Whether a change's `.openspec.yaml` sets `skip_specs: true` — the
    schema's mark of a change that deliberately has no spec deltas. OpenSpec
    reads it with a YAML 1.2 parser into a boolean, so only an unquoted `true`
    (`True` and `TRUE` are the same boolean) counts: `yes` and `on` are
    strings in YAML 1.2, and a quoted "true" is a string too. One top-level key
    is all that is read, so no YAML parser is needed. OpenSpec also ignores the
    flag when the file is not valid change metadata; that is not checked
    here."""
    return bool(re.search(r"(?m)^skip_specs[ \t]*:[ \t]*(?:true|True|TRUE)[ \t]*(?:#.*)?$",
                          yaml_text or ""))
