"""The change page: several files in one page, and what that must not break.

The single-document page already owns anchoring, selection and the corpus. What
is new here is that four files share one page, and two things follow that have
already gone wrong once each: block ids that collide between files, and injected
text that lands inside a block and corrupts every offset counted against it.
"""
import hashlib
import io
import os
import re

import pytest

import openspec_change as OC
import render_change as RC
import render_doc as R


PROPOSAL = """# Proposal: demo

## Why

Because.

## What Changes

- Delete `src/legacy/sync-engine/` entirely
- A warm-ink palette with restrained typography

## Capabilities

### Modified Capabilities

- `cla-plugin`: the sync requirements go away

## Impact

- Consumers stop receiving updates
"""

DESIGN = """# Design: demo

## Context

Words.

## Decisions

1. **Delete outright.** A banner keeps dead code alive.
"""

TASKS = """# Tasks: demo

## 1. Delete

- [x] 1.1 Remove `src/legacy/sync-engine/` via `git rm -r`
- [ ] 1.2 Apply the warm palette and restrained typography
"""

SPEC = """# Delta: cla-plugin — demo

## MODIFIED Requirements

### Requirement: Project-data scaffolding

Text.
"""


@pytest.fixture
def change(tmp_path):
    (tmp_path / ".git").mkdir()
    d = tmp_path / "openspec" / "changes" / "demo"
    (d / "specs" / "cla-plugin").mkdir(parents=True)
    (d / "proposal.md").write_text(PROPOSAL, encoding="utf-8")
    (d / "design.md").write_text(DESIGN, encoding="utf-8")
    (d / "tasks.md").write_text(TASKS, encoding="utf-8")
    (d / "specs" / "cla-plugin" / "spec.md").write_text(SPEC, encoding="utf-8")
    return {"root": str(tmp_path), "dir": str(d)}


@pytest.fixture
def built(change, tmp_path):
    out = str(tmp_path / "page.html")
    path, model, ctxs = RC.build(change["dir"], change["root"], out)
    return {"html": io.open(path, encoding="utf-8").read(), "path": path,
            "model": model, "ctxs": ctxs, **change}


def body_of(html_str):
    """The page with its scripts removed. The anchor layer's own source contains
    `data-blk="` as a string literal, and a scan that counts those reports
    colliding ids that do not exist."""
    return re.sub(r"<script.*?</script>", "", html_str, flags=re.S)


def block_text(html_str, blk):
    """The text of one block as the page's own blockText() would read it: the
    element's contents with every injected class removed."""
    m = re.search(r"<(\w+)([^>]*\bdata-blk=\"%s\")" % re.escape(blk), html_str)
    assert m, "no block %s" % blk
    # The match ends at the attribute, not at the tag — start after the `>`.
    start = html_str.index(">", m.end()) + 1
    tag, i, depth = m.group(1), start, 1
    open_re, close_re = re.compile(r"<%s\b" % tag), re.compile(r"</%s>" % tag)
    while depth and i < len(html_str):
        o, c = open_re.search(html_str, i), close_re.search(html_str, i)
        if o and o.start() < c.start():
            depth += 1
            i = o.end()
        else:
            depth -= 1
            i = c.start() if depth == 0 else c.end()
    inner = html_str[start:i]
    inner = re.sub(r"<(\w+)[^>]*class=\"[^\"]*\b(?:%s)\b[^\"]*\"[^>]*>.*?</\1>"
                   % "|".join(R.INJECTED_CLASSES), "", inner, flags=re.S)
    return " ".join(re.sub(r"<[^>]+>", "", inner).split())


# ---------------------------------------------------------------- invariants


def test_the_change_files_are_never_modified(change):
    before = {}
    for name in ("proposal.md", "design.md", "tasks.md"):
        p = os.path.join(change["dir"], name)
        before[p] = (hashlib.sha256(open(p, "rb").read()).hexdigest(),
                     os.stat(p).st_mtime_ns)
    RC.build(change["dir"], change["root"])
    RC.build(change["dir"], change["root"])
    for p, (digest, mtime) in before.items():
        assert hashlib.sha256(open(p, "rb").read()).hexdigest() == digest
        assert os.stat(p).st_mtime_ns == mtime


def test_block_ids_are_namespaced_per_file(built):
    ids = re.findall(r'data-blk="([^"]+)"', body_of(built["html"]))
    assert len(ids) == len(set(ids)), "colliding block ids across files"
    # Every file restarting at b1 is what made an annotation on the proposal
    # repaint onto the tasks; the prefix is the whole fix.
    assert any(i.startswith("proposal:") for i in ids)
    assert any(i.startswith("tasks:") for i in ids)


def test_section_ids_and_heading_anchors_are_namespaced_too(built):
    secs = re.findall(r'data-sec-id="([^"]+)"', body_of(built["html"]))
    assert len(secs) == len(set(secs))
    heads = re.findall(r'<h[1-6][^>]*\sid="([^"]+)"', body_of(built["html"]))
    assert len(heads) == len(set(heads))


