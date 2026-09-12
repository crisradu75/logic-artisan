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


# A real designed document, committed as a fixture. It began as a reference to a
# peer repo's copy and was skipped when absent, which meant the only checks
# against real authored HTML ran on one machine — and it went red once when
# somebody edited that copy, which is not a defect in this repo.
#
# Committed, it is the opposite: fixed bytes, so exact counts mean something, and
# every machine runs the same checks. It lives under `docs/` rather than beside
# these tests because it is also the document `annotate` is demonstrated on, and
# outside `.claude/plugins/cla/` because everything under there ships to
# consuming repos and this does not need to.
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
BRIEFING = os.path.join(HERE, "fixtures", "briefing-partener-2026-09-07.html")


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


def test_the_fixture_is_present():
    """It is committed, so absent is a failure rather than a skip. Every other
    check against real authored HTML rests on it, and a suite that skips them
    silently reports the same green as one that ran them."""
    assert has_briefing(), "the sample document is missing from %s" % BRIEFING
    assert os.path.getsize(BRIEFING) > 50000, "the fixture looks truncated"


def test_the_real_designed_document_instruments_and_strips_back():
    src = RH.read(BRIEFING)
    out, ctx, warnings = RH.instrument(src)
    assert RH.strip(out) == src

    # Exact counts, because the fixture is version-controlled now. They were
    # properties for a while: the file lived in a peer repo, someone edited it
    # mid-run, and 340 blocks became 357 with nothing wrong here. A figure
    # measured against a file outside version control has an expiry. This one
    # does not, so it is pinned — and a change to any of these three numbers is
    # now a real change in the block rule, which is what an assertion is for.
    assert len(ctx.blocks) == 362
    assert sum(len(t.split()) for t in ctx.blocks.values()) == 6345
    assert len(ctx.sections) == 22
    assert warnings == [], "the fixture is self-contained and fully annotatable"


def test_the_real_documents_waterfall_rows_are_blocks():
    rows = [n for n in tree_blocks(RH.read(BRIEFING))
            if "wf-row" in (n.attrs.get("class") or "")]
    assert len(rows) == 10, "two waterfalls, five rows each"


def test_the_real_documents_blocks_do_not_nest():
    nodes = tree_blocks(RH.read(BRIEFING))
    ids = {id(n) for n in nodes}
    for n in nodes:
        p = n.parent
        while p is not None:
            assert id(p) not in ids
            p = p.parent


# --------------------------------------------------------------- fixture hygiene


# Generated caches, excluded by NAME. `.git` is here so the repo's own is pruned
# without a special case: the walk below starts AT the root, so the first
# `dirnames` it prunes are the root's children and the root itself is never a
# candidate for the structural check.
_CACHE_DIRS = {".git", ".pytest_cache", ".venv", "__pycache__", "node_modules"}


def _is_nested_checkout(directory):
    """True for a second checkout inside the repo — a worktree or a submodule.

    Both carry their own `.git` entry: a FILE for a worktree, a directory for a
    clone. A worktree's is a file, which is why `_CACHE_DIRS` alone never sees
    it — `os.walk` reports it under `filenames`, not `dirnames`, so the worktree
    directory is walked into like any other.
    """
    return os.path.exists(os.path.join(directory, ".git"))


def _copies_under(root, name):
    """Every file called `name` under `root`, skipping caches and other checkouts.

    WHY THIS IS STRUCTURAL AND NOT A NAME. The first version of this walk pruned
    four cache names and nothing else, so it descended into every worktree under
    `.claude/worktrees/` and counted one fixture copy per worktree — issue #235.
    This repo's `new-worktree` skill and the Agent tool's worktree isolation both
    put a checkout there, so the walk broke whenever anyone worked the way the
    repo tells them to.

    Adding `worktrees` to the name list is the fix NOT taken, and the reasoning
    is already written down one directory over, in `tests/consistency/
    test_doc_facts.py` (see `_is_nested_checkout` and the comment above it).
    `manual_worktree.py` exposes `--worktree-dir`, so the default placement is an
    input rather than a law: a worktree at `.worktrees/`, at `wt/`, or reached
    through a directory junction is still a second checkout and would still be
    counted. It is also too broad the other way, hiding any directory that merely
    happens to be named `worktrees`. A nested `.git` entry is structural, so it
    holds for every placement.

    WHY IT READS NAMES AND NEVER AN ABSOLUTE PATH'S PARTS. `_excluded` in that
    same file carries the other half of this trap: testing the excluded names
    against the parts of a whole filesystem path means a repo checked out below a
    directory that happens to be called `node_modules` excludes its own entire
    tree, and the count silently becomes 0. This walk is immune by construction
    rather than by care — it only ever inspects one directory NAME at a time,
    descending from `root`, so no component above `root` is ever examined.
    """
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in _CACHE_DIRS
            and not _is_nested_checkout(os.path.join(dirpath, d))
        ]
        found.extend(
            os.path.join(dirpath, f) for f in filenames if f == name
        )
    return found


