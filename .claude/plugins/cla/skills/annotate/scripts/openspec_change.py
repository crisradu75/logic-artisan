#!/usr/bin/env python3
"""An OpenSpec change as one reviewable unit: its files, its claims, and which
claims cover which.

Stdlib only, and it runs on Windows and POSIX alike.

**Why this exists.** The four files of a change are only worth reading together
because a claim in one is answered in another: a proposal bullet is implemented
by a task, a capability names a spec delta, a task cites a design decision. Read
one at a time, that structure is held in the reader's head. This module makes it
explicit, so the page can show it and the reader can see what nothing answers.

**Claims are parsed from the raw markdown, then bound to rendered blocks by
text.** Structure comes from shapes this module controls — `## What Changes`
bullets, `- [ ] N.N` tasks, `### Requirement:` headings — because those are
precise. The block a claim lives in comes from matching its text against the
render, one match or none. A claim that cannot be bound keeps its place in the
list and loses only its link; it is never bound to a guess.

**A link is evidence, never an inference.** Every one carries the token that
produced it, and the page shows that token. Four families, all deterministic,
and only the first two settle anything:

  reference   an explicit citation: "design decision 3", "task 2.1", or a
              capability name resolving to its spec delta
  path        a file path — or a directory of two segments or more — named in
              two claims IN DIFFERENT FILES; the strongest signal a change
              offers, because a path names one thing
  identifier  a backticked code identifier of `IDENT_MIN` characters or more
  wording     two or more distinctive words in common, for the half of all
              promises that name no file and no identifier at all

**Only a reference or a path link TO A TASK discharges a promise.** A bullet can
MENTION a name without being about it — this repo's own sweep bullet once listed `sync-context`
among its candidates and was read as implemented by every task touching that skill.
Identifier and wording links are shown, because they are often the useful thing
to read, and are never counted as coverage.

**A token shared by too many PROMISES is not evidence.** What disqualifies a
token is failing to discriminate between the claims that need covering. Counting
holders across every claim instead left 83% of promises falsely uncovered —
`sweep_changes.py`, 355 changes — because a path named in one promise and twelve
tasks is the best evidence a change has, and it looked like vocabulary.

**Three outcomes, and only one is a finding.** *Uncovered* means the bullet names
a file or an identifier and nothing names it back. *Not checkable* means it names
neither, so there was nothing to match on — 51% of promises across the sweep,
because design and product bullets are prose and prose is not a link; calling
those uncovered is the overclaim this module exists to avoid. *Covered* is the
rest, 22%. A task not yet done is none of the three and has its own bucket.
Every row states what was looked for, because the reader is the one who can tell
the difference. Re-measure with `sweep_changes.py` before trusting any of this in
a repo whose changes are written differently.
"""
import os

from openspec_change_claims import (
    capabilities,
    decisions,
    goals,
    impacts,
    promises,
    requirements,
    tasks,
)
from openspec_change_diff import requirement_diffs
from openspec_change_links import _disambiguate, capability_coverage, coverage, detect_links

# Names this module held before its parts were split out: other scripts and the tests read them from here.
from openspec_change_claims import (
    BACKTICK_RE,
    BULLET_RE,
    CLAIM_KINDS,
    CORE_FILES,
    ChangeUnreadable,
    DECISION_RE,
    REQ_GROUP_RE,
    REQ_RE,
    TASK_RE,
    _claim,
    change_files,
    claim_id,
    fence_mask,
    find_change,
    sections_of,
    strip_md,
)
from openspec_change_diff import (
    BREAKING_RE,
    DIFF_COLLAPSE,
    DIFF_CONTEXT,
    DIFF_STATES,
    PROMISE_BUCKETS,
    RENAME_RE,
    _norm_name,
    overview,
    requirement_bodies,
    skip_specs_set,
)
from openspec_change_links import (
    COMMON_SHARE,
    DECISION_REF_RE,
    GENERIC_FILES,
    IDENT_MIN,
    IDENT_RE,
    LEXICAL_CAP,
    LEXICAL_MIN,
    LINK_KINDS,
    PATH_RE,
    STOPWORDS,
    STRONG_KINDS,
    TASK_REF_RE,
    UBIQUITOUS,
    WORD_RE,
    content_words,
    tokens_of,
)

def build(change_dir, texts, main_specs=None, archived=False, skip_specs=False):
    """Everything the page needs. `texts` maps a file key to its raw markdown;
    `main_specs`, when given, maps a capability to its main spec's text (see
    `requirement_diffs`), and only then are MODIFIED requirements diffed.
    `skip_specs` is the change's `.openspec.yaml` flag: with it set, a
    capability the proposal names is not flagged for having no delta."""
    caps = capabilities(texts.get("proposal", ""))
    claims = []
    claims += promises(texts.get("proposal", ""))
    claims += impacts(texts.get("proposal", ""))
    claims += decisions(texts.get("design", ""))
    claims += goals(texts.get("design", ""))
    claims += tasks(texts.get("tasks", ""))
    for key, text in texts.items():
        if key.startswith("spec-"):
            claims += requirements(text, key)
    claims = _disambiguate(claims)
    links, stats = detect_links(claims, caps)
    cov = coverage(claims, links)
    cov["capabilities"] = capability_coverage(caps, texts, claims)
    if skip_specs:
        for row in cov["capabilities"]:
            if not row["delta"]:
                row["why"] = ""
    cov["stats"].update(stats)
    cov["stats"]["change"] = os.path.basename(change_dir)
    cov["stats"]["files"] = len(texts)
    diffs = ({} if main_specs is None
             else requirement_diffs(claims, texts, main_specs, archived))
    # What is known about each main spec, for the overview's new/modified mark.
    # Only capabilities that were looked up appear: an archived change's main
    # specs are never read, and "not looked up" must not read as "absent".
    main_spec = {cap: ("absent" if v is None else "present" if isinstance(v, str)
                       else "unreadable")
                 for cap, v in (main_specs or {}).items()}
    return {"claims": claims, "links": links, "capabilities": caps, "coverage": cov,
            "diffs": diffs, "main_spec": main_spec, "skip_specs": bool(skip_specs)}