def test_an_inlined_counterpart_is_a_sibling_of_its_block(built):
    """The card carries another file's words. Inside the block they would be
    counted into every offset measured against it, and every annotation below
    would report itself lost against a file nobody had touched."""
    linked = re.findall(r'data-blk="([^"]+)"[^>]*>(?=[^<]*<span class="gut")',
                        built["html"])
    marked = [m for m in re.findall(r'class="linked"[^>]*data-blk="([^"]+)"', built["html"])]
    blks = set(linked) | set(marked)
    assert blks, "no linked block in the fixture — the test would prove nothing"
    for blk in blks:
        f = blk.split(":")[0]
        assert block_text(built["html"], blk) == " ".join(
            built["ctxs"][f].blocks[blk].split()), \
            "block %s reads differently after injection" % blk


def test_the_gutter_is_declared_injected_so_it_is_stripped_before_text_is_read():
    # The gutter IS inside the block, so it only stays harmless while this holds.
    assert "gut" in R.INJECTED_CLASSES
    assert "cf" not in R.INJECTED_CLASSES, "the card is a sibling, not injected"


# ---------------------------------------------------------------- the page


# requirement: annotate / Opening a document for annotation
def test_one_tab_per_file_in_the_fixed_order_plus_coverage(built):
    tabs = re.findall(r'<button class="tab(?: on)?" data-tab="([^"]+)"', built["html"])
    assert tabs == ["proposal", "design", "tasks", "spec-cla-plugin"]
    assert 'data-tab="__coverage__"' in built["html"]
    # The overview comes first, before every file.
    every = re.findall(r'<button class="tab[^"]*" data-tab="([^"]+)"', built["html"])
    assert every == ["__overview__", "proposal", "design", "tasks", "spec-cla-plugin",
                     "__coverage__"]


def _classes_by(html_str, tag, attr):
    """`{attr value: set of classes}` for every `<tag class=… attr=…>`, whatever
    else the tag carries and in whatever order the classes are written."""
    out = {}
    for m in re.finditer(r"<%s\b([^>]*)>" % tag, html_str):
        a = m.group(1)
        v = re.search(r'\b%s="([^"]+)"' % re.escape(attr), a)
        c = re.search(r'\bclass="([^"]*)"', a)
        if v:
            out[v.group(1)] = set(c.group(1).split()) if c else set()
    return out


def test_the_coverage_tab_is_dressed_as_derived_not_as_a_file(built):
    # A reader who takes it for a file goes looking for it on disk.
    tabs = _classes_by(body_of(built["html"]), "button", "data-tab")
    assert {"tab", "tab-cov"} <= tabs["__coverage__"]
    assert {"tab", "tab-cov", "tab-ov"} <= tabs["__overview__"]
    assert "tab-gap" in built["html"]


# requirement: annotate / Opening a document for annotation
def test_the_page_opens_on_the_overview(built):
    """Read from the page source: which pane, rail and tab carry `on` when the
    page loads. Nothing else is shown until a tab is clicked."""
    body = body_of(built["html"])
    for tag, attr in (("div", "data-pane"), ("div", "data-rail"), ("button", "data-tab")):
        on = [k for k, cls in _classes_by(body, tag, attr).items() if "on" in cls]
        assert on == ["__overview__"], (attr, on)
    css = "".join(re.findall(r"<style>(.*?)</style>", built["html"], flags=re.S))
    assert ".pane{display:none}" in css and ".pane.on{display:block}" in css


def _overview_pane(html_str):
    pane = html_str.split('data-pane="__overview__">', 1)[1]
    return pane[:pane.index('<div class="pane" data-pane=')]


def test_nothing_in_the_overview_can_be_annotated(built):
    """Derived data, like the coverage pane: a block in it would be an
    annotation target with no source line behind it."""
    assert "data-blk=" not in _overview_pane(body_of(built["html"]))


def test_every_overview_link_lands_on_a_block(built):
    pane = _overview_pane(body_of(built["html"]))
    targets = re.findall(r'class="cov-go" data-go-blk="([^"]+)"', pane)
    assert targets, "no promise in the overview links back"
    for blk in targets:
        assert 'data-blk="%s"' % blk in built["html"], blk


def _promise_rows(pane):
    """`{promise text start: set of chip classes}` from the overview's list."""
    out = {}
    for li in re.findall(r'<li class="ov-p">(.*?)</li>', pane, flags=re.S):
        chips = set(re.findall(r'class="ov-chip (ov-[\w-]+)"', li))
        text = re.sub(r"<[^>]+>", " ", li).split()
        words = [w for w in text if w.lower() not in
                 ("covered", "uncovered", "not", "checkable", "breaking")]
        out[" ".join(words[:3])] = chips
    return out


def _cap_status(pane):
    """`{capability: status chip}` from the overview's requirements table."""
    return dict(re.findall(r'<code>([^<]+)</code></td><td><span class="ov-chip ov-[\w-]+">'
                           r'([\w-]+)</span>', pane))