def test_the_fixture_has_exactly_one_copy_in_the_repo():
    """One canonical copy, so an assertion about its contents means something.

    This replaces a guard that forbade committing the document at all. That guard
    was built on a wrong premise — the file was thought to be confidential, and
    it is not — and a check whose stated reason is false is worse than no check,
    because the next reader either believes it or deletes it without knowing what
    it was for.

    What survives is the part that is still true: two copies drift, and a test
    pinning exact counts against one of them then passes while the document
    anyone actually reads has moved.

    The walk is `_copies_under`, whose docstring carries the worktree story. Note
    this test alone cannot prove that part: run from inside a worktree, `REPO_ROOT`
    is the worktree's own root and there is no nested checkout to skip, so it
    passes either way. The two tests below build the discriminating tree instead.
    """
    found = _copies_under(REPO_ROOT, os.path.basename(BRIEFING))
    assert found, "the fixture is missing entirely"
    assert len(found) == 1, "the fixture has %d copies, which will drift: %s" % (
        len(found), found)
    assert os.path.samefile(found[0], BRIEFING), \
        "the one copy is not where the tests look: %s" % found[0]


def _plant(root, *parts):
    """Create a file at `root/*parts`, making its directories."""
    path = os.path.join(root, *parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("x")
    return path


def test_a_nested_checkout_is_not_a_second_copy(tmp_path):
    """The #235 shape, built rather than waited for.

    A worktree under `.claude/worktrees/` holds its own copy of every tracked
    file, including this fixture. Counting those is what turned a correct tree
    into `the fixture has 6 copies`. The `.git` planted here is a FILE, which is
    what a real worktree has and what makes the name-based prune miss it.
    """
    root = str(tmp_path)
    real = _plant(root, "plugin-tests", "tests", "fixtures", "doc.html")
    _plant(root, ".claude", "worktrees", "agent-1", ".git")
    _plant(root, ".claude", "worktrees", "agent-1",
           "plugin-tests", "tests", "fixtures", "doc.html")

    assert _copies_under(root, "doc.html") == [real]


def test_a_worktree_placed_anywhere_is_still_skipped(tmp_path):
    """Not just the default placement — that is the whole point of going structural.

    `manual_worktree.py --worktree-dir` means `.claude/worktrees/` is a default,
    not a law. A name-based skip passes the test above and fails this one, which
    is exactly the discrimination the name-based fix lacks.
    """
    root = str(tmp_path)
    real = _plant(root, "plugin-tests", "tests", "fixtures", "doc.html")
    for where in (("wt", "one"), (".worktrees", "two"), ("sibling-checkout",)):
        _plant(root, *where, ".git")
        _plant(root, *where, "plugin-tests", "tests", "fixtures", "doc.html")

    assert _copies_under(root, "doc.html") == [real]


def test_an_ordinary_directory_named_worktrees_is_still_searched(tmp_path):
    """The other direction, and the reason a name is too broad as well as too narrow.

    A directory called `worktrees` that is NOT a checkout holds real repo content,
    and a genuine duplicate inside it must still be reported — otherwise the fix
    for a false failure buys a false PASS, which is the worse trade.
    """
    root = str(tmp_path)
    real = _plant(root, "plugin-tests", "tests", "fixtures", "doc.html")
    stray = _plant(root, "docs", "worktrees", "doc.html")

    assert sorted(_copies_under(root, "doc.html")) == sorted([real, stray])


def test_a_cache_directory_is_still_pruned_by_name(tmp_path):
    """The original four names still do their job; nothing was traded away."""
    root = str(tmp_path)
    real = _plant(root, "plugin-tests", "tests", "fixtures", "doc.html")
    for cache in ("__pycache__", "node_modules", ".pytest_cache", ".venv"):
        _plant(root, cache, "doc.html")

    assert _copies_under(root, "doc.html") == [real]


def test_the_repo_root_is_not_mistaken_for_a_nested_checkout(tmp_path):
    """The root's own `.git` must not prune the entire tree.

    Pruning starts at the root's CHILDREN, so the root is never a candidate — but
    a rewrite that checked `dirpath` instead of each child would take the count to
    0 and report "the fixture is missing entirely" on a correct tree.
    """
    root = str(tmp_path)
    real = _plant(root, "plugin-tests", "tests", "fixtures", "doc.html")
    os.makedirs(os.path.join(root, ".git", "objects"))

    assert _copies_under(root, "doc.html") == [real]


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


# --- anchors, and where an edit has to land ---------------------------------


def _corpus_record(ctx, blk, needle):
    text = ctx.blocks[blk]
    off = text.index(needle)
    return {"id": "a1", "doc": "d", "blk": blk, "sec": "", "line": 1, "off": off,
            "text": needle, "before": text[max(0, off - 60):off],
            "after": text[off + len(needle):off + len(needle) + 60],
            "note": "n", "at": "2026-09-07T10:00:00"}


def test_an_annotation_on_an_html_block_is_found_again_after_a_rebuild(tmp_path):
    """`check_anchors` has to accept the HTML renderer's ctx and find its text.
    A lost anchor means the document moved; reporting one against a document
    that did not move is the failure this covers."""
    import json
    import render_doc

    doc = tmp_path / "d.html"
    doc.write_text("<h2>Title</h2><p>A paragraph worth arguing with.</p>",
                   encoding="utf-8")
    _out, ctx, _w = RH.instrument(doc.read_text(encoding="utf-8"))
    blk = [k for k, v in ctx.blocks.items() if "arguing" in v][0]

    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(
        json.dumps(_corpus_record(ctx, blk, "worth arguing")) + "\n",
        encoding="utf-8")

    checked, lost, problems, fatal = render_doc.check_anchors(ctx, str(corpus))
    assert fatal is None and problems == []
    assert checked == 1
    assert lost == [], "an unchanged document reported a lost anchor"


def test_an_annotation_is_reported_lost_when_its_passage_is_edited_out(tmp_path):
    """The non-vacuity partner. A check that never reports a loss would pass the
    test above on any document at all."""
    import json
    import render_doc

    before = "<h2>Title</h2><p>A paragraph worth arguing with.</p>"
    _o, ctx_before, _w = RH.instrument(before)
    blk = [k for k, v in ctx_before.blocks.items() if "arguing" in v][0]
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(
        json.dumps(_corpus_record(ctx_before, blk, "worth arguing")) + "\n",
        encoding="utf-8")

    after = "<h2>Title</h2><p>A paragraph that no longer says it.</p>"
    _o, ctx_after, _w = RH.instrument(after)
    checked, lost, problems, fatal = render_doc.check_anchors(ctx_after, str(corpus))
    assert checked == 1
    assert lost == ["a1"], "the passage is gone and nothing reported it"


def test_the_recorded_line_is_the_source_line_an_edit_would_land_on():
    """`line` is not for scrolling — the page can already reach the block it
    painted. It is for the session that reads the annotations back and has to
    edit the FILE."""
    src = ("line one\n"
           "line two\n"
           "<h2>A heading</h2>\n"
           "<p>The paragraph to annotate.</p>\n")
    out, ctx, _w = RH.instrument(src)
    para = [m for m in re.finditer(r'<p data-blk="(b\d+)" data-line="(\d+)"', out)]
    assert para, "the paragraph was not instrumented"
    blk, line = para[0].group(1), int(para[0].group(2))
    assert "paragraph to annotate" in ctx.blocks[blk]
    # The same line `grep -n` would report for that passage.
    assert src.split("\n")[line - 1].startswith("<p>The paragraph")


def test_the_server_takes_the_document_from_its_own_argument_not_the_request():
    """The rebuild endpoint writes a file. A path taken off the wire would let a
    page choose what it renders — and the html branch must not be the one that
    reintroduces that."""
    import inspect

    import annotate_server
    src = inspect.getsource(annotate_server.Handler._render)
    assert "self.doc_path" in src
    for taken_from_the_wire in ("self.path", "urlparse", "body", "payload"):
        assert taken_from_the_wire not in src.split("def _render")[1], \
            "_render reads %r; the document must come from the server's own" \
            " argument" % taken_from_the_wire


def test_rendering_an_html_document_never_writes_to_it(tmp_path):
    """The skill's single most safety-critical claim, and it named only the
    Markdown renderer as its evidence. For an HTML target the read happens here,
    so the guarantee needs its own hash across a full build-and-rebuild cycle."""
    import hashlib

    import render_html

    (tmp_path / ".git").mkdir()
    doc = tmp_path / "d.html"
    doc.write_text(DESIGNED_SAMPLE, encoding="utf-8")
    before = hashlib.sha256(doc.read_bytes()).hexdigest()

    pages = tmp_path / "pages"
    pages.mkdir()
    out = pages / "p.html"
    render_html.build(str(doc), str(tmp_path), str(out))
    assert hashlib.sha256(doc.read_bytes()).hexdigest() == before
    # And again: a rebuild is the case where a renderer that opened the source
    # for writing would show up.
    render_html.build(str(doc), str(tmp_path), str(out))
    assert hashlib.sha256(doc.read_bytes()).hexdigest() == before


DESIGNED_SAMPLE = """<!doctype html><meta charset="utf-8">
<title>Sample</title>
<style>.wrap{max-width:62rem}</style>
<div class="wrap"><h2>Heading</h2><p>A paragraph.</p></div>
"""
