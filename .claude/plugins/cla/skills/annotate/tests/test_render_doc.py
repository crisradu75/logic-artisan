"""The page: what the Markdown subset produces, and what it must never do.

Two properties carry most of the weight here. **The document is never written
to** — the skill's whole contract is that annotating is a read of the source, and
a renderer that touched it would be editing the thing under review. And **the
text an annotation records must be the text the block actually shows**, because
`data-blk`, the captured offset and the replayed offset all count characters
against it; a renderer and a page that disagree about what a block says produce
an annotation that reports itself lost against a document nobody touched.
"""
import hashlib
import io
import os
import re

import pytest

import annotations_store as store
import render_doc


def render(md, **kw):
    body, ctx = render_doc.render_document(md, "", **kw)
    return body, ctx


def texts(ctx):
    return list(ctx.blocks.values())


@pytest.fixture
def repo(tmp_path):
    (tmp_path / ".git").mkdir()
    return tmp_path


# ---------------------------------------------------------------- the invariant


def test_rendering_never_writes_to_the_document(repo):
    src = repo / "doc.md"
    body = "# Title\n\n- one\n- two\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"
    src.write_bytes(body.encode("utf-8"))
    before = hashlib.sha256(src.read_bytes()).hexdigest()
    before_mtime = src.stat().st_mtime_ns

    render_doc.build(str(src), str(repo))
    render_doc.build(str(src), str(repo))                 # and again, idempotent

    assert hashlib.sha256(src.read_bytes()).hexdigest() == before
    assert src.stat().st_mtime_ns == before_mtime


def test_the_page_is_written_outside_the_repo(repo):
    src = repo / "doc.md"
    src.write_text("hello\n", encoding="utf-8")
    out, _ctx, _w = render_doc.build(str(src), str(repo))
    # Writing it into the tree would need a .gitignore entry in every consuming
    # repo, which an install has no business adding.
    assert store.rel_to_root(out, str(repo)) is None


def test_a_read_only_document_still_renders(repo):
    src = repo / "doc.md"
    src.write_text("hello\n", encoding="utf-8")
    os.chmod(str(src), 0o444)
    try:
        out, _ctx, _w = render_doc.build(str(src), str(repo))
        assert os.path.exists(out)
    finally:
        os.chmod(str(src), 0o644)


# ---------------------------------------------------------------- addressing


def test_every_addressable_block_carries_an_id_and_a_source_line():
    body, ctx = render("# H\n\npara one\n\n- item\n\n```\ncode\n```\n")
    found = re.findall(r'data-blk="(b\d+)" data-line="(\d+)"', body)
    assert len(found) == len(ctx.blocks)
    assert len({b for b, _ in found}) == len(found)          # ids unique
    assert all(int(l) > 0 for _, l in found)                 # lines real


def test_the_source_line_points_at_the_right_line():
    md = "# Title\n\nfirst para\n\nsecond para\n"
    body, _ = render(md)
    line = dict(re.findall(r'data-line="(\d+)"[^>]*>([^<]*)</p>', body))
    # `line` is what turns "this passage" into a place in the source, which is
    # where an edit actually has to land. A wrong number is worse than none.
    assert dict((v, k) for k, v in line.items())["first para"] == "3"
    assert dict((v, k) for k, v in line.items())["second para"] == "5"


def test_front_matter_is_addressable_and_does_not_shift_the_lines():
    md = "---\nname: x\n---\n\n# Title\n\nbody\n"
    body, ctx = render(md)
    assert "front matter" in body
    assert re.search(r'data-line="7"[^>]*>body</p>', body)


def test_html_comments_are_not_annotatable_and_do_not_shift_the_lines():
    md = "para one\n\n<!-- a note\nspanning lines -->\n\npara two\n"
    body, ctx = render(md)
    assert "a note" not in body
    # Dropping the comment outright would renumber every line below it, and
    # `data-line` is the whole reason to record one.
    assert re.search(r'data-line="6"[^>]*>para two</p>', body)


def test_a_blocks_recorded_text_is_what_the_block_shows():
    body, ctx = render("a **bold** and `code` and *em* word\n")
    # The page reads a block's characters with textContent; this script must
    # agree, or the two disagree about what an annotation anchored to.
    assert texts(ctx) == ["a bold and code and em word"]