def test_the_overview_chips_carry_each_promises_bucket(built):
    pane = _overview_pane(body_of(built["html"]))
    rows = _promise_rows(pane)
    assert rows["Delete src/legacy/sync-engine/ entirely"] == {"ov-covered"}
    assert rows["A warm-ink palette"] == {"ov-unchecked"}
    assert "<th>renamed</th>" not in pane, "a renamed column with nothing in it"
    assert _cap_status(pane) == {"cla-plugin": "new"}, \
        "no main spec in this fixture, so the capability reads as new"
    # Each rail entry jumps to a heading that is there.
    rail = built["html"].split('data-rail="__overview__"', 1)[1].split("</div>", 1)[0]
    anchors = re.findall(r'href="#([^"]+)"', rail)
    assert anchors == ["ov-promises", "ov-requirements", "ov-tasks"]
    for a in anchors:
        assert 'id="%s"' % a in pane, a


def test_a_breaking_promise_and_a_rename_show_in_the_overview(change, tmp_path):
    prop = PROPOSAL.replace("- Delete `src/legacy/sync-engine/` entirely",
                            "- **BREAKING** Delete `src/legacy/sync-engine/` entirely")
    with open(os.path.join(change["dir"], "proposal.md"), "w", encoding="utf-8") as fh:
        fh.write(prop)
    with open(os.path.join(change["dir"], "specs", "cla-plugin", "spec.md"), "w",
              encoding="utf-8") as fh:
        fh.write(SPEC + "\n## RENAMED Requirements\n\n- FROM: `### Requirement: A`\n"
                 "- TO: `### Requirement: B`\n")
    html_str, _m, _c = _rebuild(change, tmp_path, "brk.html")
    pane = _overview_pane(body_of(html_str))
    rows = _promise_rows(pane)
    assert rows["Delete src/legacy/sync-engine/ entirely"] == {"ov-covered", "ov-breaking"}
    assert rows["A warm-ink palette"] == {"ov-unchecked"}
    assert "<th>renamed</th>" in pane


def test_skip_specs_shows_in_the_overview_and_quiets_coverage(change, tmp_path):
    import shutil
    shutil.rmtree(os.path.join(change["dir"], "specs"))
    with open(os.path.join(change["dir"], ".openspec.yaml"), "w", encoding="utf-8") as fh:
        fh.write("schema: spec-driven\nskip_specs: true\n")
    html_str, model, _c = _rebuild(change, tmp_path, "skip.html")
    assert "no spec changes (skip_specs)" in _overview_pane(body_of(html_str))
    assert not [r for r in model["coverage"]["capabilities"] if r["why"]]


def test_skip_specs_beside_real_deltas_shows_both_and_says_they_conflict(change, tmp_path):
    """OpenSpec's validate refuses this combination. Hiding the deltas behind
    the flag would show the reader an empty change that is not empty."""
    with open(os.path.join(change["dir"], ".openspec.yaml"), "w", encoding="utf-8") as fh:
        fh.write("schema: spec-driven\nskip_specs: true\n")
    html_str, _m, _c = _rebuild(change, tmp_path, "conflict.html")
    pane = _overview_pane(body_of(html_str))
    assert "conflict · .openspec.yaml sets skip_specs, but this change has spec deltas" in pane
    assert _cap_status(pane) == {"cla-plugin": "new"}
    assert "no spec changes (skip_specs)" not in pane


def test_the_overview_says_nothing_parsed_and_what_it_looked_for(change, tmp_path):
    """An empty heading reads as an empty change. Each part that gave nothing
    says so, and names what was looked for."""
    with open(os.path.join(change["dir"], "proposal.md"), "w", encoding="utf-8") as fh:
        fh.write("# Proposal\n\n## Impact\n\n- `cla-plugin`: changes\n")
    os.remove(os.path.join(change["dir"], "tasks.md"))
    html_str, _m, _c = _rebuild(change, tmp_path, "empty.html")
    pane = _overview_pane(body_of(html_str))
    assert "nothing parsed · the proposal has no ## Why section" in pane
    assert "nothing parsed · no top-level bullets under the proposal&#x27;s ## What Changes" \
        in pane or "nothing parsed · no top-level bullets under the proposal's ## What Changes" \
        in pane
    assert "nothing parsed · this change has no tasks.md" in pane
    with open(os.path.join(change["dir"], "proposal.md"), "w", encoding="utf-8") as fh:
        fh.write("# Proposal\n\n## Why\n\n## What Changes\n\n- one\n")
    with open(os.path.join(change["dir"], "tasks.md"), "w", encoding="utf-8") as fh:
        fh.write("# Tasks\n\n## 1. Work\n\nNo boxes here.\n")
    html_str, _m, _c = _rebuild(change, tmp_path, "empty2.html")
    pane = _overview_pane(body_of(html_str))
    assert "## Why section is empty" in pane
    assert "nothing parsed · tasks.md holds no task lines" in pane


