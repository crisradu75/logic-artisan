"""The server: what it accepts, what it refuses, and what it must never touch.

Every refusal is exercised against a real socket rather than by calling the
handler's methods, because the failures worth catching here are ones that only
show up once a request has actually been parsed — a body that is not JSON, a
field present but empty, an amendment naming nothing.
"""
import hashlib
import http.client
import io
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
        # `e.read()` is INSIDE the try, not inside an except handler. An
        # exception raised while handling another is not caught by a sibling
        # clause of the same try, and `urlopen` raises `HTTPError` as soon as the
        # status line and headers are parsed — the error body is read lazily.
        # So reading it from within `except HTTPError:` left the 4xx/5xx branch
        # unprotected while the success branch was covered, and the 404 is the
        # exact endpoint #187 failed on. Verified rather than assumed:
        # `HTTPDefaultErrorHandler.http_error_default` raises with `fp` unread.
        err = None
        try:
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return r.status, r.read(), headers(r.headers)
            except urllib.error.HTTPError as e:
                err = e
            return err.code, err.read(), headers(err.headers)
        except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            # An HTTP status arrives as HTTPError and is a RESULT. Anything else
            # is the transport failing, and used to propagate raw — so the test
            # went red with `ConnectionAbortedError` and no indication of which
            # request, while the server's own log showed it had answered
            # normally. That is issue #187's whole shape, and the ten minutes it
            # costs to work out are what this re-raise removes.
            #
            # Deliberately NOT retried or swallowed: a transport error here means
            # the server closed the connection uncleanly, which is a defect in
            # the server, not weather. Making it legible is the fix; making it
            # disappear would hide the next one.
            raise AssertionError(
                "transport error talking to %s %s: %s: %s — the server did not "
                "close this connection cleanly" % (
                    req.get_method(), req.full_url, type(exc).__name__, exc)
            ) from exc

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


def test_an_un_delete_is_accepted_and_restores_the_record(live):
    """`deleted: false` is an amendment, decided by the key's PRESENCE.

    Tested for TRUTH it reads as a brand-new annotation, which then fails the
    anchor-field check for fields an undo was never going to send — so the page's
    Undo could not work at all. The store has always merged an un-delete
    correctly; nothing could ask it to."""
    rec_id = body(live.post("/api/annotations", VALID))["id"]
    live.post("/api/annotations", {"id": rec_id, "deleted": True})
    assert body(live.get("/api/annotations"))["annotations"] == []

    code, raw, _ = live.post("/api/annotations", {"id": rec_id, "deleted": False})
    assert code == 200, json.loads(raw).get("error")
    rows = body(live.get("/api/annotations"))["annotations"]
    assert len(rows) == 1 and rows[0]["id"] == rec_id
    assert rows[0]["text"] == "harbour"          # the merge rule kept the anchor
    assert len(store.read_raw(live.corpus)) == 3   # and nothing was rewritten


@pytest.mark.parametrize("key", ["deleted", "resolved", "edited"])
def test_a_non_boolean_amendment_flag_is_refused(live, key):
    """The server reads these by presence and the store reads `deleted` by truth.

    So the string "false" would arrive as an amendment and land in the file as a
    tombstone — deleting the record the caller meant to restore."""
    rec_id = body(live.post("/api/annotations", VALID))["id"]
    code, raw, _ = live.post("/api/annotations",
                             {"id": rec_id, key: "false", "note": "x"})
    assert code == 400 and "true or false" in json.loads(raw)["error"]
    assert body(live.get("/api/annotations"))["annotations"][0]["note"] == "too vague"


@pytest.mark.parametrize("amendment", [
    {"deleted": True}, {"resolved": True}, {"edited": True, "note": "x"},
    {"deleted": False},
])
def test_an_amendment_naming_an_unknown_id_is_refused(live, amendment):
    """Appended, it becomes a live record carrying nothing but that id.

    The page then has to draw a card for it: every field reads `undefined`, and
    the reader is told an annotation lost its place in a document nobody has
    touched."""
    live.post("/api/annotations", VALID)
    code, raw, _ = live.post("/api/annotations", dict(amendment, id="never-existed"))
    assert code == 404 and "never-existed" in json.loads(raw)["error"]
    assert len(store.read_raw(live.corpus)) == 1        # nothing was written


