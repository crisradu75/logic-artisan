"""Mutants for the server's html dispatch.

The browser suite sets `Handler.kind` directly, so `target_kind()` and the
`main()` branching that calls it were exercised by nothing at all until a
coverage review said so. These are the guards for that seam.

    python3 plugin-tests/mutate.py plugin-tests/mutants/annotate/test_annotate_server.py
"""
from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
DOC = PLUGIN / "skills" / "annotate" / "scripts" / "render_doc.py"
SRV = PLUGIN / "skills" / "annotate" / "scripts" / "annotate_server.py"
TESTS = [DEV / "tests" / "skills" / "annotate" / "test_annotate_server.py"]

MUTANTS = [
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
