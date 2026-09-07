"""Mutants for the annotation server's defects, across two changes.

FIVE amendment mutants came first. All were latent rather than live: the page had
no undo, so nothing ever posted an un-delete and nothing ever named an id the
corpus did not hold. Adding the undo makes them reachable, which is why they were
fixed first and proved here.

FOUR more cover issue #187 — a reply that closed the connection while the request
body was still unread, so the OS answered RST instead of FIN — and the two
behaviours the fix added around it: the drain cap, and the refusal of a chunked
body whose length cannot be counted.

EVERY MUTANT HERE DIES DETERMINISTICALLY, which took a second pass to arrange.
The obvious #187 mutant kills only through the RST race, and a batch that
intermittently reports a survivor is what trains a reader to skip the whole list.
It is killed instead by the keep-alive desync test, which needs no race: leave a
body unread on a connection that stays open and the NEXT request on it is parsed
from those bytes, every time. The `MAX_BODY` mutant likewise used to die on a
literal assertion rather than on anything the server does.

    python3 plugin-tests/mutate.py plugin-tests/mutants/annotate/test_annotate_server.py
"""
from pathlib import Path

DEV = Path(__file__).resolve().parents[2]                 # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
SERVER = PLUGIN / "skills" / "annotate" / "scripts" / "annotate_server.py"
SRV = PLUGIN / "skills" / "annotate" / "scripts" / "annotate_server.py"
DOC = PLUGIN / "skills" / "annotate" / "scripts" / "render_doc.py"
TESTS = [DEV / "tests" / "skills" / "annotate" / "test_annotate_server.py"]

# Anchors are matched against the target's RAW BYTES, so a multi-line one must
# spell the separator the way that file actually spells it. A bare `\n` matches
# on the working copy that just wrote the file and matches nothing once it has
# been checked out on Windows — a preflight abort of the whole batch, on a clone
# that changed nothing. Prefer a single-line anchor; use this when the line is
# not unique on its own.
_NL = "\r\n" if b"\r\n" in SERVER.read_bytes() else "\n"

# `core.autocrlf` is on in this clone, so a target file may be CRLF on disk while
# these anchors are written with LF. A multi-line anchor then matches nothing and
# mutate.py aborts the WHOLE batch at preflight — every mutant here stops
# checking anything, for a reason unrelated to any of them. Read the separator
# off the file rather than assuming it.
def _nl(path):
    return "\r\n" if b"\r\n" in path.read_bytes() else "\n"


def _a(text, path=None):
    """An anchor carrying the target file's own line separator."""
    return text.replace("\n", _nl(path if path is not None else DOC))


