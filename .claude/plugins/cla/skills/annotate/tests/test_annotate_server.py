"""The server: what it accepts, what it refuses, and what it must never touch.

Every refusal is exercised against a real socket rather than by calling the
handler's methods, because the failures worth catching here are ones that only
show up once a request has actually been parsed — a body that is not JSON, a
field present but empty, an amendment naming nothing.
"""
import hashlib
import json
import os
import threading
import urllib.error
import urllib.request
from functools import partial
from http.server import ThreadingHTTPServer

import pytest

import annotate_server
import annotations_store as store
import render_doc


class Server:
    def __init__(self, doc, root, page, corpus, serve_dir):
        annotate_server.Handler.out_path = str(corpus)
        annotate_server.Handler.doc_path = str(doc)
        annotate_server.Handler.doc_key = store.doc_key(str(doc), str(root))
        annotate_server.Handler.root = str(root)
        annotate_server.Handler.page_path = str(page)
        # Reset explicitly. These are CLASS attributes, so the first change-mode
        # server anyone adds would otherwise leak `is_change=True` into every
        # test that ran after it, in whatever order pytest chose.
        annotate_server.Handler.is_change = False
        self.srv = ThreadingHTTPServer(
            ("127.0.0.1", 0), partial(annotate_server.Handler, directory=str(serve_dir)))
        self.port = self.srv.server_address[1]
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()

    def url(self, path):
        return "http://127.0.0.1:%d%s" % (self.port, path)

    def get(self, path):
        return self._do(urllib.request.Request(self.url(path)))

    def post(self, path, obj=None, raw=None):
        body = raw if raw is not None else json.dumps(obj or {}).encode("utf-8")
        return self._do(urllib.request.Request(
            self.url(path), data=body, headers={"Content-Type": "application/json"},
            method="POST"))

    def _do(self, req):
        # Header names are lower-cased here because they do not arrive with one
        # spelling: this handler sends "Content-Type" and SimpleHTTPRequestHandler
        # sends "Content-type", so a case-sensitive lookup passes on the API path
        # and KeyErrors on the static one.
        def headers(h):
            return {k.lower(): v for k, v in h.items()}
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read(), headers(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read(), headers(e.headers)

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.thread.join(timeout=10)


@pytest.fixture
def live(tmp_path):
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    doc = root / "docs" / "spec.md"
    doc.parent.mkdir()
    doc.write_text("# Spec\n\nThe harbour was quiet.\n\nA second paragraph.\n",
                   encoding="utf-8")
    pages = tmp_path / "pages"
    pages.mkdir()
    page = pages / "spec.html"
    render_doc.build(str(doc), str(root), str(page))
    corpus = store.path_for(str(doc), str(root))
    s = Server(doc, root, page, corpus, pages)
    s.doc, s.root, s.page, s.corpus = doc, root, page, corpus
    yield s
    s.close()


def body(res):
    return json.loads(res[1].decode("utf-8"))


VALID = {"text": "harbour", "blk": "b2", "note": "too vague", "off": 4,
         "line": 3, "sec": "Spec", "before": "The ", "after": " was quiet."}


# ---------------------------------------------------------------- the invariant


def test_the_server_never_modifies_the_document(live):
    before = hashlib.sha256(live.doc.read_bytes()).hexdigest()
    mtime = live.doc.stat().st_mtime_ns

    assert live.post("/api/annotations", VALID)[0] == 200
    rec_id = body(live.post("/api/annotations", dict(VALID, text="second")))["id"]
    assert live.post("/api/annotations", {"id": rec_id, "note": "reworded",
                                          "edited": True})[0] == 200
    assert live.post("/api/annotations", {"id": rec_id, "deleted": True})[0] == 200
    assert live.post("/api/render")[0] == 200
    assert live.get("/api/annotations")[0] == 200

    # Annotating is a read of the source. A skill that wrote to it would be
    # editing the very thing under review, and the reader's next selection would
    # be against text they never approved.
    assert hashlib.sha256(live.doc.read_bytes()).hexdigest() == before
    assert live.doc.stat().st_mtime_ns == mtime


# ---------------------------------------------------------------- writing


def test_a_valid_annotation_is_stamped_and_stored(live):
    code, raw, _ = live.post("/api/annotations", VALID)
    assert code == 200
    j = json.loads(raw)
    assert j["ok"] and j["count"] == 1
    rec = j["record"]
    assert rec["id"] and rec["at"] and rec["doc"] == "docs/spec.md"
    # The whole stored record goes back, so a field stamped here reaches the page
    # rather than the page's local copy diverging from the file.
    assert store.read_all(live.corpus)[0] == rec


@pytest.mark.parametrize("missing", ["text", "blk", "note"])
def test_an_annotation_missing_an_anchor_field_is_refused(live, missing):
    bad = dict(VALID)
    bad[missing] = ""
    code, raw, _ = live.post("/api/annotations", bad)
    # A fieldless record stores happily and surfaces later as a phantom ANCHOR
    # LOST, telling the reader their document moved when it did not.
    assert code == 400 and missing in json.loads(raw)["error"]
    assert store.read_all(live.corpus) is None


def test_an_amendment_naming_nothing_is_refused(live):
    for amendment in ({"deleted": True}, {"resolved": True}, {"edited": True, "note": "x"}):
        code, raw, _ = live.post("/api/annotations", amendment)
        # Minting an id for an amendment turns it into a new fieldless record.
        assert code == 400 and "no id" in json.loads(raw)["error"]
    assert store.read_all(live.corpus) is None


def test_an_edit_with_no_note_is_refused(live):
    rec_id = body(live.post("/api/annotations", VALID))["id"]
    code, raw, _ = live.post("/api/annotations", {"id": rec_id, "edited": True, "note": ""})
    assert code == 400 and "no note" in json.loads(raw)["error"]


def test_an_edit_keeps_the_anchor_and_the_original_date(live):
    first = body(live.post("/api/annotations", VALID))["record"]
    live.post("/api/annotations", {"id": first["id"], "note": "sharper", "edited": True})
    rows = store.read_all(live.corpus)
    assert len(rows) == 1
    assert rows[0]["note"] == "sharper"
    assert rows[0]["text"] == "harbour"          # the merge rule kept the anchor
    assert rows[0]["at"] == first["at"]          # and did not redate it
    assert len(store.read_raw(live.corpus)) == 2  # both wordings on disk


def test_a_delete_is_a_tombstone_and_the_original_line_stays(live):
    rec_id = body(live.post("/api/annotations", VALID))["id"]
    assert live.post("/api/annotations", {"id": rec_id, "deleted": True})[0] == 200
    assert body(live.get("/api/annotations"))["annotations"] == []
    # The file only ever grows: a delete that rewrote it would put the corpus one
    # interrupted write away from gone.
    assert len(store.read_raw(live.corpus)) == 2
    assert store.read_all(live.corpus, include_deleted=True)[0]["note"] == "too vague"


def test_a_resolution_is_stamped_and_stays_visible_to_the_reader(live):
    rec_id = body(live.post("/api/annotations", VALID))["id"]
    code, raw, _ = live.post("/api/annotations",
                             {"id": rec_id, "resolved": True,
                              "was": "harbour", "now": "the harbour at Syracuse"})
    assert code == 200 and json.loads(raw)["record"]["resolved_at"]
    rows = body(live.get("/api/annotations"))["annotations"]
    # Resolved ones are returned; the PAGE is what takes them off the reading
    # surface, so the count can still be derived from the records.
    assert len(rows) == 1 and rows[0]["resolved"] is True
    assert rows[0]["now"] == "the harbour at Syracuse"


def test_a_body_that_is_not_json_is_refused(live):
    assert live.post("/api/annotations", raw=b"{not json")[0] == 400
    assert live.post("/api/annotations", raw=b'["a list"]')[0] == 400
    assert store.read_all(live.corpus) is None


def test_an_unknown_endpoint_is_a_404(live):
    assert live.post("/api/anything-else")[0] == 404


# ---------------------------------------------------------------- reading


def test_an_empty_corpus_and_a_missing_one_both_read_as_no_annotations(live):
    assert body(live.get("/api/annotations")) == {"annotations": [], "problems": []}


def test_damaged_lines_are_reported_alongside_the_survivors(live):
    store.append(live.corpus, dict(VALID, id="a1"))
    with open(live.corpus, "a", encoding="utf-8", newline="\n") as fh:
        fh.write("this is not json\n")
    j = body(live.get("/api/annotations"))
    assert len(j["annotations"]) == 1
    # A corpus that lost half its records must not read the same as one that
    # never had any.
    assert len(j["problems"]) == 1


def test_an_unreadable_corpus_is_a_500_that_says_so(live):
    os.makedirs(os.path.dirname(live.corpus), exist_ok=True)
    with open(live.corpus, "w", encoding="utf-8") as fh:
        fh.write("<<<<<<< HEAD\n")
    code, raw, _ = live.get("/api/annotations")
    j = json.loads(raw)
    # The page prints three different sentences for reachable-and-empty,
    # unreachable, and unreadable; it can only do that if this flag is here.
    assert code == 500 and j["unreadable"] is True and "conflict" in j["error"]


def test_a_conflicted_corpus_refuses_the_write_rather_than_interleaving(live):
    os.makedirs(os.path.dirname(live.corpus), exist_ok=True)
    with open(live.corpus, "w", encoding="utf-8") as fh:
        fh.write("<<<<<<< HEAD\n")
    code, raw, _ = live.post("/api/annotations", VALID)
    assert code == 500 and json.loads(raw)["unreadable"] is True
    assert open(live.corpus, encoding="utf-8").read() == "<<<<<<< HEAD\n"


# ---------------------------------------------------------------- rebuilding


def test_the_rebuild_endpoint_rewrites_the_page_in_place(live):
    live.doc.write_text("# Spec\n\nThe harbour was loud.\n", encoding="utf-8")
    code, raw, _ = live.post("/api/render")
    assert code == 200
    j = json.loads(raw)
    assert j["ok"] and "blocks" in j["summary"]
    # In place, so the reader's window survives: restarting the server to pick up
    # a change closes the window they are reading in.
    assert "The harbour was loud." in live.page.read_text(encoding="utf-8")


def test_the_rebuild_reports_an_anchor_the_edit_broke(live):
    live.post("/api/annotations", VALID)
    live.doc.write_text("# Spec\n\nNothing of the kind remains.\n", encoding="utf-8")
    j = body(live.post("/api/render"))
    # A lost anchor is a finding, not a fault — and it is the signal that an edit
    # answered the objection.
    assert any("could not be read back" in w for w in j["warnings"])


def test_a_document_deleted_underneath_reports_rather_than_tracebacks(live):
    live.doc.unlink()
    code, raw, _ = live.post("/api/render")
    assert code == 500
    # The type is half the diagnosis: FileNotFoundError and PermissionError read
    # identically as a bare str(e).
    assert "FileNotFoundError" in json.loads(raw)["error"]


def test_a_non_utf8_document_reports_rather_than_tracebacks(live):
    live.doc.write_bytes(b"# Spec\n\ncaf\xe9 in cp1252\n")
    code, raw, _ = live.post("/api/render")
    assert code == 500 and "not valid UTF-8" in json.loads(raw)["error"]


def test_the_rebuild_ignores_any_document_named_in_the_request(live):
    other = live.root / "other.md"
    other.write_text("# Other\n", encoding="utf-8")
    live.post("/api/render", {"document": str(other)})
    # This endpoint writes a file; a path taken off the wire would let a page
    # choose what it renders.
    assert "Spec" in live.page.read_text(encoding="utf-8")
    assert "Other" not in live.page.read_text(encoding="utf-8")


# ---------------------------------------------------------------- serving


def test_html_is_served_as_utf8(live):
    code, raw, headers = live.get("/spec.html")
    assert code == 200
    # SimpleHTTPRequestHandler sends text/html with no charset, so the browser
    # falls back to a locale default and UTF-8 arrives as mojibake.
    assert headers["content-type"] == "text/html; charset=utf-8"
    assert b"<title>Spec</title>" in raw


def test_the_api_is_never_cached(live):
    assert live.get("/api/annotations")[2]["cache-control"] == "no-store"
