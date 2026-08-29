"""Mutants for the two amendment defects the annotation server carried.

Both were latent rather than live: the page had no undo, so nothing ever posted
an un-delete and nothing ever named an id the corpus did not hold. Adding the
undo makes both reachable, which is why they are fixed first and proved here.

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
]