def test_recorded_text_survives_a_link_and_an_entity():
    body, ctx = render("see [the docs](https://x.test/a?b=1&c=2) & more\n")
    assert texts(ctx) == ["see the docs & more"]
    assert 'href="https://x.test/a?b=1&amp;c=2"' in body
    # Escaping an already-escaped href turns &amp; into &amp;amp; and the URL
    # arrives on the page visibly wrong.
    assert "&amp;amp;" not in body


# ---------------------------------------------------------------- the subset


def test_headings_paragraphs_and_rules():
    body, _ = render("# One\n\n## Two\n\ntext\n\n---\n\nmore\n")
    assert "<h1" in body and "<h2" in body and "<hr>" in body
    assert body.count("<p ") == 2


def test_nested_lists_nest():
    body, _ = render("- a\n  - b\n    - c\n- d\n")
    assert body.count("<ul>") == 3
    assert body.count("<li") == 4


def test_an_ordered_list_after_a_bullet_list_is_a_separate_list():
    body, _ = render("- a\n1. b\n")
    # Running them together renumbers one into the other's sequence.
    assert "<ul>" in body and "<ol>" in body


def test_a_paragraph_inside_a_bullet_keeps_the_list_together():
    body, _ = render("- first\n\n  still first\n\n- second\n")
    assert body.count("<ul>") == 1, "a blank line inside an item split the list"
    assert body.count("<li") == 2


def test_a_nested_fenced_block_inside_a_bullet():
    body, _ = render("- run this:\n\n  ```sh\n  ls -la\n  ```\n")
    assert "<pre" in body and "ls -la" in body
    assert body.count("<ul>") == 1


def test_fenced_code_is_escaped_and_never_interpreted():
    body, ctx = render("```html\n<script>alert(1)</script>\n**not bold**\n```\n")
    assert "<script>alert" not in body
    assert "&lt;script&gt;" in body
    assert "<strong>" not in body
    assert texts(ctx) == ["<script>alert(1)</script>\n**not bold**"]


def test_a_fence_with_a_longer_closing_run():
    body, _ = render("````\n```\ninner\n```\n````\n")
    assert body.count("<pre") == 1


def test_tables_render_with_alignment():
    body, _ = render("| a | b |\n|:--|--:|\n| 1 | 2 |\n")
    assert "<table>" in body and "<th" in body and body.count("<td") == 2
    assert 'text-align:left' in body and 'text-align:right' in body


def test_blockquotes_nest_their_own_blocks():
    body, _ = render("> quoted **text**\n>\n> second\n")
    assert body.count("<blockquote>") == 1
    assert body.count("<p ") == 2


def test_inline_code_is_not_read_as_emphasis():
    body, ctx = render("`a_b_c` and `**x**`\n")
    assert "<em>" not in body and "<strong>" not in body
    assert texts(ctx) == ["a_b_c and **x**"]


def test_the_code_span_sentinels_never_reach_the_page(repo):
    src = repo / "d.md"
    src.write_text("`x` and `y` and plain\n", encoding="utf-8")
    out, _ctx, _w = render_doc.build(str(src), str(repo))
    page = io.open(out, encoding="utf-8").read()
    body = re.sub(r"<script.*?</script>", "", page, flags=re.S)
    assert "" not in body and "" not in body


def test_a_javascript_href_is_defused():
    body, _ = render("[click](javascript:alert(1))\n")
    # The document is usually trusted, but "usually" is not a property a
    # renderer can rely on.
    assert "javascript:" not in body
    assert 'href="#"' in body


def test_a_local_image_is_carried_as_a_data_uri(repo):
    png = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
    (repo / "shot.png").write_bytes(png)
    body, _ = render_doc.render_document("![a shot](shot.png)\n", str(repo))
    # A relative src resolves against the temp dir the page is served from, and a
    # file:// subresource is blocked outright — both fail silently.
    assert 'src="data:image/png;base64,' in body


