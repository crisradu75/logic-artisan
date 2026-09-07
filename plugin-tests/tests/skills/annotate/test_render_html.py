"""Tests for `render_html.py` — the block rule, the two refusals, and the
reversibility property.

The reversibility test is the load-bearing one. Every other check here asks
whether the instrumentation did the right thing; that one asks whether it did
anything ELSE, which is the failure a reader could never see.
"""

import io
import os
import re

import pytest

import render_html as RH


# The motivating document lives in a peer repo and carries real financial
# figures, so it is never copied into this repo. It is referenced by path and
# skipped when absent — no test depends on it, and no run leaks it.
BRIEFING = r"C:\Code\interoga-ro\docs\business\briefing-partener-2026-09-07.html"


def has_briefing():
    return os.path.isfile(BRIEFING)


# --------------------------------------------------------------- fixtures

# Reproduces the SHAPES that matter, none of the content:
#   - a waterfall row whose only non-inline child is EMPTY
#   - an inline <svg> with text labels
#   - a top-level <style>
#   - a <header> whose tag name is a prefix of an excluded one
#   - a table, entities, and nested inline markup
SHAPES = """\
<!-- a comment -->
<meta charset="utf-8">
<title>Tab label</title>
<style>
  .wf-row { display:grid }
  .bar { height:.7rem }
</style>
<header class="masthead"><p class="kicker">Kicker text</p></header>
<h2>First section</h2>
<p>A paragraph with <strong>bold</strong> and an &amp; entity.</p>
<div class="waterfall">
  <div class="wf-row"><span class="lbl">Row label</span><div class="bar" style="width:2%"></div><span class="amt">&minus;0,99</span></div>
</div>
<figure>
  <svg viewBox="0 0 10 10"><g><text>Alpha</text><text>Beta</text></g></svg>
  <figcaption>A caption</figcaption>
</figure>
<h3>Second section</h3>
<table><thead><tr><th>Head</th></tr></thead><tbody><tr><td>Cell</td></tr></tbody></table>
<ul><li>Item one</li><li>Item two</li></ul>
<noscript>Enable scripting</noscript>
"""


def blocks_of(src):
    _, ctx, _ = RH.instrument(src)
    return ctx


def tree_blocks(src):
    tree = RH._Tree(src)
    tree.feed(src)
    tree.close()
    out = []
    RH.find_blocks(tree.root, out)
    return out


# --------------------------------------------------------------- the block rule


def test_a_waterfall_row_whose_only_non_inline_child_is_empty_is_one_block():
    """The formulation that fails here is the obvious one. `.wf-row` DOES
    contain a non-inline descendant — the empty `div.bar` that draws the chart
    bar — so "innermost element with no non-inline descendant" disqualifies the
    row and the whole waterfall becomes unannotatable."""
    got = [n for n in tree_blocks(SHAPES) if "wf-row" in (n.attrs.get("class") or "")]
    assert len(got) == 1, "the row should be exactly one block, not split or skipped"
    assert "Row label" in RH.text_of(got[0])
    assert "0,99" in RH.text_of(got[0]), "the row's amount belongs to the same block"


def test_the_empty_bar_div_is_not_itself_a_block():
    assert not [n for n in tree_blocks(SHAPES)
                if n.tag == "div" and (n.attrs.get("class") or "") == "bar"]


def test_blocks_do_not_nest():
    nodes = tree_blocks(SHAPES)
    ids = {id(n) for n in nodes}
    for n in nodes:
        p = n.parent
        while p is not None:
            assert id(p) not in ids, "%s at line %d nests inside %s" % (
                n.tag, n.line, p.tag)
            p = p.parent


def test_svg_is_one_block_and_its_labels_are_not_separately_addressable():
    svgs = [n for n in tree_blocks(SHAPES) if n.tag == "svg"]
    assert len(svgs) == 1
    assert "Alpha" in RH.text_of(svgs[0]) and "Beta" in RH.text_of(svgs[0])
    assert not [n for n in tree_blocks(SHAPES) if n.tag == "text"]


def test_math_canvas_and_object_are_opaque_blocks_not_excluded():
    """They hold genuine reader-facing content: MathML IS the equation, canvas
    fallback content is standard practice, and object can embed a document. An
    earlier draft excluded all three while claiming nothing reader-facing was
    reachable only through the excluded set."""
    src = ('<p>before</p><math><mi>x</mi></math>'
           '<canvas>fallback words</canvas><object>embedded words</object>')
    tags = [n.tag for n in tree_blocks(src)]
    assert tags.count("math") == 1
    assert tags.count("canvas") == 1
    assert tags.count("object") == 1
    assert "mi" not in tags, "an opaque element is never descended into"


def test_a_header_is_not_excluded_by_the_head_entry():
    """The match is on the exact tag name, never a prefix. A prefix match on
    `head` swallows `<header class="masthead">`, which is the first content
    element of the motivating document."""
    assert [n for n in tree_blocks(SHAPES)
            if "kicker" in (n.attrs.get("class") or "")], \
        "the masthead's content should still be a block"