def test_an_amendment_against_a_damaged_corpus_says_so_rather_than_404(live):
    """"Not in the file" and "in the file on a line that will not parse" reach
    the same branch, because read_raw skips what it cannot read. Answering 404
    for the second sends the reader to look for a document edit that never
    happened."""
    live.post("/api/annotations", VALID)                # the file exists now
    with open(live.corpus, "a", encoding="utf-8") as fh:
        fh.write("{not json at all\n")
    code, raw, _ = live.post("/api/annotations", {"id": "unknown", "deleted": True})
    j = json.loads(raw)
    assert code == 409 and j["damaged"] == 1
    assert "could not be read" in j["error"]


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


def test_a_refused_request_still_consumes_its_body(live):
    """Issue #187. The 404 path used to reply without reading `rfile`, and
    `send_error` sends `Connection: close` — so the socket closed with the
    request still in its receive buffer and the OS sent RST instead of FIN. The
    client's read of an already-written response then raced that RST.

    A 2-byte body loses that race about once per full-suite run, which is why the
    original report could not be reproduced. A large one loses it often, so this
    posts 8 MiB: measured on the unfixed server, `ConnectionAbortedError`
    (WinError 10053) on the client while the server logged its 404.

    HONEST ABOUT WHAT THIS IS. It is a race, so it is a probabilistic test, not a
    deterministic one — a single unfixed run can pass. The loop is what makes it
    bite, and `Server._do` now converts the transport error into a named
    AssertionError rather than letting a bare OSError escape. Both endpoints are
    exercised because they fail for opposite reasons: `/api/anything-else` closes
    (RST), `/api/render` stays alive and corrupts the NEXT request on the
    connection, which only a connection-reusing client would ever see.
    """
    big = json.dumps({"x": "a" * (8 * 1024 * 1024)}).encode("utf-8")
    for _ in range(3):
        assert live.post("/api/anything-else", raw=big)[0] == 404
        assert live.post("/api/render", raw=big)[0] == 200


def test_a_kept_alive_connection_is_not_desynced_by_an_unread_body(live):
    """The DETERMINISTIC half of the drain, and the one that needs no race.

    `/api/render` replies through `_json`, which keeps the connection alive. An
    unread body therefore does not RST anything — it sits in the stream, and the
    NEXT request on that connection is parsed starting from its bytes. `urllib`
    opens a fresh connection per request and can never see this; `http.client`
    reuses one, so it can.

    Without the drain the second request below reads `{"x": "aaa…` as its
    request line and the assertion fails every time, on every platform. That is
    what makes this the companion to the probabilistic 8 MiB test rather than a
    duplicate of it.
    """
    conn = http.client.HTTPConnection("127.0.0.1", live.port, timeout=30)
    try:
        big = json.dumps({"x": "a" * (1024 * 1024)}).encode("utf-8")
        conn.request("POST", "/api/render", body=big,
                     headers={"Content-Type": "application/json"})
        first = conn.getresponse()
        first.read()
        assert first.status == 200

        # Same connection, deliberately. This is the assertion.
        conn.request("GET", "/api/annotations")
        second = conn.getresponse()
        second.read()
        assert second.status == 200, (
            "the second request on a reused connection did not get a clean "
            "response, so the first request's body was left in the stream"
        )
    finally:
        conn.close()


def _offline_handler(headers, stream):
    """A handler with just enough state to drive `_read_body` directly."""
    h = annotate_server.Handler.__new__(annotate_server.Handler)
    h.headers = headers
    h.rfile = stream
    h.connection = None          # `_read_body` skips the socket timeout
    return h


def test_the_drain_stops_at_the_cap():
    """The cap is BEHAVIOUR, not a constant to assert against itself.

    An earlier version asserted `MAX_BODY == 32 * 1024 * 1024` and nothing else,
    so the capping expression was never executed: deleting it reopened the memory
    hole with the whole suite green, and the batch's cap mutant died on the
    literal rather than on anything the server does.
    """
    cap = annotate_server.Handler.MAX_BODY
    h = _offline_handler({"Content-Length": str(4 * cap)}, io.BytesIO(b"a" * (2 * cap)))

    got, complete = h._read_body()

    assert len(got) == cap
    assert h.rfile.tell() == cap, "the cap must stop the READ, not the return value"
    assert complete is False, (
        "a capped read leaves the rest in the stream, so it must report itself "
        "incomplete and make the caller close"
    )