def test_a_remote_or_missing_image_becomes_a_link_not_a_broken_icon(repo):
    body, _ = render_doc.render_document(
        "![x](https://e.test/a.png)\n\n![y](gone.png)\n", str(repo))
    assert body.count('class="imglink"') == 2
    assert "<img" not in body


def test_unrecognised_markup_passes_through_as_text():
    body, ctx = render("A footnote[^1] and <span>raw</span>\n")
    # A wrong guess renders confidently and silently, and the reader annotates a
    # passage the document does not contain.
    assert "&lt;span&gt;" in body
    assert texts(ctx) == ["A footnote[^1] and <span>raw</span>"]


def test_plain_text_gets_no_markup_interpretation():
    body, ctx = render("# not a heading\n\n**not bold**\n", plain_text=True)
    assert "<h1" not in body and "<strong>" not in body
    assert texts(ctx) == ["# not a heading", "**not bold**"]


def test_a_txt_extension_selects_plain_text(repo):
    src = repo / "notes.txt"
    src.write_text("# not a heading\n", encoding="utf-8")
    out, ctx, _w = render_doc.build(str(src), str(repo))
    assert texts(ctx) == ["# not a heading"]


def test_crlf_and_a_bom_render_the_same_as_lf(repo):
    lf = "# T\r\n\r\nbody\r\n"
    _, a = render_doc.render_document(lf, "")
    _, b = render_doc.render_document("﻿" + lf, "")
    assert texts(a) == texts(b) == ["T", "body"]


# ---------------------------------------------------------------- anchors


def _annotate(corpus, text, blk, before="", after=""):
    store.append(corpus, {"id": "a-" + blk, "text": text, "blk": blk, "note": "n",
                          "before": before, "after": after, "off": 0})


def test_an_anchor_that_still_matches_is_not_reported_lost(repo, tmp_path):
    corpus = str(tmp_path / "c.jsonl")
    _, ctx = render("the harbour was quiet\n")
    _annotate(corpus, "harbour", list(ctx.blocks)[0])
    checked, lost, problems, fatal = render_doc.check_anchors(ctx, corpus)
    assert (checked, lost, problems, fatal) == (1, [], [], None)


def test_an_anchor_whose_block_moved_is_relocated_by_its_context(tmp_path):
    corpus = str(tmp_path / "c.jsonl")
    _, ctx = render("first\n\nthe harbour was quiet\n")
    # b99 does not exist: block ids are ordinals, so an insertion above renumbers
    # everything below it.
    _annotate(corpus, "harbour", "b99", before="the ", after=" was quiet")
    _checked, lost, _p, _f = render_doc.check_anchors(ctx, corpus)
    assert lost == []


def test_an_anchor_whose_text_is_gone_is_reported_lost(tmp_path):
    corpus = str(tmp_path / "c.jsonl")
    _, ctx = render("the harbour was quiet\n")
    _annotate(corpus, "a sentence since deleted", "b1")
    _checked, lost, _p, _f = render_doc.check_anchors(ctx, corpus)
    # A lost anchor is a finding, not a fault: the note may be the reason the
    # edit that caused it was wrong.
    assert lost == ["a-b1"]


def test_an_ambiguous_anchor_is_left_lost_rather_than_guessed(tmp_path):
    corpus = str(tmp_path / "c.jsonl")
    _, ctx = render("the same words here\n\nthe same words here\n")
    _annotate(corpus, "the same words here", "b9")
    _checked, lost, _p, _f = render_doc.check_anchors(ctx, corpus)
    # Guessing files an annotation against the wrong passage while showing text
    # that looks exactly right.
    assert lost == ["a-b9"]


def test_a_resolved_annotation_is_not_chased(tmp_path):
    corpus = str(tmp_path / "c.jsonl")
    _, ctx = render("the replacement sentence\n")
    store.append(corpus, {"id": "a1", "text": "the old sentence", "blk": "b1",
                          "note": "n", "resolved": True})
    checked, lost, _p, _f = render_doc.check_anchors(ctx, corpus)
    # Its text is gone *because* something replaced it; chasing it would report
    # ANCHOR LOST on every annotation already dealt with.
    assert (checked, lost) == (0, [])