def test_a_promise_cut_short_says_so(change, tmp_path):
    long = "- Delete `src/legacy/sync-engine/` " + "and more words " * 40 + "\n"
    prop = PROPOSAL.replace("- Delete `src/legacy/sync-engine/` entirely\n", long)
    with open(os.path.join(change["dir"], "proposal.md"), "w", encoding="utf-8") as fh:
        fh.write(prop)
    html_str, _m, _c = _rebuild(change, tmp_path, "long.html")
    li = [x for x in re.findall(r'<li class="ov-p">(.*?)</li>', _overview_pane(body_of(html_str)))
          if "sync-engine" in x][0]
    assert re.search(r"…</span>$", li)


def test_each_file_gets_its_own_rail(built):
    rails = re.findall(r'data-rail="([^"]+)"', built["html"])
    assert set(rails) == {"__overview__", "proposal", "design", "tasks", "spec-cla-plugin",
                          "__coverage__"}


def test_the_page_is_self_contained(built):
    assert re.findall(r'(?:src|href)="(https?://[^"]+)"', built["html"]) == []


def test_the_page_opens_in_light_mode(built):
    assert '<html lang="en" data-theme="light">' in built["html"]


def test_the_change_key_reaches_the_page(built):
    assert 'const DOC = "openspec/changes/demo"' in built["html"]


def test_the_bar_reports_files_blocks_and_words(built):
    assert re.search(r"4 files · \d+ blocks · [\d,]+ words", built["html"])


# ---------------------------------------------------------------- coverage pane


def test_the_coverage_pane_carries_all_three_groups(built):
    pane = built["html"].rsplit('data-pane="__coverage__"', 1)[1]
    assert "Uncovered" in pane and "Not checkable" in pane and "Covered" in pane


def test_a_prose_bullet_lands_in_not_checkable_rather_than_uncovered(built):
    cov = built["model"]["coverage"]
    assert any("warm-ink palette" in r["claim"]["text"] for r in cov["unchecked"])
    assert not any("warm-ink palette" in r["claim"]["text"] for r in cov["uncovered"])


def test_coverage_rows_link_back_to_the_passage_they_were_read_from(built):
    pane = built["html"].rsplit('data-pane="__coverage__"', 1)[1]
    targets = re.findall(r'class="cov-go[^"]*" data-go-blk="([^"]+)"', pane)
    assert targets, "no coverage row is clickable"
    for blk in targets:
        assert 'data-blk="%s"' % blk in built["html"], "row points at no block"


def test_a_claim_with_no_block_degrades_to_text_rather_than_a_dead_link(built):
    """A link that scrolls somewhere arbitrary is worse than none, because it is
    believed."""
    html_str = RC.coverage_pane(
        {"coverage": {"uncovered": [{"claim": {"file": "proposal", "kind": "promise",
                                               "num": "p9", "text": "unbound", "blk": None},
                                     "why": "x", "pays": []}],
                      "unchecked": [], "covered": [], "undone": [], "capabilities": [],
                      "stats": {"files": 1, "claims": 1, "links": 0, "promises": 1,
                                "tasks": 0, "tasks_done": 0}}},
        {"proposal": "proposal"})
    assert 'class="cov-dead"' in html_str
    assert "data-go-blk" not in html_str


def test_the_provenance_line_states_what_was_read(built):
    pane = built["html"].rsplit('data-pane="__coverage__"', 1)[1]
    # Not `\d+` for the counts that matter: `\d+` matches 0, so the line passed
    # with every link destroyed.
    assert re.search(r"read 4 files · 2 promises · [1-9]\d* claims · [1-9]\d* links", pane)


# ---------------------------------------------------------------- binding


def test_claims_bind_to_the_block_holding_their_text(built):
    bound = [c for c in built["model"]["claims"] if c.get("blk")]
    assert bound, "nothing bound"
    for c in bound:
        assert c["blk"].startswith(c["file"] + ":")
        assert c["text"][:70] in built["ctxs"][c["file"]].blocks[c["blk"]]


def test_an_ambiguous_claim_binds_to_nothing(change, tmp_path):
    # Two identical bullets: binding either one is a guess, and a guess sends the
    # reader to the wrong passage while showing text that looks right.
    dupe = PROPOSAL.replace(
        "- A warm-ink palette with restrained typography",
        "- Same words here\n- Same words here")
    (tmp_path / "openspec" / "changes" / "demo" / "proposal.md").write_text(
        dupe, encoding="utf-8")
    _p, model, _c = RC.build(change["dir"], change["root"], str(tmp_path / "p.html"))
    same = [c for c in model["claims"] if c["text"] == "Same words here"]
    assert len(same) == 2 and all(c["blk"] is None for c in same)


def test_a_weak_link_is_marked_weak_wherever_it_shows(built):
    if 'class="cf weak"' not in built["html"]:
        pytest.skip("fixture produced no wording link")
    assert 'class="weak"' in built["html"]      # the gutter mark too


# ---------------------------------------------------------------- discovery


def test_build_refuses_a_directory_that_is_not_a_change(tmp_path):
    """A real exception, never SystemExit. SystemExit is a BaseException: raised
    in the server's worker thread it is caught by nothing and swallowed by
    `threading`, so the reader saw the browser's generic "Failed to fetch" and
    the server printed nothing at all."""
    empty = tmp_path / "nothing"
    empty.mkdir()
    with pytest.raises(RC.ChangeUnreadable):
        RC.build(str(empty), str(tmp_path))
    assert not issubclass(RC.ChangeUnreadable, SystemExit)


