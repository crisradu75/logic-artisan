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


def test_one_tab_per_file_in_the_fixed_order_plus_coverage(built):
    tabs = re.findall(r'<button class="tab(?: on)?" data-tab="([^"]+)"', built["html"])
    assert tabs == ["proposal", "design", "tasks", "spec-cla-plugin"]
    assert 'data-tab="__coverage__"' in built["html"]


def test_the_coverage_tab_is_dressed_as_derived_not_as_a_file(built):
    # A reader who takes it for a file goes looking for it on disk.
    assert 'class="tab tab-cov"' in built["html"]
    assert "tab-gap" in built["html"]


def test_only_the_first_pane_and_rail_start_visible(built):
    assert built["html"].count('class="pane on"') == 1
    assert built["html"].count('class="rail-wrap on"') == 1


def test_each_file_gets_its_own_rail(built):
    rails = re.findall(r'data-rail="([^"]+)"', built["html"])
    assert set(rails) == {"proposal", "design", "tasks", "spec-cla-plugin", "__coverage__"}


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
                      "unchecked": [], "covered": [], "capabilities": [],
                      "stats": {"files": 1, "claims": 1, "links": 0,
                                "tasks": 0, "tasks_done": 0}}},
        {"proposal": "proposal"})
    assert 'class="cov-dead"' in html_str
    assert "data-go-blk" not in html_str


def test_the_provenance_line_states_what_was_read(built):
    pane = built["html"].rsplit('data-pane="__coverage__"', 1)[1]
    assert re.search(r"read 4 files · \d+ claims · \d+ links", pane)


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
    empty = tmp_path / "nothing"
    empty.mkdir()
    with pytest.raises(SystemExit):
        RC.build(str(empty), str(tmp_path))


def test_find_change_accepts_a_directory_path(change):
    assert OC.find_change(change["dir"], change["root"]) == change["dir"]