def test_a_malformed_content_length_reports_itself_incomplete():
    """A length that is not a number leaves a body of unknown size in the stream.

    Measured before this reported itself: a folded duplicate header
    (`Content-Length: 34, 34`) made the server answer 400 about missing fields
    for a request whose fields were all present — it never saw the body — and
    then the next request on the connection came back 501 with the annotation
    JSON parsed as the HTTP method.
    """
    h = _offline_handler({"Content-Length": "34, 34"}, io.BytesIO(b"a" * 34))

    got, complete = h._read_body()

    assert (got, complete) == (b"", False)


def test_a_short_body_reports_itself_incomplete():
    """A client that declares more than it sends leaves the connection in an
    unknown state, which is the same problem as the cap."""
    h = _offline_handler({"Content-Length": "100"}, io.BytesIO(b"a" * 10))

    got, complete = h._read_body()

    assert (len(got), complete) == (10, False)


def _chunked(stream_bytes):
    return _offline_handler({"Transfer-Encoding": "chunked"}, io.BytesIO(stream_bytes))


class _EndlessStream:
    """A reader that repeats `pattern` forever, and refuses past `limit`.

    A `BytesIO` CANNOT test an unbounded loop: it runs out, the decoder sees an
    empty read and returns, and a runaway decoder looks exactly like a correct
    one. Both loop guards were measured to survive their own mutants for that
    reason — the two rules agree on every finite input.

    Serving forever makes them disagree, and the limit turns a runaway into a
    failed assertion rather than a hung suite.
    """

    def __init__(self, pattern, limit=1 << 20):
        self.pattern, self.limit, self.served, self.buf = pattern, limit, 0, b""

    def _fill(self, n):
        while len(self.buf) < n:
            self.served += len(self.pattern)
            if self.served > self.limit:
                raise AssertionError(
                    "the decoder consumed over %d bytes without returning — it "
                    "is not bounded" % self.limit
                )
            self.buf += self.pattern

    def read(self, n):
        self._fill(n)
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def readline(self, n=-1):
        limit = 1024 if n is None or n < 0 else n
        self._fill(limit)
        cut = self.buf.find(b"\n", 0, limit)
        end = limit if cut < 0 else cut + 1
        out, self.buf = self.buf[:end], self.buf[end:]
        return out


def _endless_chunked(pattern):
    return _offline_handler({"Transfer-Encoding": "chunked"}, _EndlessStream(pattern))


def test_a_negative_chunk_size_terminates_the_decode():
    """`int(b"-1", 16)` is -1 in Python, and -1 walked through every guard the
    first decoder had: not zero so the trailer branch was skipped, `total + size`
    DECREASED so the cap never tripped, `while want > 0` consumed nothing, and the
    loop went round again. Measured at 17.5 MB read against a 64 KiB cap, still
    spinning — an unbounded loop reachable by a REFUSED cross-origin request,
    which is strictly worse than the RST the decode was written to avoid.

    Driven from an ENDLESS stream, not a `BytesIO`: a finite one runs out and the
    unguarded decoder returns too, so the guard and its absence agree on every
    input a fixed buffer can supply.
    """
    got, complete = _endless_chunked(b"-1\r\n\r\n")._read_body()

    assert (got, complete) == (b"", False)


def test_endless_trailers_end_the_read_rather_than_the_process():
    """The trailer loop counted nothing against the cap and had no iteration
    limit, so a peer sending trailer lines forever kept it running — the socket
    timeout never fires while data keeps arriving. Measured at 6.5 million lines
    with no return.

    Endless for the same reason as the test above. The first chunk header ends
    the body and opens the trailer section, and the trailers then never stop.
    """
    handler = _offline_handler(
        {"Transfer-Encoding": "chunked"},
        _EndlessStream(b"X-Pad: yyyyyyyyyyyyyyyyyyyy\r\n"),
    )
    handler.rfile.buf = b"0\r\n"

    got, complete = handler._read_body()

    # Incomplete, not complete: the budget ran out with bytes still in the stream.
    assert (got, complete) == (b"", False)


