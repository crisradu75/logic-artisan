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
MENTION a name without being about it — this repo's own sweep bullet lists `sync-context` among
its candidates and was read as implemented by every task touching that skill.
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
import re

# A token held by more than this many PROMISES is vocabulary rather than
# evidence: past that it cannot say which promise a task serves.
#
# Set from the sweep, not from one change — `sweep_changes.py` over every repo on
# this machine: 355 changes, 2264 promises, covered 22%, uncovered 27%, not
# checkable 51%. On this repo's own archived change the rule never fires at all
# (no token reaches even two promises, and `stats["ubiquitous"]` comes back
# empty), which is exactly why one change cannot set it.
UBIQUITOUS = 4

# An identifier shorter than this does not identify one thing. `cla-init` is
# eight characters and names a skill mentioned all over this repo; matching on it
# reported a proposal bullet as covered because that bullet happened to LIST the
# skill among sweep candidates. `EXEMPT_SKILLS` is thirteen and does identify one
# thing. The line sits between them.
IDENT_MIN = 12

# Generic build and config filenames are vocabulary, not evidence: the same
# string names a different file in every directory it appears in, so two claims
# sharing one are not talking about the same thing. `pyproject.toml` in a promise
# about deleting a skill and in a task about scope discovery are two different
# files — and linking them displaced the link that actually mattered.
GENERIC_FILES = frozenset({
    "pyproject.toml", "package.json", "package-lock.json", "setup.py",
    "__init__.py", "tsconfig.json", "requirements.txt", "makefile",
    "readme.md", "claude.md", "spec.md", "proposal.md", "tasks.md", "design.md",
    "skill.md", "todo.md",
})

# Fixed order, never directory order: it is the order a change is written in and
# the order it is read in, and a reader should know where a file will be before
# looking. `design.md` is optional in OpenSpec.
CORE_FILES = (("proposal", "proposal.md"), ("design", "design.md"), ("tasks", "tasks.md"))

# Two shapes, because a change names both: a file, which has an extension, and a
# DIRECTORY, which does not. Missing the second is what let `pyproject.toml`
# stand in for `src/legacy/sync-engine/`.
PATH_RE = re.compile(
    r"(?:[\w.\-]+/)*[\w.\-]+\.(?:py|md|mjs|json|toml|ya?ml|sh|cmd|txt|js|ts)\b"
    r"|(?:[\w.\-]+/){2,}[\w.\-]*")
