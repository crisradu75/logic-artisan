"""The defects a multi-agent review of this feature found, pinned.

Everything here failed before the fix beside it. They live in one file rather
than scattered because they share a cause worth naming: each is a place where
the code and its own comment disagreed, or where a three-state answer was
squeezed through a two-state primitive, and none of them was caught by a green
suite. A mutation study over the original suite left 30 of 36 mutants alive.
"""
import io
import json
import os
import threading
import urllib.error
import urllib.request

import pytest

import annotations_store as store
import openspec_change as OC
import render_change as RC
import render_doc as R


# ---------------------------------------------------------------- injection


def test_a_fence_info_string_cannot_break_out_of_its_attribute():
    """`esc()` is quote=False — right for a text node, wrong for an attribute.
    A fence opened ```js"onmouseover="alert(1) closed the class attribute and
    left a live handler on a page that is same-origin with the endpoint that
    appends to a committed, never-rewritten corpus."""
    body, _ = R.render_document('```js"onmouseover="alert(1)\nx\n```\n', ".")
    # The token may still APPEAR — escaped, inside the attribute value, where it
    # is inert text. What must not appear is an unescaped quote closing the
    # attribute and starting a handler.
    assert 'onmouseover="' not in body
    assert "&quot;onmouseover=&quot;" in body


def test_a_heading_with_a_quote_cannot_break_out_of_data_sec():
    body, _ = R.render_document('## He said "hi"\n\nbody\n', ".")
    assert 'data-sec="He said &quot;hi&quot;"' in body


def test_a_counterpart_label_with_a_quote_stays_inside_its_attribute():
    assert RC.esc_attr('a "quoted" label') == "a &quot;quoted&quot; label"


# ---------------------------------------------------------------- markdown


@pytest.mark.parametrize("src,want", [
    ('[a](http://x/y "the title")', '<a href="http://x/y"'),
    ('![alt](p.png "cap")', 'class="imglink"'),
])
def test_a_link_or_image_with_a_title_renders(src, want):
    """The title group matched `&quot;`, but `esc()` runs with quote=False so a
    `"` is still a literal `"` by then — the group could never fire, `\\)` then
    failed against the space, and raw markdown was left sitting in the prose the
    reader is trying to annotate."""
    body, ctx = R.render_document(src + "\n", ".")
    assert want in body
    assert "](" not in body, "raw markdown left in the rendered prose"
    assert "the title" not in list(ctx.blocks.values())[0]


# ---------------------------------------------------------------- anchors


def test_check_anchors_agrees_with_the_page_when_the_context_changed(tmp_path):
    """`check_anchors` fell back to a bare text search across every block. The
    page's hostFor() has no such fallback — it returns null and paints ANCHOR
    LOST — so the CLI reported "0 could not be read back" over records the drawer
    was already flagging. The fallback only fired when the context search missed,
    i.e. exactly when the page cannot relocate the record."""
    _body, ctx = R.render_document("first para\n\nthe harbour was calm\n", ".")
    # The document was edited from "quiet" to "calm": the stored block is gone,
    # the context needle no longer matches, but the bare word still occurs once.
    rec = {"id": "a1", "text": "harbour", "blk": "b99",
           "before": "the ", "after": " was quiet", "note": "n", "off": 0}
    corpus = str(tmp_path / "c.jsonl")
    store.append(corpus, rec)
    checked, lost, _p, _f = R.check_anchors(ctx, corpus)
    assert checked == 1
    assert lost == ["a1"], "reported anchored where the page paints ANCHOR LOST"


def _change_with_a_lost_anchor(tmp_path):
    """A rendered change plus a corpus holding one annotation whose text is gone."""
    root = tmp_path
    (root / ".git").mkdir()
    d = root / "openspec" / "changes" / "demo"
    d.mkdir(parents=True)
    (d / "proposal.md").write_text(
        "# P\n\n## What Changes\n\n- Rework `src/a/b.py`\n", encoding="utf-8")
    (d / "tasks.md").write_text(
        "# T\n\n## 1. Go\n\n- [x] 1.1 Edit `src/a/b.py`\n", encoding="utf-8")
    _out, _model, ctxs = RC.build(str(d), str(root), str(tmp_path / "p.html"))
    corpus = store.path_for(str(d), str(root))
    store.append(corpus, {"id": "a1", "note": "n", "blk": "proposal:b9",
                          "text": "a passage since deleted", "before": "", "after": ""})
    return str(d), str(root), ctxs, corpus