def test_a_chunk_size_line_with_no_newline_is_refused():
    """`readline(64)` returns 64 bytes with no terminator when the line is
    longer, and the prefix before `;` still parses — so a long chunk extension
    is read as a size and the rest of the line consumed as body.

    The sizes are chosen so the UNGUARDED decoder succeeds rather than merely
    failing differently: `0x26` is 38, and exactly 38 padding bytes plus a CRLF
    remain after `readline(64)` takes its 64. Without the newline check the
    decode returns `(b"zzz…", True)` — a wrong body, reported clean. Asserting
    only `complete is False` did not discriminate, because the unguarded path
    also ended up incomplete on a less carefully built line.
    """
    line = b"26;" + b"z" * 97 + b"\r\n"
    got, complete = _chunked(line + b"0\r\n\r\n")._read_body()

    assert (got, complete) == (b"", False)


def test_a_missing_inter_chunk_crlf_is_refused():
    """Discarding two bytes whatever they are eats the first two characters of
    the next size line when a peer omits the CRLF, and mis-frames the rest."""
    got, complete = _chunked(b"5\r\nhello0\r\n\r\n")._read_body()

    assert complete is False


def test_a_well_formed_chunked_body_still_decodes():
    """The non-vacuity partner: five guards that refuse everything would pass
    every test above and serve nothing.

    Written first with `3\\r\\n you\\r\\n` — a 4-byte chunk declared as 3 — and the
    decode came back `(b"hello yo", False)`, because the inter-chunk CRLF check
    landed on `u\\r`. The fixture was wrong rather than the decoder, and the guard
    added two edits earlier is what said so.
    """
    got, complete = _chunked(b"5\r\nhello\r\n4\r\n you\r\n0\r\n\r\n")._read_body()

    assert (got, complete) == (b"hello you", True)


def test_an_undrainable_body_closes_the_connection_rather_than_desyncing(live):
    """The live half of "drained or closed, never neither".

    The three `_read_body` tests above are offline unit tests of the report; this
    is the one that proves the caller ACTS on it. A malformed `Content-Length`
    leaves a body of unknown size in the stream, so the only safe reply is a 400
    plus a close — `http.client` sees `will_close`, and a client that tried to
    reuse the connection would otherwise read the annotation JSON as the next
    request line and get a 501.
    """
    payload = json.dumps(VALID).encode("utf-8")
    conn = http.client.HTTPConnection("127.0.0.1", live.port, timeout=30)
    try:
        conn.putrequest("POST", "/api/annotations", skip_accept_encoding=True)
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", "%d, %d" % (len(payload), len(payload)))
        conn.endheaders()
        conn.send(payload)
        res = conn.getresponse()
        res.read()
        assert res.status == 400
        assert res.will_close, (
            "a body that could not be drained must close the connection; "
            "leaving it open desyncs the next request on it"
        )
    finally:
        conn.close()


def test_a_chunked_body_is_decoded_and_leaves_the_connection_clean(live):
    """`BaseHTTPRequestHandler` does not decode chunked framing, so the server
    does.

    An earlier cut answered 411 and closed instead. That was worse twice over: a
    411 is a strange reply to a request this server can read perfectly well, and
    closing on an undrained body just moved #187's own race onto a different
    reply. The second request on the same connection is the assertion — without
    the decode, it is parsed from the leftover chunk framing.
    """
    payload = json.dumps(VALID).encode("utf-8")
    conn = http.client.HTTPConnection("127.0.0.1", live.port, timeout=30)
    try:
        conn.putrequest("POST", "/api/annotations", skip_accept_encoding=True)
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Transfer-Encoding", "chunked")
        conn.endheaders()
        conn.send(b"%x\r\n%s\r\n0\r\n\r\n" % (len(payload), payload))
        first = conn.getresponse()
        first.read()
        assert first.status == 200

        conn.request("GET", "/api/annotations")
        second = conn.getresponse()
        assert second.status == 200
        assert len(json.loads(second.read())["annotations"]) == 1
    finally:
        conn.close()


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