@pytest.mark.parametrize("tag", ["script", "style", "title", "noscript", "template"])
def test_excluded_elements_are_neither_blocks_nor_text(tag):
    src = "<p>kept</p><%s>excluded words</%s>" % (tag, tag)
    ctx = blocks_of(src)
    assert [t for t in ctx.blocks.values()] == ["kept"]
    assert "excluded words" not in "".join(ctx.blocks.values())


def test_a_documents_own_stylesheet_is_not_offered_as_a_passage():
    for text in blocks_of(SHAPES).blocks.values():
        assert "display:grid" not in text


def test_a_void_element_does_not_open_a_scope():
    """HTMLParser reports a void element through handle_starttag with no
    matching handle_endtag, so a tree builder that pushes it corrupts every
    nesting decision after it."""
    src = "<div><br><p>after the break</p></div>"
    tags = [n.tag for n in tree_blocks(src)]
    assert tags == ["p"], "the <p> is a sibling of <br>, not nested inside it"


# --------------------------------------------------------------- block text


def test_block_text_matches_textcontent_semantics():
    src = "<p>a <strong>b</strong> &amp; c<span> d</span></p>"
    assert list(blocks_of(src).blocks.values()) == ["a b & c d"]


def test_block_text_preserves_whitespace_verbatim():
    """The page compares a selection against this exact string. A
    normalisation here reports annotations lost against a document that never
    changed."""
    src = "<p>two  spaces\n\tand a tab</p>"
    assert list(blocks_of(src).blocks.values()) == ["two  spaces\n\tand a tab"]


def test_excluded_subtree_contributes_no_text_to_an_enclosing_block():
    src = "<div>visible<style>.x{color:red}</style></div>"
    assert list(blocks_of(src).blocks.values()) == ["visible"]


# --------------------------------------------------------------- reversibility


def test_stripping_the_instrumentation_yields_the_original_bytes():
    out, _, _ = RH.instrument(SHAPES)
    assert out != SHAPES, "the fixture must actually be instrumented"
    assert RH.strip(out) == SHAPES


def test_the_only_element_added_is_the_marker_stylesheet():
    out, _, _ = RH.instrument(SHAPES)
    before = re.findall(r"<([a-zA-Z][a-zA-Z0-9]*)", SHAPES)
    after = re.findall(r"<([a-zA-Z][a-zA-Z0-9]*)", out)
    assert sorted(after) == sorted(before + ["style"])


def test_the_marker_stylesheet_uses_no_var_reference():
    """The shell's custom properties are defined on ITS :root and do not inherit
    across a frame boundary, so a var() here resolves to nothing — silently."""
    assert "var(" not in RH.MARKER_CSS
    assert "[data-cla-mark]" in RH.MARKER_CSS
    assert "prefers-color-scheme" in RH.MARKER_CSS


def test_the_stylesheet_is_appended_after_all_content():
    out, ctx, _ = RH.instrument(SHAPES)
    assert out.index(RH.MARK_OPEN) > out.rindex("data-blk="), \
        "appended last so it shifts no data-line already recorded"


def test_data_line_names_the_source_line_of_the_tag():
    src = "line one\n<p>second line</p>\n<p>third line</p>\n"
    out, _, _ = RH.instrument(src)
    for lineno, needle in ((2, "second line"), (3, "third line")):
        tag = out[:out.index(needle)].rsplit("<p", 1)[-1]
        assert 'data-line="%d"' % lineno in tag


def test_a_start_tag_spanning_several_lines_still_records_its_first_line():
    src = 'intro\n<p\n   class="x"\n   id="y">text</p>\n'
    out, _, _ = RH.instrument(src)
    assert 'data-line="2"' in out
    assert RH.strip(out) == src


def test_a_start_tag_with_a_gt_inside_an_attribute_value_round_trips():
    src = '<p title="a > b">text</p>'
    out, _, _ = RH.instrument(src)
    assert RH.strip(out) == src
    assert list(blocks_of(src).blocks.values()) == ["text"]


# --------------------------------------------------------------- the refusals


def test_an_existing_data_blk_attribute_is_refused():
    """A repeated attribute resolves to the AUTHOR's value, so every later
    lookup anchors to whatever it named — and nothing on the page looks wrong."""
    with pytest.raises(RH.Refused) as e:
        RH.instrument('<p data-blk="mine">text</p>')
    assert "data-blk" in str(e.value)
    assert "<p>" in str(e.value) or "p>" in str(e.value)


# Spelled out rather than taken from RH.OURS. Parametrizing over the constant
# under test makes the case list shrink WITH the constant, so dropping an entry
# from OURS left this test green — a mutant proved it, and a test that cannot
# fail is worse than no test, because the suite reports it as coverage.
COLLIDING = ("data-blk", "data-line", "data-sec", "data-sec-id")