def test_the_change_path_reports_lost_anchors(tmp_path):
    """The document path has always done this. The change path returned before
    reading the corpus at all — in the case where anchors are most fragile."""
    _d, _root, ctxs, corpus = _change_with_a_lost_anchor(tmp_path)
    checked, lost, _p, fatal = RC.check_change_anchors(ctxs, corpus)
    assert fatal is None and checked == 1 and lost == ["a1"]


def test_the_change_build_itself_reports_the_lost_anchor(tmp_path, capsys):
    """Calling `check_change_anchors` directly proves the function works and says
    nothing about whether `build()` CALLS it — a mutation run showed exactly that
    by deleting the call and leaving the suite green."""
    d, root, _ctxs, _corpus = _change_with_a_lost_anchor(tmp_path)
    capsys.readouterr()
    RC.main([d, "--root", root, "--out", str(tmp_path / "p2.html")])
    out = capsys.readouterr().out
    assert "ANCHOR LOST" in out and "a1" in out


# ---------------------------------------------------------------- the corpus


def test_a_byte_order_mark_does_not_cost_the_first_record(tmp_path):
    """`open(encoding="utf-8")` does not strip a BOM — only `utf-8-sig` does. A
    corpus touched by a Windows editor would otherwise lose its FIRST record and
    report it as unparseable, in a plugin that ships to Windows repos."""
    p = tmp_path / "c.jsonl"
    p.write_bytes(b'\xef\xbb\xbf{"id":"a1","note":"n","text":"t"}\n'
                  b'{"id":"a2","note":"n","text":"t"}\n')
    problems = []
    rows = store.read_all(str(p), problems=problems)
    assert [r["id"] for r in rows] == ["a1", "a2"]
    assert problems == []


def test_an_empty_corpus_is_not_a_missing_one(tmp_path):
    """Three states, and the distinction drives the banner: "no annotations yet;
    this is the first pass" must not print over a file that exists."""
    missing = tmp_path / "absent.jsonl"
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    assert store.read_all(str(missing)) is None
    assert store.read_all(str(empty)) == []


def test_concurrent_appends_do_not_tear_each_other(tmp_path):
    """The server is a ThreadingHTTPServer and `LOCK` is the only thing
    serialising writes. A torn line costs the record that tore AND the one
    appended after it."""
    p = str(tmp_path / "c.jsonl")
    errors = []

    def write(i):
        try:
            store.append(p, {"id": "a%d" % i, "note": "n" * 200, "text": "t"})
        except Exception as e:                                   # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=write, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not errors
    problems = []
    rows = store.read_all(p, problems=problems)
    assert problems == []
    assert len({r["id"] for r in rows}) == 20


def test_a_record_with_no_id_is_refused_at_the_write(tmp_path):
    """It was accepted, fsynced, and reported as saved — then dropped by every
    reader, in a store whose whole premise is that nothing is ever lost."""
    p = str(tmp_path / "c.jsonl")
    with pytest.raises(ValueError):
        store.append(p, {"text": "lost note", "note": "gone"})
    assert store.read_all(p) is None, "nothing should have been written"


def test_a_corpus_that_cannot_be_stated_is_damage_not_absence(tmp_path, monkeypatch):
    """`os.path.exists` returns False for a stat that FAILED — a permission
    error, an I/O error, a path over MAX_PATH. Returning None there prints "first
    pass" over a corpus full of work."""
    p = str(tmp_path / "c.jsonl")
    real = os.stat

    def boom(path, *a, **k):
        if str(path) == p:
            raise PermissionError(13, "denied")
        return real(path, *a, **k)

    monkeypatch.setattr(os, "stat", boom)
    with pytest.raises(store.CorpusUnreadable) as e:
        store.read_all(p)
    assert "not an empty corpus" in str(e.value)