def test_an_amendment_against_a_conflicted_corpus_is_a_409_not_a_500(live):
    """The amendment path reads the corpus BEFORE `store.append`, so it meets an
    unreadable corpus one step earlier than a new annotation does and answers
    409, not the 500 the append path gives.

    Both pre-existing unreadable-corpus tests post a new record, so they take the
    append path and never reach this branch — and the page puts the server's
    sentence straight into the undo strip, so the code and the message are both
    read by a human."""
    rec_id = body(live.post("/api/annotations", VALID))["id"]
    with open(live.corpus, "a", encoding="utf-8") as fh:
        fh.write("<<<<<<< HEAD\n")
    code, raw, _ = live.post("/api/annotations", {"id": rec_id, "deleted": False})
    j = json.loads(raw)
    assert code == 409, "an amendment against a conflicted corpus must not 500"
    assert j["unreadable"] is True
    assert "conflict" in j["error"]


# --- the html target: dispatch, refusal, and where the path comes from -----
# Found wholly untested by review: the browser suite sets `Handler.kind`
# directly, so `target_kind()` and the `main()` branching that calls it were
# exercised by nothing at all.


@pytest.mark.parametrize("name,want", [
    ("doc.md", "doc"),
    ("doc.markdown", "doc"),
    ("page.html", "html"),
    ("page.htm", "html"),
    ("PAGE.HTML", "html"),
    ("notes.txt", "doc"),
    ("archive.tar.gz", "doc"),
    ("no-extension", "doc"),
])
def test_target_kind_routes_by_extension(name, want):
    assert render_doc.target_kind(name) == want


def test_the_server_asks_for_the_extension_rule_rather_than_repeating_it():
    """One rule, read by the CLI and by the server. Two copies is how
    `render_doc.py foo.html` and the server come to disagree about what a file
    renders as.

    An earlier version of this test asserted the server's source contains no
    ".html" at all, which is not the property: it legitimately builds a page
    FILENAME ending ".html" for a change. A test that cannot tell a routing
    decision from a filename fails on correct code, which is worse than not
    checking.
    """
    import inspect

    assert inspect.getsource(render_doc).count("HTML_SUFFIXES = ") == 1
    server_src = inspect.getsource(annotate_server)
    assert "render_doc.target_kind(" in server_src, \
        "the server does not ask for the rule"
    assert "HTML_SUFFIXES" not in server_src, \
        "the server keeps its own copy of the suffix list"
    assert '.htm"' not in server_src and ".htm'" not in server_src, \
        "the server tests an html suffix itself instead of asking"


def test_a_refused_document_is_reported_rather_than_thrown(tmp_path, monkeypatch):
    """The CLI prints a clean REFUSED. Without the same branch here the identical
    failure reaches the browser as a traceback, so one entry point is actionable
    and the other is not."""
    import render_html

    doc = tmp_path / "clash.html"
    doc.write_text('<p data-blk="mine">text</p>', encoding="utf-8")

    sent = {}

    class Fake(object):
        is_change = False
        kind = "html"
        doc_path = str(doc)
        root = str(tmp_path)
        page_path = str(tmp_path / "page.html")
        out_path = str(tmp_path / "corpus.jsonl")

        def _json(self, obj, code=200):
            sent["obj"], sent["code"] = obj, code
            return obj

    with pytest.raises(render_html.Refused):
        render_html.build(str(doc), str(tmp_path), str(tmp_path / "page.html"))

    out = annotate_server.Handler._render(Fake())
    assert sent["code"] == 500
    assert "refused" in sent["obj"]["error"]
    assert "data-blk" in sent["obj"]["error"]
    assert out is sent["obj"]


def test_the_renderers_warnings_reach_the_page_not_just_the_console(tmp_path):
    """`ctx.warnings` were printed by the CLI and discarded by the server, so a
    document opened through the server was never told what the same document
    told the command line."""
    doc = tmp_path / "rel.html"
    doc.write_text('<p>text</p><img src="pic.png">', encoding="utf-8")
    sent = {}

    class Fake(object):
        is_change = False
        kind = "html"
        doc_path = str(doc)
        root = str(tmp_path)
        page_path = str(tmp_path / "page.html")
        out_path = str(tmp_path / "corpus.jsonl")

        def _json(self, obj, code=200):
            sent["obj"] = obj
            return obj

    annotate_server.Handler._render(Fake())
    warnings = sent["obj"].get("warnings", [])
    assert any("not self-contained" in w for w in warnings), warnings
