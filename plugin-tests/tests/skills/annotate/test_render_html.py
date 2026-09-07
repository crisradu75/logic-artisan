"""Tests for `render_html.py` — the block rule, the two refusals, and the
reversibility property.

The reversibility test is the load-bearing one. Every other check here asks
whether the instrumentation did the right thing; that one asks whether it did
anything ELSE, which is the failure a reader could never see.
"""

import io
import os
import re
import sys

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
    assert len(ctx.blocks) == 340
    assert sum(len(t.split()) for t in ctx.blocks.values()) == 4468
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


# ======================================================================
# PR review round 1. Each block below closes a gap a reviewer named, and
# the header says which, so a later reader can tell a deliberate case
# from an incidental one.
# ======================================================================


# --- text that belongs to no block -----------------------------------
# Found by the correctness reviewer: `find_blocks` returned as soon as a child
# subtree held a block, without ever looking at the node's OWN direct text.


def test_text_beside_a_block_is_reported_rather_than_dropped():
    """`<div>before<p>x</p>after</div>` is legal, common, and has nowhere to put
    an anchor: marking the div would nest two blocks, and the instrumentation
    may not introduce an element. So the text is genuinely unannotatable — and
    saying so is the only honest option."""
    _, ctx, warnings = RH.instrument("<div>before<p>inside</p>after</div>")
    assert list(ctx.blocks.values()) == ["inside"]
    assert any("cannot be annotated" in w for w in warnings)
    assert any("before" in w or "after" in w for w in warnings)


def test_stranded_text_counts_every_occurrence():
    src = "<div>a<p>x</p>b</div><div>c<p>y</p>d</div>"
    _, _, warnings = RH.instrument(src)
    stranded = [w for w in warnings if "cannot be annotated" in w]
    assert stranded and "4 passage(s)" in stranded[0]


def test_a_clean_document_reports_no_stranded_text():
    """The non-vacuity partner: a warning that fires on everything is a warning
    nobody reads."""
    _, _, warnings = RH.instrument(SHAPES)
    assert not [w for w in warnings if "cannot be annotated" in w]


# --- implicit end tags ------------------------------------------------
# HTMLParser does not implement them, so an unclosed <p> nested rather than
# closing and the outer paragraph's text belonged to no block.


def test_an_unclosed_paragraph_closes_implicitly_as_a_browser_would():
    _, ctx, _ = RH.instrument("<p>one<p>two</p>")
    assert list(ctx.blocks.values()) == ["one", "two"]


def test_an_unclosed_list_item_closes_implicitly():
    _, ctx, _ = RH.instrument("<ul><li>one<li>two</ul>")
    assert list(ctx.blocks.values()) == ["one", "two"]


def test_an_unclosed_table_cell_closes_implicitly():
    _, ctx, _ = RH.instrument("<table><tr><td>a<td>b</tr></table>")
    assert list(ctx.blocks.values()) == ["a", "b"]


def test_a_block_element_closes_an_open_paragraph():
    _, ctx, _ = RH.instrument("<p>para<div>block</div>")
    assert list(ctx.blocks.values()) == ["para", "block"]


def test_a_paragraph_inside_a_div_inside_a_paragraph_does_not_close_the_outer():
    """Unwinding stops at anything not implicitly closable, or a nested
    paragraph would close an outer one a browser keeps open."""
    _, ctx, _ = RH.instrument("<p>outer<div><p>inner</p></div></p>")
    assert "inner" in list(ctx.blocks.values())


# --- the recursion, which no test reached -----------------------------
# Found by the test reviewer: every collision and relative reference sat on a
# direct child of the root, so deleting the recursive call passed the suite.


def test_a_collision_nested_deep_in_the_document_is_still_refused():
    with pytest.raises(RH.Refused):
        RH.instrument('<div><section><article>'
                      '<p data-blk="mine">text</p>'
                      '</article></section></div>')


def test_a_relative_reference_nested_deep_in_the_document_still_warns():
    _, _, warnings = RH.instrument('<div><section><figure>'
                                   '<img src="deep.png"><figcaption>c</figcaption>'
                                   '</figure></section></div>')
    assert any("not self-contained" in w for w in warnings)