# ---------------------------------------------------------------- the model


def test_two_tasks_that_share_a_number_get_distinct_ids():
    """`num` is author-supplied for tasks. A list mixing numbered and unnumbered
    items produced two `tasks:1`, and every `{c["id"]: c}` downstream silently
    kept one — painting one task's links onto the other's passage."""
    tasks = "# T\n\n## 1. Go\n\n- [ ] Unnumbered first\n- [ ] 1. Numbered one\n"
    m = OC.build("demo", {"proposal": "# P\n\n## What Changes\n\n- x\n", "tasks": tasks})
    ids = [c["id"] for c in m["claims"] if c["kind"] == "task"]
    assert len(ids) == len(set(ids)) == 2


def test_two_decisions_that_share_a_number_get_distinct_ids():
    design = ("# D\n\n## Decisions\n\n"
              "1. **First** the argument.\n"
              "  1. **Nested point** under it.\n"
              "2. **Second** one.\n")
    m = OC.build("demo", {"proposal": "# P\n\n## What Changes\n\n- x\n", "design": design})
    ids = [c["id"] for c in m["claims"] if c["kind"] == "decision"]
    assert len(ids) == len(set(ids))


def test_ubiquity_is_scoped_to_promises_so_a_discriminating_path_survives():
    """One promise and twelve tasks naming one path is the best evidence a change
    offers. Counted across all claims it looked like vocabulary — which left 83%
    of promises falsely uncovered across the sweep."""
    prop = "# P\n\n## What Changes\n\n- Rework `web/skills/site/audit.py` end to end\n"
    tasks = "# T\n\n## 1. Go\n\n" + "".join(
        "- [x] 1.%d Edit `web/skills/site/audit.py` step %d\n" % (i, i) for i in range(1, 13))
    m = OC.build("demo", {"proposal": prop, "tasks": tasks})
    assert m["coverage"]["covered"], "the one discriminating path was discarded"
    assert m["coverage"]["stats"]["ubiquitous"] == []


def test_a_token_in_too_many_promises_is_dropped_as_vocabulary():
    prop = "# P\n\n## What Changes\n\n" + "".join(
        "- Step %d touches `src/shared/thing.py`\n" % i for i in range(1, 7))
    tasks = "# T\n\n## 1. Go\n\n- [x] 1.1 Edit `src/shared/thing.py`\n"
    m = OC.build("demo", {"proposal": prop, "tasks": tasks})
    assert "src/shared/thing.py" in m["coverage"]["stats"]["ubiquitous"]
    assert m["coverage"]["covered"] == []


def test_a_design_decision_citation_is_a_link():
    prop = "# P\n\n## What Changes\n\n- Drop the banner, per design decision 2\n"
    design = ("# D\n\n## Decisions\n\n1. **First.** a\n2. **Keep the convention.** b\n")
    m = OC.build("demo", {"proposal": prop, "design": design})
    refs = [l for l in m["links"] if l["kind"] == "reference"]
    assert refs and any("design:2" in (l["src"], l["dst"]) for l in refs)


def test_a_task_citation_discharges_the_promise_that_makes_it():
    prop = "# P\n\n## What Changes\n\n- Rename the thing, see task 1.1\n"
    tasks = "# T\n\n## 1. Go\n\n- [x] 1.1 Rename it\n"
    m = OC.build("demo", {"proposal": prop, "tasks": tasks})
    assert len(m["coverage"]["covered"]) == 1
    assert m["coverage"]["covered"][0]["pays"][0][1]["kind"] == "reference"


def test_a_requirement_title_quoted_in_a_task_is_a_link():
    prop = "# P\n\n## What Changes\n\n- x\n"
    tasks = "# T\n\n## 1. Go\n\n- [x] 1.1 Update Consolidated project-facts file wording\n"
    spec = "# D\n\n## MODIFIED Requirements\n\n### Requirement: Consolidated project-facts file\n\nt\n"
    m = OC.build("demo", {"proposal": prop, "tasks": tasks, "spec-cap": spec})
    assert [l for l in m["links"] if l["kind"] == "reference"
            and any(i.startswith("spec-cap:") for i in (l["src"], l["dst"]))]