def test_a_nested_capability_delta_gets_its_own_tab(change, tmp_path):
    nested = os.path.join(change["dir"], "specs", "identity", "user-auth")
    os.makedirs(nested)
    with open(os.path.join(nested, "spec.md"), "w", encoding="utf-8") as fh:
        fh.write(SPEC)
    path, _model, ctxs = RC.build(change["dir"], change["root"], str(tmp_path / "n.html"))
    html_str = io.open(path, encoding="utf-8").read()
    assert 'data-tab="spec-identity/user-auth"' in html_str
    assert "spec · identity/user-auth" in html_str
    assert all(b.startswith("spec-identity/user-auth:") for b in ctxs["spec-identity/user-auth"].blocks)


def test_find_change_accepts_a_directory_path(change):
    assert OC.find_change(change["dir"], change["root"]) == change["dir"]


# ---------------------------------------------------------------- the seam with render_doc


def test_the_tabbed_shell_actually_replaces_render_docs_reading_column(built):
    """This build takes render_doc's whole page and swaps one run of markup for
    its own tabs, panes and rails. That is a string match against another
    module's output — the coupling that breaks with no symptom.

    A missed match leaves render_doc's EMPTY column in the page and drops every
    pane on the floor, and the page still renders: a bar, a rail, a theme
    toggle, and no document."""
    html = built["html"]
    assert '<div class="col" id="doc"></div>' not in html, \
        "render_doc's empty reading column survived; the substitution did not fire"
    assert html.count('<div class="pane') >= 3
    assert '<div class="panes" id="doc">' in html


def test_the_substitution_refuses_rather_than_silently_doing_nothing(change, monkeypatch):
    """The guard, exercised. Left unguarded, a divergence turns `str.replace`
    into a no-op and the failure is a blank page nobody can attribute.

    Patching SHELL_MARKUP alone cannot make this fire, and that is the refactor
    working: both sides read the one constant, so they cannot disagree about it.
    What the guard still has to catch is `page()` no longer emitting it — a
    wrapper around the column, a renamed class, an id moved — so that is what is
    simulated here."""
    real = R.page
    monkeypatch.setattr(
        R, "page",
        lambda *a, **k: real(*a, **k).replace('<div class="wrap">',
                                              '<div class="wrap" data-v2="1">'))
    with pytest.raises(RC.ChangeUnreadable) as e:
        RC.build(change["dir"], change["root"])
    assert "shell markup" in str(e.value)


def test_the_panes_and_the_margin_share_one_reading_grid(built):
    """The annotation margin takes the second track. `.col` inside a pane is not
    a DIRECT child of `.wrap`, so the sizing that neutralises the standalone
    page's centred 44rem measure has to be restated here — or every pane
    overflows its own track."""
    html = built["html"]
    assert '<div class="gutter" id="gutter"' in html
    css = "".join(re.findall(r"<style>(.*?)</style>", html, flags=re.S))
    assert ".panes .col{max-width:none" in css
    # Two rules, two different failures. Without `.panes .col` every pane keeps
    # the standalone page's centred 44rem measure inside a 40rem track; without
    # `min-width:0` the grid track refuses to shrink below its content and the
    # pane overflows it. Only the first was asserted.
    assert ".wrap>.panes{min-width:0}" in css


# ---------------------------------------------------------------- requirement groups


# The ADDED group comes LAST, straight after the removed ones, as it does in real
# changes: that is where a removed span that does not stop at the next group
# heading would swallow a live requirement.
GROUPED_SPEC = """# Delta: cla-plugin — demo

## MODIFIED Requirements

### Requirement: Project-data scaffolding

Text.

## REMOVED Requirements

### Requirement: Old rule one

**Reason**: Folded into another rule.
**Migration**: Nothing to do.

### Requirement: Old rule two

**Reason**: Folded into another rule.

#### Scenario: A scenario of the removed rule

- **WHEN** it ran
- **THEN** it did

## ADDED Requirements

### Requirement: A fresh rule

Reason enough to add it is stated here, but this block is live text.

#### Scenario: It applies

- **WHEN** it runs
- **THEN** it works
"""


@pytest.fixture
def grouped(change, tmp_path):
    spec = os.path.join(change["dir"], "specs", "cla-plugin", "spec.md")
    with open(spec, "w", encoding="utf-8") as fh:
        fh.write(GROUPED_SPEC)
    out = str(tmp_path / "grouped.html")
    path, model, ctxs = RC.build(change["dir"], change["root"], out)
    return {"html": io.open(path, encoding="utf-8").read(), "model": model, "ctxs": ctxs}


def _heading(grouped, title):
    ctx = grouped["ctxs"]["spec-cla-plugin"]
    hits = [b for b, t in ctx.blocks.items() if t == "Requirement: " + title]
    assert len(hits) == 1, title
    return hits[0]