def test_the_reported_collision_names_the_element_that_carries_it():
    """With more than one collision the message must identify a real one, not
    whichever the traversal happened to reach."""
    with pytest.raises(RH.Refused) as e:
        RH.instrument('<div><p data-line="x">a</p><span data-sec="y">b</span></div>')
    msg = str(e.value)
    assert ("data-line" in msg and "<p>" in msg) or \
           ("data-sec" in msg and "<span>" in msg)


# --- the zero-block case ----------------------------------------------


def test_a_document_with_no_annotatable_text_warns():
    """It reads as success in every count the caller has: zero blocks, zero
    words, no error."""
    _, ctx, warnings = RH.instrument("<div></div><br><img src='https://x/y.png'>")
    assert ctx.blocks == {}
    assert any("no annotatable text" in w for w in warnings)


def test_a_document_with_text_does_not_warn_about_having_none():
    _, _, warnings = RH.instrument("<p>words</p>")
    assert not [w for w in warnings if "no annotatable text" in w]


# --- reversibility is enforced in the library, not only the CLI --------


def test_instrument_refuses_a_document_it_cannot_strip_back():
    """`strip()` is a regex over the finished text, so a document that already
    contains the exact run of attributes this module emits does not round-trip.
    The realistic source is documentation about this very tool. The check lives
    in `instrument()` so a library caller gets it too, rather than in whichever
    wrapper remembered."""
    doc_about_this_tool = (
        '<pre><code>&lt;p data-blk="b1" data-line="3" data-sec="I" '
        'data-sec-id="s1"&gt;</code></pre>')
    with pytest.raises(RH.Refused) as e:
        RH.instrument(doc_about_this_tool)
    assert "strip back" in str(e.value)


def test_a_near_miss_of_the_attribute_run_still_round_trips():
    """The non-vacuity partner. The guard must fire on the real collision and
    NOT on text that merely mentions the attribute names — otherwise it would
    refuse this project's own documentation and get switched off."""
    mentions = '<p>The attributes are data-blk, data-line and data-sec.</p>'
    out, _, _ = RH.instrument(mentions)
    assert RH.strip(out) == mentions


# --- empty src vs empty href ------------------------------------------


def test_an_empty_src_is_reported():
    _, _, warnings = RH.instrument('<p>t</p><img src="">')
    assert any("not self-contained" in w for w in warnings)


def test_an_empty_href_is_not_reported():
    """A same-page link is legitimate; an empty src resolves to the document
    itself and is an authoring defect. They were treated identically."""
    _, _, warnings = RH.instrument('<p>t</p><a href="">x</a>')
    assert not [w for w in warnings if "not self-contained" in w]


def test_the_relative_warning_truncates_a_long_list():
    src = "<p>t</p>" + "".join('<img src="p%d.png">' % i for i in range(9))
    _, _, warnings = RH.instrument(src)
    w = [x for x in warnings if "not self-contained" in x][0]
    assert "9 relative reference(s)" in w
    assert w.endswith("...)")


# --- the script half of the text-collision scan -----------------------


def test_the_same_token_in_script_text_warns():
    """Only the <style> half of `self.cur.tag in ("style", "script")` was
    covered."""
    _, _, warnings = RH.instrument(
        '<script>var x = "data-sec-id";</script><p>t</p>')
    assert any("data-sec-id" in w for w in warnings)


# --- malformed markup -------------------------------------------------


def test_a_stray_close_tag_is_ignored_without_corrupting_the_tree():
    _, ctx, _ = RH.instrument("<div><p>one</p></span><p>two</p></div>")
    assert list(ctx.blocks.values()) == ["one", "two"]


def test_overlapping_tags_do_not_lose_a_block():
    _, ctx, _ = RH.instrument("<div><b><i>text</b></i></div>")
    assert "text" in "".join(ctx.blocks.values())


def test_an_unclosed_wrapper_at_end_of_document_still_yields_its_blocks():
    _, ctx, _ = RH.instrument("<div><p>one</p><p>two</p>")
    assert list(ctx.blocks.values()) == ["one", "two"]