def test_a_capability_with_a_spec_delta_but_no_proposal_bullet_is_flagged():
    """The other half of `capability_coverage`, which had no test at all — the
    one that was named was asserting the well-formed case."""
    prop = "# P\n\n## What Changes\n\n- something\n"
    spec = "# D\n\n## MODIFIED Requirements\n\n### Requirement: R\n\nt\n"
    m = OC.build("demo", {"proposal": prop, "spec-orphan": spec})
    row = [c for c in m["coverage"]["capabilities"] if c["name"] == "orphan"][0]
    assert row["delta"] and not row["named"]
    assert "no proposal capability names" in row["why"]


def test_two_archived_changes_matching_one_id_is_ambiguity_not_absence(tmp_path):
    arch = tmp_path / "openspec" / "changes" / "archive"
    for d in ("2026-08-13-remove-thing", "2026-09-01-remove-thing"):
        (arch / d).mkdir(parents=True)
        (arch / d / "proposal.md").write_text("# P\n", encoding="utf-8")
    # Returning the first would annotate the wrong change, silently.
    assert OC.find_change("remove-thing", str(tmp_path)) is None


def test_the_link_vocabulary_is_stated_once():
    """It was spelled three times in three encodings, two of them inverses — so a
    fifth kind could be added and only one site would say it had been missed."""
    assert set(OC.STRONG_KINDS) <= set(OC.LINK_KINDS)
    assert OC.LINK_KINDS[0] == "reference" and OC.LINK_KINDS[-1] == "wording"


def test_an_unknown_claim_kind_is_refused_rather_than_silently_rescoping():
    """Coverage scopes ubiquity to promises and falls back to all claims when it
    finds none, so a typo does not skip a branch — it restores the rule the sweep
    measured wrong."""
    with pytest.raises(AssertionError):
        OC._claim("proposal", "promiseee", "p1", "text", 1)


# ---------------------------------------------------------------- the page


def test_a_counterpart_never_lands_inside_a_nested_block():
    """`after_block` closed the INNER element. Blocks nest — a nested list puts
    one `<li data-blk>` inside another — so the card landed inside the outer
    block, whose every offset then counted words the document does not contain."""
    h = ('<ul><li data-blk="t:b1">parent'
         '<ul><li data-blk="t:b2">child</li></ul></li></ul>')
    out = RC.after_block(h, "t:b2", '<span class="cf">CARD</span>')
    assert out.index("CARD") > out.index("</li></ul></li>")


def test_add_class_merges_rather_than_adding_a_second_attribute():
    """HTML keeps the FIRST class attribute and drops the rest, so a block that
    already had one would lose it."""
    got = RC.add_class('<p class="pt" data-blk="x">t</p>', "x", "linked")
    assert got.count("class=") == 1 and "linked" in got and "pt" in got


def test_the_change_key_keeps_the_archive_segment(tmp_path):
    """Dropping it made the page name a path that does not exist, and disagree
    with both the server's doc_key and the corpus path."""
    root = tmp_path
    (root / ".git").mkdir()
    d = root / "openspec" / "changes" / "archive" / "2026-08-13-demo"
    d.mkdir(parents=True)
    (d / "proposal.md").write_text("# P\n\n## What Changes\n\n- x\n", encoding="utf-8")
    out, _m, _c = RC.build(str(d), str(root), str(tmp_path / "p.html"))
    page = io.open(out, encoding="utf-8").read()
    assert 'const DOC = "openspec/changes/archive/2026-08-13-demo"' in page


def test_a_change_with_no_parsed_promises_says_so_rather_than_reading_green(tmp_path):
    """"Nothing was parsed" and "nothing is wrong" printed identically, in the one
    view whose whole purpose is saying what nothing answers."""
    root = tmp_path
    (root / ".git").mkdir()
    d = root / "openspec" / "changes" / "demo"
    d.mkdir(parents=True)
    (d / "proposal.md").write_text("# P\n\n## What's Changing\n\n- a bullet\n",
                                   encoding="utf-8")
    out, model, _c = RC.build(str(d), str(root), str(tmp_path / "p.html"))
    assert model["coverage"]["stats"]["promises"] == 0
    page = io.open(out, encoding="utf-8").read()
    assert "Nothing to check" in page
    assert "nothing was parsed" in page