IDENT_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_.\-]+)`")
BACKTICK_RE = re.compile(r"`([^`]+)`")
TASK_RE = re.compile(r"^\s*[-*]\s*\[( |x|X)\]\s*(\d+(?:\.\d+)*)?\s*(.*)$")
BULLET_RE = re.compile(r"^\s{0,3}[-*]\s+(.*)$")
DECISION_RE = re.compile(r"^\s{0,3}(\d+)\.\s+(.*)$")
REQ_RE = re.compile(r"^###\s+Requirement:\s*(.+?)\s*$")
REQ_GROUP_RE = re.compile(r"^##\s+(ADDED|MODIFIED|REMOVED|RENAMED)\s+Requirements\s*$")
DECISION_REF_RE = re.compile(r"\b(?:design\s+)?decision\s+(\d+)\b", re.I)
TASK_REF_RE = re.compile(r"\btask\s+(\d+(?:\.\d+)+)\b", re.I)


def strip_md(s):
    """Inline markers removed, whitespace collapsed. The rendered page shows text
    without them, so a claim compared against a block has to lose them too."""
    s = re.sub(r"`([^`]*)`", r"\1", s or "")
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s, flags=re.S)
    s = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    return " ".join(s.split())


def sections_of(text):
    """`## Heading` -> the lines beneath it, in file order, with line numbers."""
    out, current = {}, None
    for n, line in enumerate(text.replace("\r\n", "\n").split("\n"), 1):
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            current = strip_md(m.group(1))
            out.setdefault(current, [])
            continue
        if current is not None:
            out[current].append((n, line))
    return out


# ---------------------------------------------------------------- discovery


def find_change(target, root):
    """The directory of a change, given an id, a path, or a directory.

    Active changes and archived ones are both annotatable — a review of what was
    shipped is as legitimate as a review of what is proposed, and the archive is
    where the finished examples live.
    """
    cands = []
    if os.path.isdir(target):
        cands.append(target)
    base = os.path.join(root, "openspec", "changes")
    cands += [os.path.join(base, target), os.path.join(base, "archive", target)]
    for c in cands:
        if os.path.isfile(os.path.join(c, "proposal.md")):
            return os.path.abspath(c)
    # An archived change is prefixed with its date, so the bare id does not match
    # the directory name; suffix-matching finds it without the caller knowing it.
    arch = os.path.join(base, "archive")
    if os.path.isdir(arch):
        hits = [d for d in sorted(os.listdir(arch)) if d.endswith("-" + target)
                and os.path.isfile(os.path.join(arch, d, "proposal.md"))]
        if len(hits) == 1:
            return os.path.abspath(os.path.join(arch, hits[0]))
    return None


def change_files(change_dir):
    """[(key, label, absolute path)] in the fixed order, existing files only."""
    out = []
    for key, name in CORE_FILES:
        p = os.path.join(change_dir, name)
        if os.path.isfile(p):
            out.append((key, key, p))
    specs = os.path.join(change_dir, "specs")
    if os.path.isdir(specs):
        for cap in sorted(os.listdir(specs)):
            p = os.path.join(specs, cap, "spec.md")
            if os.path.isfile(p):
                out.append(("spec-" + cap, "spec · " + cap, p))
    return out


# ---------------------------------------------------------------- claims


def claim_id(file_key, num):
    """The join key for links, coverage and block binding. Spelled here and
    nowhere else: `detect_links` used to rebuild it by hand for citations, and a
    format change would have turned every citation into a silent no-op."""
    return "%s:%s" % (file_key, num)


def _claim(file_key, kind, num, text, line, **extra):
    assert kind in CLAIM_KINDS, kind
    cid = claim_id(file_key, num)
    rec = {"id": cid, "file": file_key, "kind": kind, "num": num,
           "text": strip_md(text), "raw": text, "line": line}
    rec.update(extra)
    return rec


def promises(text):
    """The proposal's `## What Changes` bullets — what the change promises to do.

    Only top-level bullets. A sub-bullet elaborates its parent rather than
    promising something separate, and counting it as its own claim reports the
    parent as covered while its detail goes unmentioned by any task.
    """
    out = []
    for title, lines in sections_of(text).items():
        if title.lower() != "what changes":
            continue
        for n, line in lines:
            if line[:1] not in ("-", "*"):
                continue
            m = BULLET_RE.match(line)
            if m:
                out.append(_claim("proposal", "promise", "p%d" % (len(out) + 1),
                                  m.group(1), n))
    return out


def impacts(text):
    """`## Impact` bullets. Claims about consequence rather than work, so they
    are shown but never counted as uncovered: nothing is owed against them."""
    out = []
    for title, lines in sections_of(text).items():
        if title.lower() != "impact":
            continue
        for n, line in lines:
            m = BULLET_RE.match(line)
            if m and line[:1] in ("-", "*"):
                out.append(_claim("proposal", "impact", "i%d" % (len(out) + 1),
                                  m.group(1), n))
    return out


def capabilities(text):
    """Capability names under `## Capabilities`, and whether they are new."""
    out = []
    for title, lines in sections_of(text).items():
        if "capabilit" not in title.lower():
            continue
        new = False
        for n, line in lines:
            h = re.match(r"^###\s+(.+?)\s*$", line)
            if h:
                new = "new" in h.group(1).lower()
                continue
            m = BULLET_RE.match(line)
            if not m or line[:1] not in ("-", "*"):
                continue
            name = BACKTICK_RE.search(m.group(1))
            if name:
                out.append({"name": name.group(1), "new": new, "line": n,
                            "text": strip_md(m.group(1))})
    return out


def tasks(text):
    """Every `- [ ] N.N ...` item, with its checkbox state and its `## N.` group."""
    out, group = [], ""
    for n, line in enumerate(text.replace("\r\n", "\n").split("\n"), 1):
        h = re.match(r"^##\s+(.+?)\s*$", line)
        if h:
            group = strip_md(h.group(1))
            continue
        m = TASK_RE.match(line)
        if not m:
            continue
        num = m.group(2) or str(len(out) + 1)
        out.append(_claim("tasks", "task", num, m.group(3), n,
                          done=m.group(1).lower() == "x", group=group))
    return out


def requirements(text, file_key):
    """`### Requirement: X` headings, tagged with the ADDED/MODIFIED/REMOVED
    group they sit under. A REMOVED requirement still needs a task — deleting a
    requirement is work — so it is a claim like any other."""
    out, group = [], ""
    for n, line in enumerate(text.replace("\r\n", "\n").split("\n"), 1):
        g = REQ_GROUP_RE.match(line)
        if g:
            group = g.group(1)
            continue
        m = REQ_RE.match(line)
        if m:
            out.append(_claim(file_key, "requirement", "r%d" % (len(out) + 1),
                              m.group(1), n, group=group))
    return out


def decisions(text):
    """The design's numbered decisions. The bold lead sentence is the title —
    the rest is the argument, and a decision is cited by its number."""
    out = []
    for title, lines in sections_of(text).items():
        if title.lower() != "decisions":
            continue
        for n, line in lines:
            m = DECISION_RE.match(line)
            if not m:
                continue
            body = m.group(2)
            lead = re.match(r"\*\*(.+?)\*\*", body)
            out.append(_claim("design", "decision", m.group(1),
                              lead.group(1) if lead else body, n, body=strip_md(body)))
    return out


def goals(text):
    """`## Goals / Non-Goals` bullets — cited by tasks and worth linking, but
    never owed anything, so they are never uncovered."""
    out = []
    for title, lines in sections_of(text).items():
        if "goal" not in title.lower():
            continue
        for n, line in lines:
            m = BULLET_RE.match(line)
            if m and line[:1] in ("-", "*"):
                out.append(_claim("design", "goal", "g%d" % (len(out) + 1),
                                  m.group(1), n))
    return out


# ---------------------------------------------------------------- links


def tokens_of(claim):
    """The evidence-bearing tokens in one claim: file paths and long backticked
    identifiers. Lower-cased, because a path's casing varies between prose and a
    command line and a link missed on that is a link missed for no reason."""
    raw = claim.get("raw") or claim.get("text") or ""
    found = set()
    for m in PATH_RE.finditer(raw):
        tok = m.group(0).strip("`,;:").rstrip(".").lower()
        if "/" not in tok and os.path.basename(tok) in GENERIC_FILES:
            continue
        if len(tok) >= 6:
            found.add(tok)
    for m in IDENT_RE.finditer(raw):
        tok = m.group(1).strip("`.,;:").lower()
        if PATH_RE.fullmatch(tok) or tok in GENERIC_FILES:
            continue
        if len(tok) >= IDENT_MIN:
            found.add(tok)
    return found


# Words carried by the scaffolding of a change rather than by its subject.
STOPWORDS = frozenset("""
about above across after against along among around because before behind below
beside between beyond during except inside into onto outside over through under
until within without which while where whose whether should would could their
there these those they them this that then than with from have has had been being
will shall must may can not but and the for its it's are was were more most other
another same such only just also still even ever never always already yet each
every both either neither all any some none one two three add adds added adding
new newly change changes changed changing update updates updated updating make
makes made making use uses used using via per plus etc via existing current
support supports supported replace replaces replaced remove removes removed
rather instead including include includes included ensure ensures ensured
""".split())

WORD_RE = re.compile(r"[a-z][a-z0-9\-]{4,}")

# A word held by more than this share of a change's PROMISES is that change's
# subject matter, not a link: in a change about audits, "audit" is in everything.
# The `max(1, ...)` floor below means the effective share is far under 30% on a
# small change — with five promises the ceiling is 1.
COMMON_SHARE = 0.30

# One shared word is a coincidence at this vocabulary size; two is a signal. It
# is still only ever a WEAK link — shown, never counted as coverage.
LEXICAL_MIN = 2

# At most this many wording links per promise, strongest first.
LEXICAL_CAP = 3

# Strongest evidence first. This ordering was spelled three times in three
# encodings — a local RANK dict here, a membership tuple in coverage(), and an
# inverted `order` dict with a silent .get default in render_change — and two of
# them were inverses of each other, so a fifth kind could be added and only one
# would say it had been forgotten.
LINK_KINDS = ("reference", "path", "identifier", "wording")

# Only these discharge a promise. A bullet can MENTION a name without being about
# it, so an identifier or shared wording is shown and never counted.
STRONG_KINDS = frozenset({"reference", "path"})

# Every kind a claim may have. `coverage` scopes ubiquity to promises and falls
# back to all claims when it finds none — so a typo in one producer does not skip
# a branch, it silently restores the all-claims rule the sweep measured wrong.
CLAIM_KINDS = frozenset({"promise", "impact", "requirement", "decision", "goal", "task"})


def content_words(text):
    return {w for w in WORD_RE.findall((text or "").lower()) if w not in STOPWORDS}


def detect_links(claims, caps=()):
    """-> (links, stats). Each link is {src, dst, why, kind}.

    `src` and `dst` are the pair SORTED, not an ordering with meaning: a promise
    and the task implementing it are the same relation read from either end, and
    inventing a direction would have the page assert something the text does not.
    Both consumers add the pair to their adjacency in both directions; the names
    are a historical accident, and this sentence is the only thing that says so.
    """
    by_id = {c["id"]: c for c in claims}
    toks = {c["id"]: tokens_of(c) for c in claims}

    freq = {}
    for cid, ts in toks.items():
        for t in ts:
            freq.setdefault(t, set()).add(cid)
    # Ubiquity is measured over PROMISES, not over every claim. A path named in
    # one promise and twelve tasks is the best evidence a change offers — it says
    # exactly which promise those tasks serve — but counting all thirteen holders
    # made it look like vocabulary and threw it away. Measured across 355 real
    # changes, the all-claims rule left 83% of promises uncovered and 157 changes
    # with nothing covered at all. What disqualifies a token is failing to
    # DISCRIMINATE between the claims that need covering, and only promises need
    # covering.
    promise_ids = {c["id"] for c in claims if c["kind"] == "promise"}
    scope = promise_ids or set(by_id)
    ubiquitous = {t for t, holders in freq.items() if len(holders & scope) > UBIQUITOUS}

    links, seen = [], {}
    # A citation beats a path beats an identifier, and among paths the one with
    # more segments wins. Two claims often share several tokens, and the page
    # shows only one as the reason — keeping whichever arrived first showed
    # `skill.md` where the evidence was `src/legacy/sync-engine/`.
    RANK = {k: len(LINK_KINDS) - i for i, k in enumerate(LINK_KINDS)}

    def add(a, b, why, kind):
        if a == b or a not in by_id or b not in by_id:
            return
        key = (a, b) if a < b else (b, a)
        cur = seen.get(key)
        if cur is None:
            rec = {"src": key[0], "dst": key[1], "why": why, "kind": kind}
            seen[key] = rec
            links.append(rec)               # same object, so an upgrade lands here too
            return
        if ((RANK[kind], why.count("/"), len(why))
                > (RANK[cur["kind"]], cur["why"].count("/"), len(cur["why"]))):
            cur["why"], cur["kind"] = why, kind

    # 1. a token shared by two claims, unless it is shared by everything.
    #    Sorted, so the same change always produces the same page: the tokens
    #    come out of a set, and iterating one directly made which reason got
    #    shown depend on string hashing.
    for tok, holders in sorted(freq.items()):
        if tok in ubiquitous or len(holders) < 2:
            continue
        hs = sorted(holders)
        for i, a in enumerate(hs):
            for b in hs[i + 1:]:
                if by_id[a]["file"] == by_id[b]["file"]:
                    continue          # two tasks naming one file is not evidence
                kind = "path" if "/" in tok or "." in tok else "identifier"
                add(a, b, tok, kind)

    # 2. explicit citations — the only links the text states outright
    for c in claims:
        body = (c.get("raw") or "") + " " + (c.get("body") or "")
        for m in DECISION_REF_RE.finditer(body):
            add(c["id"], claim_id("design", m.group(1)),
                "decision %s" % m.group(1), "reference")
        for m in TASK_REF_RE.finditer(body):
            add(c["id"], claim_id("tasks", m.group(1)),
                "task %s" % m.group(1), "reference")

    # 3. a capability named in the proposal resolves to its own spec delta
    cap_names = {c["name"].lower(): c for c in caps}
    for c in claims:
        if c["kind"] != "requirement":
            continue
        cap = c["file"][len("spec-"):].lower() if c["file"].startswith("spec-") else ""
        if cap not in cap_names:
            continue
        for other in claims:
            if other["kind"] in ("promise",) and cap in (other.get("raw") or "").lower():
                add(other["id"], c["id"], cap, "reference")

    # 4. a requirement's title quoted in a task
    for req in [c for c in claims if c["kind"] == "requirement"]:
        needle = req["text"].lower()
        if len(needle) < 18:
            continue           # too short to identify one requirement
        for t in [c for c in claims if c["kind"] == "task"]:
            if needle in t["text"].lower():
                add(t["id"], req["id"], req["text"], "reference")

    # 5. shared wording, for the half of all promises that name no file and no
    #    identifier — 51% of them across the sweep. The loop runs over EVERY
    #    promise; that half is the motivation for the family, not a filter. Design and
    #    product bullets ("a warm-ink palette", "typography roles") are prose,
    #    and a detector that only reads paths is silent on them. This link is
    #    always WEAK: it is shown so the reader has somewhere to look, and it
    #    never discharges a promise, because sharing two words is a hint and not
    #    a commitment.
    words = {c["id"]: content_words(c.get("raw") or c["text"]) for c in claims}
    # Counted over promises, for the same reason paths are: a word in one promise
    # and fourteen tasks identifies that promise exactly, but counted across all
    # fifteen claims it looks like the change's subject matter and is discarded.
    # What disqualifies a word is appearing in several PROMISES, where it can no
    # longer say which one a task serves.
    wfreq = {}
    for c in claims:
        if c["kind"] != "promise":
            continue
        for w in words[c["id"]]:
            wfreq[w] = wfreq.get(w, 0) + 1
    ceiling = max(1, int(len(promise_ids) * COMMON_SHARE))
    # Capped per promise, and the cap is not cosmetic. Uncapped, one real change
    # produced 162 links, almost all of this kind — a promise carrying twenty
    # counterparts is not a correlation, it is a wall, and the reader stops
    # reading them. Only the strongest few say anything.
    for p in [c for c in claims if c["kind"] == "promise"]:
        cands = []
        for t in [c for c in claims if c["kind"] == "task"]:
            shared = sorted(w for w in words[p["id"]] & words[t["id"]]
                            if wfreq[w] <= ceiling)
            if len(shared) >= LEXICAL_MIN:
                cands.append((len(shared), t["id"], shared))
        for _n, tid, shared in sorted(cands, key=lambda x: (-x[0], x[1]))[:LEXICAL_CAP]:
            add(p["id"], tid, ", ".join(shared[:3]), "wording")

    return links, {"ubiquitous": sorted(ubiquitous), "tokens": len(freq)}


# ---------------------------------------------------------------- coverage


def coverage(claims, links):
    """What covers what, and what nothing covers.

    Two kinds of claim can be *uncovered*: a promise nothing implements, and a
    task not yet done. Impacts, goals, decisions and requirements are context —
    real claims, linkable, shown — but nothing is owed against them.

    **Requirements are deliberately not counted.** Measured on this repo's
    archived change, requiring a task per requirement reported ten of eleven as
    uncovered, which is formally true and useless: in a delta spec the
    requirement operation *is* the change, and the tasks carrying it are the doc
    and test tasks already linked to the promise. Ten warnings buried the two
    real findings. Coverage of the spec is asked at the level the proposal
    actually speaks at — the capability — in `capability_coverage` below.
    """
    by_id = {c["id"]: c for c in claims}
    adj = {}
    for l in links:
        adj.setdefault(l["src"], []).append((l["dst"], l))
        adj.setdefault(l["dst"], []).append((l["src"], l))

    def linked(cid, kind=None):
        out = []
        for other, l in adj.get(cid, []):
            c = by_id.get(other)
            if c and (kind is None or c["kind"] == kind):
                out.append((c, l))
        return out

    tasks_all = [c for c in claims if c["kind"] == "task"]
    done = [t for t in tasks_all if t.get("done")]

    covered, uncovered, unchecked, undone = [], [], [], []
    for c in claims:
        if c["kind"] != "promise":
            continue
        task_links = linked(c["id"], "task")
        # Only a path or an explicit citation discharges a promise. An identifier
        # in common is shown — it is often the useful thing to read — but it does
        # not settle the question, because a bullet can MENTION a name without
        # being about it: the sweep bullet here lists `sync-context` among its
        # candidates and was read as implemented by every task touching that
        # skill. A path names a file the change touches and a citation names its
        # target outright; neither can be a passing mention.
        strong = [p for p in task_links if p[1]["kind"] in STRONG_KINDS]
        weak = [p for p in task_links if p[1]["kind"] not in STRONG_KINDS]
        others = [p for p in linked(c["id"]) if p[0]["kind"] in ("decision", "requirement")]
        if strong:
            covered.append({"claim": c, "pays": strong + weak + others})
        elif tokens_of(c):
            why = "no task names this bullet's file or identifier"
            if weak:
                why += " — %d weaker match%s found, shown below" % (
                    len(weak), "" if len(weak) == 1 else "es")
            uncovered.append({"claim": c, "why": why, "pays": weak + others})
        else:
            # Nothing to match ON. This bullet names no file and no identifier,
            # so the detector has no basis to speak — and saying "uncovered"
            # here would be the overclaim this whole tab exists to avoid.
            # Measured across 355 real changes, half of all promises land here:
            # design and product bullets are prose, and prose is not a link.
            # They are listed, with any shared wording, for the reader to judge.
            unchecked.append({
                "claim": c, "pays": weak + others,
                "why": "no file path or identifier in this bullet to match on"
                       + (" — %d bullet%s share wording with it"
                          % (len(weak), "" if len(weak) == 1 else "s") if weak else ""),
            })
    # A task not yet done is not an uncovered claim, and mixing the two made
    # every summary — the rebuild line, the CLI, the red badge, the rail — report
    # one number for two different things. An unstarted change with 18 tasks read
    # as "18 uncovered", which is the overclaim this module exists to prevent.
    for t in tasks_all:
        if not t["done"]:
            undone.append({"claim": t, "pays": linked(t["id"]),
                           "why": "not done · %d of %d tasks done"
                                  % (len(done), len(tasks_all))})

    return {
        "covered": covered,
        "uncovered": uncovered,
        "unchecked": unchecked,
        "undone": undone,
        # Named here rather than bolted on by build(), so one function owns the
        # complete shape and "did this go through build()?" stops being a
        # question every consumer has to know the answer to.
        "capabilities": [],
        "stats": {"claims": len(claims), "links": len(links),
                  "tasks": len(tasks_all), "tasks_done": len(done),
                  "promises": len([c for c in claims if c["kind"] == "promise"]),
                  "change": "", "files": 0, "ubiquitous": [], "tokens": 0},
    }


def _disambiguate(claims):
    """Make every claim id unique, in place.

    `num` is an ordinal for promises, impacts, goals and requirements — those
    cannot collide. It is AUTHOR-SUPPLIED for tasks and decisions, and both do:
    a task list mixing numbered and unnumbered items produces two `tasks:1`
    (`num` falls back to the running count), and a nested numbered list under
    `## Decisions` produces two `design:1` (the pattern allows three leading
    spaces).

    A duplicate does not crash. It is silently dropped by every
    `{c["id"]: c for c in claims}` downstream, so both claims keep their coverage
    row and their block, while every lookup resolves to whichever won — painting
    one claim's links onto the other's passage. That is the guess `bind_claims`
    refuses to make, arriving through the id layer instead.
    """
    seen = {}
    for c in claims:
        n = seen.get(c["id"], 0)
        seen[c["id"]] = n + 1
        if n:
            c["id"] = "%s#%d" % (c["id"], n + 1)
    return claims


def capability_coverage(caps, texts, claims):
    """The spec side of coverage, asked at the level the proposal speaks at.

    Two failures are real and both are cheap to detect: a capability the proposal
    names with no delta file to change it, and a delta file no capability names.
    Either one means the proposal and the specs disagree about what this change
    touches, which is worth more than ten per-requirement warnings.
    """
    delta_keys = {k[len("spec-"):] for k in texts if k.startswith("spec-")}
    named = {c["name"] for c in caps}
    reqs = {}
    for c in claims:
        if c["kind"] == "requirement":
            reqs.setdefault(c["file"][len("spec-"):], []).append(c)
    rows = []
    for cap in sorted(named | delta_keys):
        rows.append({
            "name": cap,
            "named": cap in named,
            "delta": cap in delta_keys,
            "requirements": reqs.get(cap, []),
            "why": ("named in the proposal, but no specs/%s/spec.md" % cap
                    if cap not in delta_keys else
                    "has a spec delta that no proposal capability names"
                    if cap not in named else ""),
        })
    return rows


def build(change_dir, texts):
    """Everything the page needs. `texts` maps a file key to its raw markdown."""
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
    cov["stats"].update(stats)
    cov["stats"]["change"] = os.path.basename(change_dir)
    cov["stats"]["files"] = len(texts)
    return {"claims": claims, "links": links, "capabilities": caps, "coverage": cov}