def test_the_collision_set_is_exactly_these_four():
    assert tuple(RH.OURS) == COLLIDING


@pytest.mark.parametrize("token", COLLIDING)
def test_every_attribute_this_module_adds_is_refused_when_already_present(token):
    with pytest.raises(RH.Refused):
        RH.instrument('<p %s="mine">text</p>' % token)


def test_the_same_token_in_style_text_warns_rather_than_refusing():
    """A different and milder problem: the author's rules could style our
    markers, but no annotation mis-anchors. Refusing on any occurrence anywhere
    is broader than the hazard, and a guard that fires on a document nothing is
    wrong with gets switched off."""
    out, _, warnings = RH.instrument('<style>[data-blk]{color:red}</style><p>t</p>')
    assert out, "it renders"
    assert any("data-blk" in w for w in warnings)


# --------------------------------------------------------------- relative assets


def test_a_relative_reference_warns():
    _, _, warnings = RH.instrument('<p>t</p><img src="pic.png">')
    assert any("not self-contained" in w for w in warnings)


@pytest.mark.parametrize("ref", [
    "#anchor", "//cdn.example/x.js", "data:image/png;base64,AAAA",
    "mailto:a@b.c", "tel:+40700000000", "https://example.com/x.png",
])
def test_the_predicate_does_not_fire_on_a_non_relative_reference(ref):
    """The naive "not absolute" test fires on in-page anchors, mail links and
    inline data, which are universal in designed documents."""
    _, _, warnings = RH.instrument('<p>t</p><a href="%s">x</a>' % ref)
    assert not [w for w in warnings if "not self-contained" in w]


# --------------------------------------------------------------- sections


def test_sections_come_from_headings():
    ctx = blocks_of(SHAPES)
    assert [s["title"] for s in ctx.sections] == ["First section", "Second section"]
    assert [s["level"] for s in ctx.sections] == [2, 3]


def test_a_document_with_no_headings_yields_no_sections_rather_than_an_error():
    ctx = blocks_of("<p>just prose</p><p>and more</p>")
    assert ctx.sections == []
    assert len(ctx.blocks) == 2


def test_two_sections_with_the_same_title_get_distinct_slugs():
    ctx = blocks_of("<h2>Notes</h2><p>a</p><h2>Notes</h2><p>b</p>")
    slugs = [s["slug"] for s in ctx.sections]
    assert len(set(slugs)) == len(slugs)


def test_every_block_carries_its_section_id():
    out, ctx, _ = RH.instrument(SHAPES)
    assert 'data-sec-id="s1"' in out and 'data-sec-id="s2"' in out


# --------------------------------------------------------------- the real file


@pytest.mark.skipif(not has_briefing(), reason="peer-repo document not present")
def test_the_real_designed_document_instruments_and_strips_back():
    src = RH.read(BRIEFING)
    out, ctx, warnings = RH.instrument(src)
    assert RH.strip(out) == src
    # The design's original 319/4,251 came from a throwaway probe whose text
    # accumulation interleaved approximately. These are the corrected figures,
    # and this test is the command that produces them — which is the whole
    # reason the design was told to stop quoting the probe.
    assert len(ctx.blocks) == 319
    assert sum(len(t.split()) for t in ctx.blocks.values()) == 4369
    assert not [w for w in warnings if "not self-contained" in w], \
        "the motivating document is self-contained"


@pytest.mark.skipif(not has_briefing(), reason="peer-repo document not present")
def test_the_real_documents_waterfall_rows_are_blocks():
    rows = [n for n in tree_blocks(RH.read(BRIEFING))
            if "wf-row" in (n.attrs.get("class") or "")]
    assert len(rows) == 10, "two waterfalls, five rows each"


@pytest.mark.skipif(not has_briefing(), reason="peer-repo document not present")
def test_the_real_documents_blocks_do_not_nest():
    nodes = tree_blocks(RH.read(BRIEFING))
    ids = {id(n) for n in nodes}
    for n in nodes:
        p = n.parent
        while p is not None:
            assert id(p) not in ids
            p = p.parent


# --------------------------------------------------------------- fixture hygiene


def test_no_checked_in_fixture_carries_the_peer_documents_content():
    """The motivating briefing is a peer repo's document with real financial
    figures. It is referenced by path and never vendored.

    The tokens are assembled from halves rather than written out. A guard whose
    own source contains the strings it declares absent fails against itself —
    this repo has shipped that exact defect before, in a comment that named the
    token it said was missing.
    """
    tokens = ["Comision" + " card", "Infrastructur\u0103" + " GCP", "39" + ",32"]
    here = os.path.dirname(os.path.abspath(__file__))
    for name in sorted(os.listdir(here)):
        if not name.endswith((".py", ".html")):
            continue
        with io.open(os.path.join(here, name), encoding="utf-8") as fh:
            body = fh.read()
        for token in tokens:
            assert token not in body, "%s carries peer-repo content" % name