def test_an_undone_task_is_not_counted_into_the_coverage_badge(tmp_path):
    root = tmp_path
    (root / ".git").mkdir()
    d = root / "openspec" / "changes" / "demo"
    d.mkdir(parents=True)
    (d / "proposal.md").write_text(
        "# P\n\n## What Changes\n\n- Rework `src/a/b.py`\n", encoding="utf-8")
    (d / "tasks.md").write_text(
        "# T\n\n## 1. Go\n\n- [x] 1.1 Edit `src/a/b.py`\n- [ ] 1.2 Something else\n",
        encoding="utf-8")
    _out, model, _c = RC.build(str(d), str(root), str(tmp_path / "p.html"))
    cov = model["coverage"]
    # An unstarted change with 18 tasks read as "18 uncovered" — the overclaim
    # the module exists to prevent.
    assert cov["uncovered"] == []
    assert len(cov["undone"]) == 1


# ---------------------------------------------------------------- the server


def _serve(tmp_path, doc, corpus):
    import annotate_server as S
    from functools import partial
    from http.server import ThreadingHTTPServer
    S.Handler.out_path, S.Handler.doc_path = str(corpus), str(doc)
    S.Handler.doc_key, S.Handler.root = "docs/a.md", str(tmp_path)
    S.Handler.page_path, S.Handler.is_change = str(tmp_path / "p.html"), False
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(S.Handler, directory=str(tmp_path)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _post(port, body, headers=None):
    req = urllib.request.Request(
        "http://127.0.0.1:%d/api/annotations" % port,
        data=json.dumps(body).encode("utf-8"),
        headers=headers or {"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


@pytest.fixture
def live(tmp_path):
    doc = tmp_path / "a.md"
    doc.write_text("# A\n\nbody\n", encoding="utf-8")
    srv = _serve(tmp_path, doc, tmp_path / "c.jsonl")
    yield srv.server_address[1]
    srv.shutdown()
    srv.server_close()


def test_a_cross_origin_write_is_refused(live):
    """Loopback is not authentication: a JSON body sent as text/plain is a CORS
    simple request, so no preflight refuses it and the write lands — in a corpus
    this skill forbids ever rewriting."""
    code, raw = _post(live, {"text": "t", "blk": "b1", "note": "n"},
                      {"Content-Type": "text/plain", "Origin": "https://evil.test"})
    assert code == 403 and b"refused" in raw
    assert not os.path.exists(os.path.join(os.path.dirname(str(live)), "c.jsonl"))


def test_a_page_built_for_another_document_is_refused(live):
    """One temp directory holds every rendered page for a repo, and a browser
    window outlives the server that opened it."""
    code, raw = _post(live, {"text": "t", "blk": "b1", "note": "n", "doc": "docs/OTHER.md"})
    assert code == 409
    assert json.loads(raw)["wrong_doc"] is True


def test_a_same_document_write_still_lands(live):
    code, _raw = _post(live, {"text": "t", "blk": "b1", "note": "n", "doc": "docs/a.md"})
    assert code == 200


def test_the_server_refuses_a_port_already_in_use(tmp_path):
    """HTTPServer sets allow_reuse_address = 1. On Windows that permits binding a
    port ALREADY IN ACTIVE USE — the second bind succeeds, every request is
    answered by the first server, and the second document's annotations are
    appended to the first document's corpus with nothing reported anywhere."""
    import annotate_server as S
    from http.server import ThreadingHTTPServer

    class Server(ThreadingHTTPServer):
        allow_reuse_address = False

    first = Server(("127.0.0.1", 0), S.Handler)
    port = first.server_address[1]
    try:
        with pytest.raises(OSError):
            Server(("127.0.0.1", port), S.Handler).server_close()
    finally:
        first.server_close()