MUTANTS = [
    ("an amendment is decided by TRUTH again, so an un-delete reads as a new "
     "annotation and is refused for anchor fields it never carries",
     SERVER,
     "amendment = any(k in rec for k in AMEND_KEYS)",
     "amendment = any(rec.get(k) for k in AMEND_KEYS)",
     TESTS),

    ("the boolean check goes, so the string \"false\" lands as a tombstone over "
     "the record the caller meant to restore",
     SERVER,
     "if k in rec and not isinstance(rec[k], bool):",
     "if False and k in rec and not isinstance(rec[k], bool):",
     TESTS),

    ("an amendment naming an id the corpus never held is appended again",
     SERVER,
     'if not any(r.get("id") == rec["id"] for r in known):',
     'if False and not any(r.get("id") == rec["id"] for r in known):',
     TESTS),

    ("a damaged corpus answers 404 — the wrong diagnosis, which sends the reader "
     "to look for a document edit that never happened",
     SERVER,
     "                if damage:",
     "                if False:",
     TESTS),

    ("an amendment against a conflicted corpus 500s from the append path "
     "instead of 409ing from the read",
     SERVER,
     "                print(\"REFUSED an amendment: %s\" % e)",
     "                raise",
     TESTS),

    # Issue #187. Both of these restore the shape that made the flake: a reply
    # that closes the connection while the request body is still unread, so the
    # OS answers RST instead of FIN and the client's read races it.
    ("only /api/annotations consumes its body again, so the 404 path closes on "
     "an unread request and RSTs the client — #187 exactly",
     SERVER,
     "        raw, complete = self._read_body()",
     '        raw, complete = (self._read_body()'
     ' if urlparse(self.path).path == "/api/annotations" else (b"", True))',
     TESTS),

    ("the drain cap drops below a real body, so anything larger is left unread "
     "and the close is unclean again",
     SERVER,
     "    MAX_BODY = 32 * 1024 * 1024",
     "    MAX_BODY = 1024",
     TESTS),

    ("the cap goes entirely, so a declared Content-Length is buffered whole and "
     "the fix for one hole becomes a memory hole",
     SERVER,
     "            want, out = min(declared, cap), []",
     "            want, out = declared, []",
     TESTS),

    ("chunked framing stops being decoded, so the body reads as empty and its "
     "leftovers desync the connection",
     SERVER,
     '            if "chunked" in (self.headers.get("Transfer-Encoding") or "").lower():',
     '            if False:',
     TESTS),

    ("an incomplete read stops closing the connection, so whatever is left in "
     "the stream is read as the next request on it",
     SERVER,
     "        if not complete:",
     "        if False:",
     TESTS),

    # Single-line anchor deliberately. A multi-line one needs the separator built
    # off the file (`_NL`), because a bare \n matches nothing on a CRLF checkout
    # — the trap that made a sibling batch abort at preflight on any fresh clone.
    ("a capped read reports itself complete, so the caller never closes and the "
     "truncated remainder is read as the next request",
     SERVER,
     '            return b"".join(out), declared <= cap',
     '            return b"".join(out), True',
     TESTS),

    # The five below are the chunked decoder's own bounds. Every one of them was
    # ABSENT in the first cut, and two of those absences were unbounded loops
    # reachable by a refused cross-origin request.
    ("a negative chunk size stops being rejected, so it skips the cap check, "
     "consumes nothing, and the decoder never terminates",
     SERVER,
     "            if size < 0:",
     "            if False:",
     TESTS),

    # BOTH lines, deliberately. Mutating the loop condition ALONE survives, and
    # it is not the guard's fault: `readline(min(budget, 1024))` bounds the read
    # by itself, because budget lands exactly on 0 and `readline(0)` returns b"".
    # Traced under `while True`: 283 iterations, then an empty read ends it. Two
    # expressions that agree on every input are one rule written twice, so the
    # mutant has to remove the rule — which is exactly the shape review measured
    # at 6.5 million trailer lines with no return.
    ("the trailer read loses BOTH its bound and its budget, so a peer sending "
     "trailer lines forever keeps it running while the socket timeout never "
     "fires — the shape review measured at 6.5M lines",
     SERVER,
     "                while budget > 0:" + _NL
     + "                    trailer = self.rfile.readline(min(budget, 1024))",
     "                while True:" + _NL
     + "                    trailer = self.rfile.readline(1024)",
     TESTS),

    ("a size line no longer has to end in a newline, so an over-long chunk "
     "extension is read as a size and its remainder as body",
     SERVER,
     _a('            if not line or not line.endswith(b"\\n"):'),
     "            if not line:",
     TESTS),

    ("the inter-chunk CRLF goes back to being discarded unverified, eating the "
     "next size line's first two bytes when a peer omits it",
     SERVER,
     _a('            if self.rfile.read(2) not in (b"\\r\\n", b"\\n\\r", b"\\n"):'),
     "            if False:",
     TESTS),

    ("running out of trailer budget reports COMPLETE, so the caller leaves the "
     "connection open on a stream that still has bytes in it",
     SERVER,
     '                return b"".join(out), False' + _NL + "            if total + size > cap:",
     '                return b"".join(out), True' + _NL + "            if total + size > cap:",
     TESTS),

    # ---- the html dispatch, added when a coverage review found this seam
    # exercised by nothing at all ----

    ("the extension rule stops recognising .htm, so half the html suffixes "
     "render as escaped markup",
     DOC,
     'HTML_SUFFIXES = (".html", ".htm")',
     'HTML_SUFFIXES = (".html",)',
     TESTS),

    ("the extension match stops folding case, so an uppercase .HTML file "
     "renders as plain text",
     DOC,
     'return "html" if os.path.splitext(path)[1].lower() in HTML_SUFFIXES else "doc"',
     'return "html" if os.path.splitext(path)[1] in HTML_SUFFIXES else "doc"',
     TESTS),

    ("a refusal reaches the browser as an exception instead of a message",
     SRV,
     "                except render_html.Refused as e:",
     "                except NotImplementedError as e:",
     TESTS),

    ("the renderer's warnings go back to being discarded by the server",
     SRV,
     "        warn = list(renderer_warnings)",
     "        warn = []",
     TESTS),
]