def _open_tag(html_str, blk):
    m = re.search(r'<\w+[^>]*\bdata-blk="%s"[^>]*>' % re.escape(blk), html_str)
    assert m, blk
    return m.group(0)


def _section_html(html_str, blk):
    """The `<section>` holding a block, opening tag included."""
    i = html_str.index('data-blk="%s"' % blk)
    start = html_str.rindex("<section ", 0, i)
    return html_str[start:html_str.index("</section>", i)]


# requirement: annotate / Reviewing a change shows how each requirement changes the current spec
def test_each_requirement_heading_carries_its_group(grouped):
    html_str = body_of(grouped["html"])
    for title, group in (("A fresh rule", "ADDED"), ("Project-data scaffolding", "MODIFIED"),
                         ("Old rule one", "REMOVED"), ("Old rule two", "REMOVED")):
        assert 'data-group="%s"' % group in _open_tag(html_str, _heading(grouped, title)), title
    # That the label is DRAWN is a question for a browser: the computed
    # `::before` content is checked in test_page_in_a_browser.py.


def test_a_labelled_heading_reads_the_same_text_as_before(grouped):
    """The label is drawn by CSS from an attribute. Written into the heading, its
    word would be counted into every offset measured against that block."""
    html_str = body_of(grouped["html"])
    ctx = grouped["ctxs"]["spec-cla-plugin"]
    for title in ("A fresh rule", "Project-data scaffolding", "Old rule one", "Old rule two"):
        blk = _heading(grouped, title)
        assert block_text(html_str, blk) == " ".join(ctx.blocks[blk].split())


# requirement: annotate / Reviewing a change shows how each requirement changes the current spec
def test_a_removed_requirement_and_its_scenarios_are_set_apart(grouped):
    html_str = body_of(grouped["html"])
    ctx = grouped["ctxs"]["spec-cla-plugin"]
    two = _section_html(html_str, _heading(grouped, "Old rule two"))
    assert 'class="sec req-removed"' in two
    # Its scenario is a level-4 section of its own, and is just as removed.
    scen = [b for b, t in ctx.blocks.items() if t == "Scenario: A scenario of the removed rule"][0]
    assert 'class="sec req-removed"' in _section_html(html_str, scen)
    # The live requirements are not.
    for title in ("A fresh rule", "Project-data scaffolding"):
        assert "req-removed" not in _section_html(html_str, _heading(grouped, title)), title


def test_the_reason_block_of_every_removed_requirement_is_marked(grouped):
    """Found by section, never by text: both removed requirements give the same
    reason word for word, and a text match would mark one or neither."""
    html_str = body_of(grouped["html"])
    ctx = grouped["ctxs"]["spec-cla-plugin"]
    reasons = [b for b, t in ctx.blocks.items() if t.startswith("Reason: Folded")]
    assert len(reasons) == 2
    for b in reasons:
        assert "rm-why" in _open_tag(html_str, b)
        assert block_text(html_str, b) == " ".join(ctx.blocks[b].split())
    # A live requirement's paragraph that happens to start with the word is not.
    live = [b for b, t in ctx.blocks.items() if t.startswith("Reason enough")][0]
    assert "rm-why" not in _open_tag(html_str, live)


def test_the_group_label_is_not_injected_text():
    # It is an attribute, so nothing has to be stripped before text is read.
    assert not any("group" in c for c in R.INJECTED_CLASSES)


def test_add_attr_replaces_rather_than_duplicates():
    html_str = '<h3 data-group="ADDED" data-blk="x:b1" id="h">T</h3>'
    out = RC.add_attr(html_str, "x:b1", "data-group", "REMOVED")
    assert out.count("data-group=") == 1 and 'data-group="REMOVED"' in out


# ---------------------------------------------------------------- requirement diffs


MAIN_SPEC = """# cla-plugin Specification

## Requirements

### Requirement: Project-data scaffolding

Old words here.
"""


def _main_spec(change, data):
    d = os.path.join(change["root"], "openspec", "specs", "cla-plugin")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "spec.md"), "wb") as fh:
        fh.write(data)


def _rebuild(change, tmp_path, name="diff.html"):
    path, model, ctxs = RC.build(change["dir"], change["root"], str(tmp_path / name))
    return io.open(path, encoding="utf-8").read(), model, ctxs


def _req_heading(ctxs):
    ctx = ctxs["spec-cla-plugin"]
    return [b for b, t in ctx.blocks.items() if t == "Requirement: Project-data scaffolding"][0]


# requirement: annotate / Reviewing a change shows how each requirement changes the current spec
def test_a_modified_requirement_shows_its_diff_under_its_heading(change, tmp_path):
    _main_spec(change, MAIN_SPEC.encode("utf-8"))
    html_str, _model, ctxs = _rebuild(change, tmp_path)
    body = body_of(html_str)
    blk = _req_heading(ctxs)
    # Directly after the heading, as a sibling of it.
    after = body[body.index('data-blk="%s"' % blk):]
    after = after[after.index("</h3>") + len("</h3>"):]
    assert after.startswith('<div class="rd">'), after[:120]
    card = after[:after.index("</div>")]
    assert '<span class="rd-del">Old words here.</span>' in card
    assert '<span class="rd-ins">Text.</span>' in card
    assert block_text(body, blk) == " ".join(ctxs["spec-cla-plugin"].blocks[blk].split())


