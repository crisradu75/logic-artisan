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
TESTS = [DEV / "tests" / "skills" / "annotate" / "test_annotate_server.py"]

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
     "        raw = self._read_body()",
     '        raw = (self._read_body()'
     ' if urlparse(self.path).path == "/api/annotations" else b"")',
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
     "        chunks, remaining = [], min(remaining, self.MAX_BODY)",
     "        chunks, remaining = [], remaining",
     TESTS),

    ("a chunked body is accepted again, so its framing is neither counted nor "
     "decoded and the leftovers desync the connection",
     SERVER,
     "        if self._chunked_request():",
     "        if False and self._chunked_request():",
     TESTS),
]