@pytest.mark.parametrize("markup", [
    "<p class=unquoted>text</p>",
    "<p class='single'>text</p>",
    '<p class="double">text</p>',
    "<p  class = 'spaced' >text</p>",
])
def test_attribute_quoting_styles_all_round_trip(markup):
    """Real authored HTML is not uniformly double-quoted, and the splice edits
    the source rather than re-serialising it — so quoting must survive."""
    out, ctx, _ = RH.instrument(markup)
    assert RH.strip(out) == markup
    assert list(ctx.blocks.values()) == ["text"]


def test_a_self_closing_non_void_tag_round_trips():
    src = '<div><p>text</p><span/></div>'
    out, _, _ = RH.instrument(src)
    assert RH.strip(out) == src


def test_deeply_nested_blocks_are_found_at_depth():
    src = "<div>" * 12 + "<p>deep</p>" + "</div>" * 12
    _, ctx, _ = RH.instrument(src)
    assert list(ctx.blocks.values()) == ["deep"]


def test_a_real_head_element_is_excluded():
    """SHAPES puts <title>/<meta>/<style> at the top level, so the `head` entry
    was never tested against an actual <head>."""
    src = "<html><head><title>T</title></head><body><p>body text</p></body></html>"
    _, ctx, _ = RH.instrument(src)
    assert list(ctx.blocks.values()) == ["body text"]


# --- sections, the parts nothing asserted -----------------------------


def test_content_before_the_first_heading_carries_an_empty_section():
    """A very common real shape: an intro paragraph before the first heading."""
    out, ctx, _ = RH.instrument("<p>intro</p><h2>First</h2><p>body</p>")
    assert 'data-sec="" data-sec-id=""' in out
    assert ctx.sections[0]["title"] == "First"


def test_a_headings_own_words_count_towards_its_section():
    _, ctx, _ = RH.instrument("<h2>Two words</h2><p>three more words here</p>")
    assert ctx.sections[0]["words"] == 2 + 4


def test_a_heading_with_no_sluggable_characters_still_gets_a_slug():
    ctx = blocks_of("<h2>!!!</h2><p>a</p><h2>???</h2><p>b</p>")
    slugs = [s["slug"] for s in ctx.sections]
    assert all(slugs) and len(set(slugs)) == 2


# --- the CLI ----------------------------------------------------------


def test_main_reports_a_missing_document(capsys):
    assert RH.main(["no-such-file.html"]) == 1
    assert "no such document" in capsys.readouterr().out


def test_main_reports_a_refusal(tmp_path, capsys):
    p = tmp_path / "x.html"
    p.write_text('<p data-blk="mine">text</p>', encoding="utf-8")
    assert RH.main([str(p)]) == 1
    assert "REFUSED" in capsys.readouterr().out


def test_main_reports_invalid_utf8(tmp_path, capsys):
    """The encoding guard the module's docstring calls dangerous in a repo with
    no CI, because it fails on Windows and nowhere else."""
    p = tmp_path / "x.html"
    p.write_bytes(b"<p>caf\xe9</p>")
    assert RH.main([str(p)]) == 1
    assert "not valid UTF-8" in capsys.readouterr().out


def test_main_writes_the_instrumented_copy(tmp_path, capsys):
    src = tmp_path / "x.html"
    src.write_text("<p>text</p>", encoding="utf-8")
    out = tmp_path / "out.html"
    assert RH.main([str(src), "--out", str(out)]) == 0
    written = out.read_text(encoding="utf-8")
    assert "data-blk=" in written
    assert RH.strip(written) == "<p>text</p>"


def test_main_prints_warnings(tmp_path, capsys):
    p = tmp_path / "x.html"
    p.write_text('<p>t</p><img src="pic.png">', encoding="utf-8")
    assert RH.main([str(p)]) == 0
    assert "not self-contained" in capsys.readouterr().out