def test_a_main_spec_is_not_a_tab_and_not_a_file(change, tmp_path):
    _main_spec(change, MAIN_SPEC.encode("utf-8"))
    html_str, _model, _ctxs = _rebuild(change, tmp_path)
    assert re.search(r"4 files · \d+ blocks", html_str)
    assert "Old words here" not in "".join(re.findall(r'data-tab="[^"]+"', html_str))


def test_an_unreadable_main_spec_still_builds_and_says_so(change, tmp_path):
    _main_spec(change, b"## Requirements\n\n\xff\xfe broken\n")
    html_str, model, _ctxs = _rebuild(change, tmp_path)
    assert [r["state"] for r in model["diffs"].values()] == ["unreadable"]
    assert '<div class="rd rd-note">' in html_str
    assert "could not be read: not valid UTF-8" in html_str


# requirement: annotate / Reviewing a change shows how each requirement changes the current spec
def test_an_archived_change_shows_no_base_rather_than_unchanged(tmp_path):
    (tmp_path / ".git").mkdir()
    d = tmp_path / "openspec" / "changes" / "archive" / "2026-01-01-demo"
    (d / "specs" / "cla-plugin").mkdir(parents=True)
    (d / "proposal.md").write_text(PROPOSAL, encoding="utf-8")
    (d / "specs" / "cla-plugin" / "spec.md").write_text(SPEC, encoding="utf-8")
    # The main spec holds the archived change's own text, as archiving leaves it.
    main = tmp_path / "openspec" / "specs" / "cla-plugin"
    main.mkdir(parents=True)
    (main / "spec.md").write_text(SPEC.replace("## MODIFIED Requirements", "## Requirements"),
                                  encoding="utf-8")
    assert RC.is_archived(str(d))
    path, model, _c = RC.build(str(d), str(tmp_path), str(tmp_path / "a.html"))
    html_str = io.open(path, encoding="utf-8").read()
    assert [r["state"] for r in model["diffs"].values()] == ["archived"]
    assert "no base · this change is archived" in html_str
    assert "unchanged · " not in html_str
    # Its main specs are never read, so whether the capability was new or
    # modified is not known — and the chip says that, not "modified".
    assert _cap_status(_overview_pane(body_of(html_str))) == {"cla-plugin": "unknown"}


