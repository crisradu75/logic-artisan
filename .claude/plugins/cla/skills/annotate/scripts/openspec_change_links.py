"""Links between a change's claims, and what covers what, for `openspec_change.py`.

Four families of link, each carrying the token that produced it, and the
coverage verdict built from them (see the docstring of `openspec_change.py` for
what counts as evidence). Not a command: import it, or use
`openspec_change.py`.
"""

import os
import re

from openspec_change_claims import claim_id


# A token held by more than this many PROMISES is vocabulary rather than
# evidence: past that it cannot say which promise a task serves.
#
# Set from the sweep, not from one change — `sweep_changes.py` over every repo on
# this machine: 355 changes, 2264 promises, covered 22%, uncovered 27%, not
# checkable 51%. On this repo's own archived change the rule never fires at all
# (no token reaches even two promises, and `stats["ubiquitous"]` comes back
# empty), which is exactly why one change cannot set it.
UBIQUITOUS = 4

# An identifier shorter than this does not identify one thing. `cla-init` (a
# skill since merged into `cla-setup`) was eight characters and named a skill
# mentioned all over this repo; matching on it reported a proposal bullet as
# covered because that bullet happened to LIST the skill among sweep candidates. `EXEMPT_SKILLS` is thirteen and does identify one
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
    "readme.md", "claude.md", "agents.md", "spec.md", "proposal.md", "tasks.md", "design.md",
    "skill.md", "todo.md",
})

# Two shapes, because a change names both: a file, which has an extension, and a
# DIRECTORY, which does not. Missing the second is what let `pyproject.toml`
# stand in for `src/legacy/sync-engine/`.
PATH_RE = re.compile(
    r"(?:[\w.\-]+/)*[\w.\-]+\.(?:py|md|mjs|json|toml|ya?ml|sh|cmd|txt|js|ts)\b"
    r"|(?:[\w.\-]+/){2,}[\w.\-]*")
IDENT_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_.\-]+)`")

DECISION_REF_RE = re.compile(r"\b(?:design\s+)?decision\s+(\d+)\b", re.I)
TASK_REF_RE = re.compile(r"\btask\s+(\d+(?:\.\d+)+)\b", re.I)


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
            # A whole-word mention, as capability_coverage counts one: a
            # substring test linked `cla-plugin-extra` promises to `cla-plugin`.
            if other["kind"] in ("promise",) and _mentions(other.get("raw") or "", cap):
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
        # being about it: a sweep bullet here once listed `sync-context` among its
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


def _mentions(text, name):
    """Whether `text` names the capability `name` anywhere, as a whole word.

    A whole word means no letter, digit, underscore, hyphen or slash on either
    side, so `cla-plugin-extra` and `old-cla-plugin` do not mention `cla-plugin`,
    and `identity/user-auth` does not mention a capability called `user-auth` —
    a capability is a path, and a slash joins two segments of one. Case is
    ignored, because prose capitalises a name that a heading spells in lower case.
    """
    pattern = r"(?<![\w/-])" + re.escape(name) + r"(?![\w/-])"
    return re.search(pattern, text or "", re.I) is not None


def capability_coverage(caps, texts, claims):
    """The spec side of coverage, asked at the level the proposal speaks at.

    Two failures are real and both are cheap to detect: a capability the proposal
    names with no delta file to change it, and a delta file the proposal never
    names. Either one means the proposal and the specs disagree about what this
    change touches, which is worth more than ten per-requirement warnings.

    A delta counts as named when the proposal MENTIONS its capability anywhere,
    not only under `## Capabilities`. Most proposals list what they touch under
    `## Impact` instead, and flagging every delta there turned the tab's badge red
    on changes that named every capability they touched. A mention clears the flag and nothing more: it adds no
    row of its own and no link, because naming a capability in passing is not a
    citation.
    """
    delta_keys = {k[len("spec-"):] for k in texts if k.startswith("spec-")}
    named = {c["name"] for c in caps}
    proposal = texts.get("proposal", "")
    reqs = {}
    for c in claims:
        if c["kind"] == "requirement":
            reqs.setdefault(c["file"][len("spec-"):], []).append(c)
    rows = []
    for cap in sorted(named | delta_keys):
        mentioned = _mentions(proposal, cap)
        rows.append({
            "name": cap,
            "named": cap in named,
            "mentioned": mentioned,
            "delta": cap in delta_keys,
            "requirements": reqs.get(cap, []),
            "why": ("named in the proposal, but no specs/%s/spec.md" % cap
                    if cap not in delta_keys else
                    "has a spec delta that no proposal capability names, and the "
                    "proposal never mentions it"
                    if cap not in named and not mentioned else ""),
        })
    return rows