def test_an_unreadable_corpus_is_reported_not_counted_as_zero(tmp_path):
    corpus = tmp_path / "c.jsonl"
    corpus.write_text("<<<<<<< HEAD\n", encoding="utf-8")
    _, ctx = render("text\n")
    checked, lost, _p, fatal = render_doc.check_anchors(ctx, str(corpus))
    assert fatal and (checked, lost) == (0, [])


# ---------------------------------------------------------------- the page


def test_the_page_declares_one_non_source_class_matching_the_python_side(repo):
    src = repo / "d.md"
    src.write_text("text\n", encoding="utf-8")
    out, _ctx, _w = render_doc.build(str(src), str(repo))
    page = io.open(out, encoding="utf-8").read()
    for cls in render_doc.INJECTED_CLASSES:
        assert "const NON_SOURCE = '." + cls in page or ", ." + cls in page


def test_the_page_is_self_contained_and_needs_no_network(repo):
    src = repo / "d.md"
    src.write_text("# T\n\nbody\n", encoding="utf-8")
    out, _ctx, _w = render_doc.build(str(src), str(repo))
    page = io.open(out, encoding="utf-8").read()
    assert 'rel="icon" href="data:image/svg+xml;base64,' in page
    remote = re.findall(r'(?:src|href)="(https?://[^"]+)"', page)
    # A page that fetches a stylesheet renders wrong on a machine with no
    # network, which is exactly where a local reading tool gets used.
    assert remote == []


def test_the_document_key_reaches_the_page_as_json(repo):
    src = repo / "docs" / "it's a doc.md"
    src.parent.mkdir()
    src.write_text("body\n", encoding="utf-8")
    out, _ctx, _w = render_doc.build(str(src), str(repo))
    page = io.open(out, encoding="utf-8").read()
    assert 'const DOC = "docs/it\'s a doc.md";' in page


# ---------------------------------------------------------------- the rail


def titles(ctx):
    return [s["title"] for s in ctx.sections if s["titled"]]


def test_every_heading_becomes_a_section_and_a_rail_entry():
    body, ctx = render("# One\n\ntext\n\n## Two\n\nmore\n\n## Three\n\nlast\n")
    assert titles(ctx) == ["One", "Two", "Three"]
    # One extra section for the preamble, which carries no title and so earns no
    # rail entry.
    assert body.count('<section class="sec"') == 4
    assert render_doc.rail(ctx.sections).count('class="rail-item"') == 3


def test_the_preamble_gets_a_section_but_no_rail_entry():
    body, ctx = render("opening prose\n\n# First heading\n\ntext\n")
    assert ctx.sections[0]["titled"] is False
    # Without it, a document opening with prose has blocks outside every observed
    # region and the rail lights nothing until the first heading scrolls past.
    assert body.index("opening prose") > body.index('data-sec-id="s1"')
    assert render_doc.rail(ctx.sections).count('class="rail-item"') == 1


def test_a_heading_inside_a_fence_is_content_not_structure():
    body, ctx = render("# Real\n\n```sh\n# not a heading\necho hi\n```\n\ntext\n")
    # Splitting the document on raw heading-shaped lines puts a section boundary
    # inside a shell script.
    assert titles(ctx) == ["Real"]
    assert body.count('<section class="sec"') == 2


def test_a_heading_inside_a_blockquote_is_content_not_structure():
    _body, ctx = render("# Real\n\n> ## quoted heading\n>\n> text\n")
    assert titles(ctx) == ["Real"]


def test_a_heading_inside_a_list_item_is_content_not_structure():
    _body, ctx = render("# Real\n\n- item\n\n  ### nested heading\n")
    assert titles(ctx) == ["Real"]


def test_rail_depth_is_measured_against_the_shallowest_heading_present():
    _body, ctx = render("## Top\n\ntext\n\n### Under\n\nmore\n")
    got = render_doc.rail(ctx.sections)
    # A document whose top level is `##` would otherwise render its whole rail
    # indented one step, with the left column reserved for a level nothing uses.
    assert 'data-depth="0"' in got and 'data-depth="1"' in got
    assert 'data-depth="2"' not in got