def test_the_main_spec_is_found_beside_the_change_not_at_the_repo_root(tmp_path):
    """A change may live in a store of its own. Its main specs are the ones in
    the same `openspec/` folder as the change, whatever the repo root is."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    store_dir = tmp_path / "store" / "openspec"
    d = store_dir / "changes" / "demo"
    (d / "specs" / "cla-plugin").mkdir(parents=True)
    (d / "proposal.md").write_text(PROPOSAL, encoding="utf-8")
    (d / "specs" / "cla-plugin" / "spec.md").write_text(SPEC, encoding="utf-8")
    (store_dir / "specs" / "cla-plugin").mkdir(parents=True)
    (store_dir / "specs" / "cla-plugin" / "spec.md").write_text(MAIN_SPEC, encoding="utf-8")
    # A decoy at the repo root, which must not be the one read.
    (repo / "openspec" / "specs" / "cla-plugin").mkdir(parents=True)
    (repo / "openspec" / "specs" / "cla-plugin" / "spec.md").write_text(
        MAIN_SPEC.replace("Old words here.", "Decoy."), encoding="utf-8")
    path, model, _c = RC.build(str(d), str(repo), str(tmp_path / "s.html"))
    html_str = io.open(path, encoding="utf-8").read()
    assert [r["state"] for r in model["diffs"].values()] == ["diff"]
    assert '<span class="rd-del">Old words here.</span>' in html_str
    # The card names the file it actually read, not the repo-relative guess.
    assert "changes against %s" % (store_dir / "specs" / "cla-plugin" / "spec.md").as_posix() \
        in html_str
    assert RC.main_specs_dir(str(d / "x" / "..")) == str(store_dir / "specs")
    arch = store_dir / "changes" / "archive" / "2026-01-01-demo"
    assert RC.main_specs_dir(str(arch)) == str(store_dir / "specs")


def test_a_change_folder_outside_changes_has_no_main_specs(tmp_path):
    """Neither openspec/changes/<id> nor its archive: there is no main specs
    folder that belongs to it, and borrowing the repo's would compare against
    a spec from another store."""
    (tmp_path / ".git").mkdir()
    d = tmp_path / "loose" / "demo"
    (d / "specs" / "cla-plugin").mkdir(parents=True)
    (d / "proposal.md").write_text(PROPOSAL, encoding="utf-8")
    (d / "specs" / "cla-plugin" / "spec.md").write_text(SPEC, encoding="utf-8")
    (tmp_path / "openspec" / "specs" / "cla-plugin").mkdir(parents=True)
    (tmp_path / "openspec" / "specs" / "cla-plugin" / "spec.md").write_text(
        MAIN_SPEC, encoding="utf-8")
    assert RC.main_specs_dir(str(d)) is None
    path, model, _c = RC.build(str(d), str(tmp_path), str(tmp_path / "loose.html"))
    html_str = io.open(path, encoding="utf-8").read()
    assert [r["state"] for r in model["diffs"].values()] == ["no-main-spec"]
    assert "no base · this change folder is not under openspec/changes/" in html_str
    assert "Old words here" not in html_str


def test_the_archive_folder_is_recognised_in_any_case_where_the_os_folds_case(tmp_path):
    d = tmp_path / "openspec" / "Changes" / "Archive" / "2026-01-01-demo"
    expected = os.path.normcase("Changes") == os.path.normcase("changes")
    assert RC.is_archived(str(d)) is expected
    if expected:
        assert RC.main_specs_dir(str(d)) == str(tmp_path / "openspec" / "specs")


def test_an_unchanged_requirement_claims_only_what_was_compared(change, tmp_path):
    _main_spec(change, MAIN_SPEC.replace("Old words here.", "Text.").encode("utf-8"))
    html_str, model, _c = _rebuild(change, tmp_path, "same.html")
    assert [r["state"] for r in model["diffs"].values()] == ["same"]
    assert "no word-level difference from openspec/specs/cla-plugin/spec.md" in html_str
    assert "unchanged" not in body_of(html_str).split('data-pane="spec-cla-plugin"', 1)[1]


def test_a_requirement_that_cannot_be_placed_is_listed_not_dropped(change, tmp_path):
    """Two headings with one name: neither can carry the label or the diff
    without guessing, so both go to the coverage pane with the reason."""
    twice = SPEC + "\n### Requirement: Project-data scaffolding\n\nAgain.\n"
    with open(os.path.join(change["dir"], "specs", "cla-plugin", "spec.md"), "w",
              encoding="utf-8") as fh:
        fh.write(twice)
    _main_spec(change, MAIN_SPEC.encode("utf-8"))
    html_str, model, _c = _rebuild(change, tmp_path, "unplaced.html")
    rows = model["unplaced"]
    assert {r["why"] for r in rows} == {"heading not unique"}
    assert all(set(r["what"]) == {"label", "diff"} for r in rows)
    cov = html_str.rsplit('data-pane="__coverage__"', 1)[1]
    assert "Not placed — 2" in cov
    assert "its label and diff could not be placed: heading not unique" in cov
    assert 'data-group="MODIFIED"' not in body_of(html_str)


def test_a_heading_with_a_closing_hash_run_still_carries_its_label(change, tmp_path):
    closed = SPEC.replace("### Requirement: Project-data scaffolding",
                          "### Requirement: Project-data scaffolding ###")
    with open(os.path.join(change["dir"], "specs", "cla-plugin", "spec.md"), "w",
              encoding="utf-8") as fh:
        fh.write(closed)
    html_str, model, _c = _rebuild(change, tmp_path, "closed.html")
    assert 'data-group="MODIFIED"' in body_of(html_str)
    assert not model.get("unplaced")


def test_an_active_change_is_not_archived(change):
    assert not RC.is_archived(change["dir"])


def test_a_counterpart_is_clamped_to_two_lines_until_opened(built):
    css = "".join(re.findall(r"<style>(.*?)</style>", built["html"], flags=re.S))
    assert (".cf-x{display:-webkit-box;-webkit-box-orient:vertical;"
            "-webkit-line-clamp:2;") in css
    assert ".cf.open .cf-x{display:block}" in css
    body = body_of(built["html"])
    cards = len(re.findall(r'<span class="cf(?: weak)?">', body))
    assert cards, "no counterpart in the fixture — the test would prove nothing"
    assert body.count('<span class="cf-x" role="button" tabindex="0" '
                      'aria-expanded="false">') == cards


@pytest.mark.parametrize("control", ["showTab", "cf-toggle", "toggleCf"])
def test_every_flow_changing_control_here_relays_the_margin(built, control):
    """Switching tabs swaps one whole document for another and hiding the
    counterparts moves a pane by hundreds of pixels — measured at 871px on a real
    change. Opening one counterpart moves every block below it. A margin top is
    an absolute pixel computed once, so each has to re-lay-out the notes or
    every tie points at the wrong line."""
    script = "".join(re.findall(r"<script>(.*?)</script>", built["html"], flags=re.S))
    if control in ("showTab", "toggleCf"):
        block = script[script.index("function %s(" % control):]
        block = block[:block.index("\n}")]
    else:
        block = script[script.index("cfBtn.onclick"):]
        block = block[:block.index("\n};")]
    # The whole STATEMENT, not the substring. `if (false) syncMargin();` still
    # contains "syncMargin()", so a presence check reads a dead call as a live
    # one — measured, it survives here at both call sites. The doc page's
    # equivalent check was strengthened for exactly this and this twin, written
    # in the same commit, was left as a presence check.
    assert re.search(r"^\s*syncMargin\(\);", block, flags=re.M), \
        "%s does not call syncMargin unconditionally" % control