def test_use_utf8_stdout_survives_a_stream_without_reconfigure():
    """It no-ops when `reconfigure` is absent. Exercised so the no-op is a
    decision rather than an untested branch."""
    class Bare(object):
        pass

    real_out, real_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = Bare(), Bare()
        RH.use_utf8_stdout()
    finally:
        sys.stdout, sys.stderr = real_out, real_err


# --- PR review round 2 ------------------------------------------------
# The round-1 fix reported bare text beside a block. Round 2's question — does
# this fix leave the same defect somewhere else? — found that text wrapped in an
# INLINE element was still lost, and unreported. On the motivating document that
# was 21 passages, 13 of them callout and section labels.


def test_an_inline_element_beside_a_block_becomes_a_block():
    _, ctx, _ = RH.instrument("<div><span>label</span><p>body</p></div>")
    assert list(ctx.blocks.values()) == ["label", "body"]


def test_a_promoted_inline_keeps_document_order():
    """The blocks are numbered in reading order, so an inline promoted after its
    siblings were collected would number out of sequence."""
    _, ctx, _ = RH.instrument("<div><p>first</p><span>second</span><p>third</p></div>")
    assert list(ctx.blocks.values()) == ["first", "second", "third"]


def test_a_promoted_inline_is_not_split_into_its_own_inline_children():
    _, ctx, _ = RH.instrument("<div><span>a <b>bold</b> c</span><p>body</p></div>")
    assert list(ctx.blocks.values()) == ["a bold c", "body"]


def test_an_inline_inside_a_block_is_still_not_a_block():
    """The rule barring inline elements exists to stop a paragraph being split
    into its own <strong> runs. Promotion must not reintroduce that."""
    _, ctx, _ = RH.instrument("<p>a <strong>bold</strong> c</p>")
    assert list(ctx.blocks.values()) == ["a bold c"]


def test_promoted_inlines_do_not_nest_with_their_siblings():
    nodes = tree_blocks("<div><span>label</span><p>body</p></div>")
    ids = {id(n) for n in nodes}
    for n in nodes:
        p = n.parent
        while p is not None:
            assert id(p) not in ids
            p = p.parent


def test_bare_text_beside_a_block_is_still_reported_as_unannotatable():
    """Promotion cannot help here: bare text has no element to anchor to, and
    the instrumentation may not introduce a wrapper."""
    _, ctx, warnings = RH.instrument("<div>bare<p>body</p></div>")
    assert list(ctx.blocks.values()) == ["body"]
    assert any("cannot be annotated" in w for w in warnings)


def test_an_excluded_element_beside_a_block_is_not_promoted():
    _, ctx, _ = RH.instrument("<div><style>.x{}</style><p>body</p></div>")
    assert list(ctx.blocks.values()) == ["body"]


def test_an_empty_inline_beside_a_block_is_not_promoted():
    _, ctx, warnings = RH.instrument("<div><span></span><p>body</p></div>")
    assert list(ctx.blocks.values()) == ["body"]
    assert not [w for w in warnings if "cannot be annotated" in w]


@pytest.mark.skipif(not has_briefing(), reason="peer-repo document not present")
def test_the_real_document_has_nothing_unannotatable():
    """Before this fix it had 21 such passages, silently. The count is the point:
    a warning that can never fire is not evidence."""
    _, _, warnings = RH.instrument(RH.read(BRIEFING))
    assert not [w for w in warnings if "cannot be annotated" in w]


def test_a_lone_opaque_element_is_the_block_rather_than_its_container():
    """The discriminating case for the opaque rule, found by a surviving mutant.

    Where the figure has a block sibling, the round-2 promotion path would carry
    it even if the opaque branch were removed — so a fixture with siblings
    cannot tell the two apart. Alone, it can: with the opaque branch gone the
    CONTAINER becomes the block and the anchor lands on the wrong element.
    """
    nodes = tree_blocks("<div><svg><text>Alpha</text></svg></div>")
    assert [n.tag for n in nodes] == ["svg"]


def test_a_lone_opaque_element_with_no_text_is_not_a_block():
    """The non-vacuity partner: an empty figure is not a passage."""
    assert tree_blocks("<div><svg><rect/></svg></div>") == []