def test_two_headings_with_the_same_title_get_distinct_anchors():
    body, ctx = render("## Notes\n\na\n\n## Notes\n\nb\n")
    ids = re.findall(r'<h2[^>]*id="([^"]+)"', body)
    # A document's own [link](#notes) lands on whichever the browser found first
    # when both share an id.
    assert ids == ["notes", "notes-2"]
    assert len(set(s["id"] for s in ctx.sections)) == len(ctx.sections)


def test_the_rail_links_to_anchors_that_exist_in_the_body():
    body, ctx = render("# One\n\na\n\n## Two\n\nb\n\n## Two\n\nc\n")
    got = render_doc.rail(ctx.sections)
    for href in re.findall(r'href="#([^"]+)"', got):
        assert 'id="%s"' % href in body


def test_section_word_counts_account_for_every_block():
    _body, ctx = render("# One\n\nthree words here\n\n## Two\n\ntwo words\n")
    total = sum(len(t.split()) for t in ctx.blocks.values())
    # The rail's bars are only meaningful if the counts are the same ones the
    # header reports; two independent tallies drift.
    assert sum(s["words"] for s in ctx.sections) == total


def test_a_longer_section_gets_a_longer_bar():
    _body, ctx = render("## Short\n\none\n\n## Long\n\n%s\n" % ("word " * 40))
    bars = [float(x) for x in re.findall(r'width:([\d.]+)%', render_doc.rail(ctx.sections))]
    assert len(bars) == 2 and bars[1] == 100.0 and bars[0] < bars[1]


def test_a_document_with_no_headings_gets_no_rail(repo):
    src = repo / "flat.md"
    src.write_text("just prose\n\nand more prose\n", encoding="utf-8")
    out, ctx, _w = render_doc.build(str(src), str(repo))
    assert render_doc.rail(ctx.sections) == ""
    page = io.open(out, encoding="utf-8").read()
    # An empty rail is a column of nothing taking a fifth of the reading width.
    assert 'class="rail"' not in page


def test_plain_text_gets_no_rail(repo):
    src = repo / "notes.txt"
    src.write_text("# not a heading\n\nmore\n", encoding="utf-8")
    out, ctx, _w = render_doc.build(str(src), str(repo))
    assert render_doc.rail(ctx.sections) == ""
    assert 'class="rail"' not in io.open(out, encoding="utf-8").read()


def test_every_addressable_block_sits_inside_a_section():
    body, ctx = render("prose\n\n# One\n\ntext\n\n## Two\n\n- item\n")
    depth = 0
    for chunk in re.split(r"(<section [^>]*>|</section>)", body):
        if chunk.startswith("<section"):
            depth += 1
        elif chunk == "</section>":
            depth -= 1
        elif "data-blk=" in chunk:
            # A block outside every section is invisible to the scroll-spy and
            # uncounted by the rail's annotation badges.
            assert depth == 1, "block outside a section: %s" % chunk[:60]


# ---------------------------------------------------------------- the theme


def test_the_page_opens_in_light_mode(repo):
    src = repo / "d.md"
    src.write_text("# T\n\nbody\n", encoding="utf-8")
    out, _ctx, _w = render_doc.build(str(src), str(repo))
    page = io.open(out, encoding="utf-8").read()
    # Set in the markup rather than by the script, so the page cannot paint one
    # palette and swap to the other on load.
    assert '<html lang="en" data-theme="light">' in page


def test_the_page_does_not_follow_the_system_theme(repo):
    src = repo / "d.md"
    src.write_text("# T\n\nbody\n", encoding="utf-8")
    out, _ctx, _w = render_doc.build(str(src), str(repo))
    page = io.open(out, encoding="utf-8").read()
    css = page[page.index("<style>"):page.index("</style>")]
    # Comments are stripped before the check, because a comment EXPLAINING that
    # there is no such rule contains the token and passes a naive scan — the
    # failure CLAUDE.md records under "a diagnosis, a measurement, or a count".
    rules = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    # The favicon keeps its own such rule — it sits on the tab strip, which does
    # follow the OS — but it is a data URI, not part of this stylesheet.
    assert "prefers-color-scheme" not in rules
    assert "matchMedia" not in page
