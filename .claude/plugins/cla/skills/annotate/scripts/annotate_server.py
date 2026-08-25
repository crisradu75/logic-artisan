#!/usr/bin/env python3
"""Serve a rendered document and collect annotations against it.

Stdlib only, and it runs on Windows and POSIX alike.

    python3 <plugin>/skills/annotate/scripts/render_doc.py docs/spec.md
    python3 <plugin>/skills/annotate/scripts/annotate_server.py docs/spec.md

Select any text in the browser, write a note, and it is appended to
`cla.io/annotations/<path>.jsonl` — committed, because the pair of what was
objected to and what answered it is the material a later pass actually reads,
and it has to survive a change of machine.

The corpus's shape, the merge rule and what each kind of line means live in
[annotations_store.py](annotations_store.py), which this script does not
duplicate.

Each record carries the section, the source line, the selected text verbatim and
sixty characters either side of it — enough to find the passage again after the
document moves underneath, and enough to say so when it has.
"""
import argparse
import functools
import json
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import annotations_store as store
import openspec_change
import render_change
import render_doc

# stdout buffers when it is not a terminal, and this server is normally run in
# the background — an unflushed warning is the same as no warning.
print = functools.partial(print, flush=True)


class Handler(SimpleHTTPRequestHandler):
    # HTTP/1.0 — the default — closes the connection after every response, and
    # the close races the client's read: on Windows that surfaces as an aborted
    # connection on a reply the server logged as sent. Every response here sets
    # Content-Length (this class's `_json`, SimpleHTTPRequestHandler's static
    # path, and `send_error`), which is what makes keep-alive safe to turn on.
    protocol_version = "HTTP/1.1"

    out_path = None      # the corpus
    doc_path = None      # the document, or the change directory, being annotated
    doc_key = None
    root = None
    page_path = None
    is_change = False    # a whole OpenSpec change rather than one file

    def log_message(self, fmt, *a):
        sys.stderr.write("  %s\n" % (fmt % a))

    def _local_request(self):
        """Loopback is not authentication. A browser will happily send a
        cross-origin POST to 127.0.0.1 from any page the user has open: a JSON
        body sent as `text/plain` is a CORS *simple* request, so there is no
        preflight to refuse it, and the opaque response does not matter because
        the write has already landed — in a committed corpus this skill forbids
        ever rewriting. An absent Host check also leaves DNS rebinding open,
        which turns the read side into an exfiltration path.

        Two headers close both, and cost nothing locally.
        """
        host = (self.headers.get("Host") or "").strip()
        if host.rsplit(":", 1)[0].strip("[]") not in ("127.0.0.1", "localhost", "::1"):
            return False, "Host %r is not loopback" % host
        origin = (self.headers.get("Origin") or "").strip()
        if origin and urlparse(origin).hostname not in ("127.0.0.1", "localhost", "::1"):
            return False, "Origin %r is not this page" % origin
        return True, ""

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def guess_type(self, path):
        """SimpleHTTPRequestHandler sends text/html with no charset, so a browser
        falls back to a locale default and UTF-8 arrives as mojibake."""
        t = SimpleHTTPRequestHandler.guess_type(self, path)
        base = t.split(";")[0].strip()
        if base.startswith("text/") or base in ("application/javascript", "application/json"):
            return base + "; charset=utf-8"
        return t

    # An annotation must carry these to be findable again. A tombstone, a
    # resolution and a note amendment legitimately carry only an id plus their
    # own flag, so those three are named exemptions rather than the validation
    # being skipped: a fieldless record stores happily and then surfaces
    # downstream as a phantom ANCHOR LOST, saying the document moved when it did
    # not.
    REQUIRED = ("text", "blk", "note")

    def do_GET(self):
        ok, why = self._local_request()
        if not ok:
            return self._json({"error": "refused: %s" % why}, 403)
        if urlparse(self.path).path == "/api/annotations":
            # Resolved ones are returned too. The page takes them off the reading
            # surface and keeps only their count, but the count has to be derived
            # from the records rather than trusted from anywhere else.
            problems = []
            try:
                live = store.read_all(self.out_path, problems=problems)
            except store.CorpusUnreadable as e:
                print("CORPUS UNREADABLE: %s" % e)
                return self._json({"error": str(e), "unreadable": True}, 500)
            if problems:
                print("%d unreadable line(s) in %s:" % (len(problems), self.out_path))
                for p in problems:
                    print("  %s" % p)
            return self._json({"annotations": live or [], "problems": problems})
        return SimpleHTTPRequestHandler.do_GET(self)

    def _render(self):
        """Rebuild the page from the document, on the reader's click.

        The document comes from the server's own argument and never from the
        request: this endpoint writes a file, and a path taken off the wire would
        let a page choose what it renders.

        A failure is reported to the page rather than swallowed. "Server up,
        rebuild refused" is a different sentence from "nothing happened", and
        only one of them says what to fix.
        """
        try:
            if self.is_change:
                out, model, ctxs = render_change.build(
                    self.doc_path, self.root, self.page_path)
                cov = model["coverage"]
                summary = ("%d files, %d blocks · %d uncovered, %d not checkable, "
                           "%d task(s) not done"
                           % (cov["stats"]["files"],
                              sum(len(c.blocks) for c in ctxs.values()),
                              len(cov["uncovered"]), len(cov["unchecked"]),
                              len(cov.get("undone", []))))
                print("rebuilt   %s  ->  %s" % (summary, out))
                warn = []
                unbound = [c for c in model["claims"] if not c.get("blk")]
                if unbound:
                    warn.append("%d claim(s) could not be bound to a block" % len(unbound))
                # The document path has always reported this. The change path
                # returned before reading the corpus at all, so a rebuild that
                # orphaned every anchor printed a clean summary — in the case
                # where anchors are most fragile and the corpus is largest.
                checked, lost, problems, fatal = render_change.check_change_anchors(
                    ctxs, self.out_path)
                if fatal:
                    warn.append("CORPUS UNREADABLE: %s" % fatal)
                if lost:
                    warn.append("%d annotation(s) could not be read back: %s"
                                % (len(lost), ", ".join(lost[:10])))
                if problems:
                    warn.append("%d line(s) could not be read" % len(problems))
                for w in warn:
                    print("          %s" % w)
                return self._json({"ok": True, "summary": summary, "warnings": warn})
            out, ctx, words = render_doc.build(self.doc_path, self.root, self.page_path)
        except OSError as e:
            # The type is half the diagnosis: FileNotFoundError, PermissionError
            # and IsADirectoryError all read identically as a bare str(e).
            msg = "%s: %s" % (type(e).__name__, e)
            print("REBUILD FAILED: %s" % msg)
            return self._json({"error": msg}, 500)
        except UnicodeDecodeError as e:
            msg = "%s is not valid UTF-8 (%s at byte %d)" % (self.doc_path, e.reason, e.start)
            print("REBUILD FAILED: %s" % msg)
            return self._json({"error": msg}, 500)
        except render_change.ChangeUnreadable as e:
            print("REBUILD FAILED: %s" % e)
            return self._json({"error": str(e)}, 500)
        summary = "%d blocks, %s words" % (len(ctx.blocks), format(words, ",d"))
        print("rebuilt   %s  ->  %s" % (summary, out))
        checked, lost, problems, fatal = render_doc.check_anchors(ctx, self.out_path)
        warn = []
        if fatal:
            warn.append("CORPUS UNREADABLE: %s" % fatal)
        if lost:
            warn.append("%d annotation(s) could not be read back: %s"
                        % (len(lost), ", ".join(lost[:10])))
        if problems:
            warn.append("%d line(s) could not be read" % len(problems))
        for w in warn:
            print("          %s" % w)
        return self._json({"ok": True, "summary": summary, "warnings": warn})

    def do_POST(self):
        ok, why = self._local_request()
        if not ok:
            print("REFUSED cross-origin request: %s" % why)
            return self._json({"error": "refused: %s" % why}, 403)
        path = urlparse(self.path).path
        if path == "/api/render":
            return self._render()
        if path != "/api/annotations":
            return self.send_error(404)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            rec = json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._json({"error": "bad json"}, 400)
        if not isinstance(rec, dict):
            return self._json({"error": "not an object"}, 400)

        # An amendment is decided by the PRESENCE of its key, never by its truth.
        # Testing `rec.get("deleted")` for truth reads an un-delete — the
        # {"id": ..., "deleted": false} an undo posts — as a brand-new
        # annotation, which then fails the REQUIRED check for anchor fields it
        # was never going to carry. The store has always merged an un-delete
        # correctly; nothing could ask it to.
        #
        # `deleted` must also be a real boolean. The store tests it for truth
        # while this reads it by presence, so the string "false" would arrive
        # here as an amendment and land in the file as a tombstone — deleting
        # the record the caller meant to restore.
        AMEND_KEYS = ("deleted", "resolved", "edited")
        for k in AMEND_KEYS:
            if k in rec and not isinstance(rec[k], bool):
                return self._json({"error": "%s must be true or false" % k}, 400)
        amendment = any(k in rec for k in AMEND_KEYS)

        # setdefault does not fire on a key that is present but empty, and
        # read_raw then drops an id-less line forever — a silent loss in a store
        # whose whole premise is that nothing is ever lost. And an amendment
        # names an EXISTING record: minting an id for one that does not turns it
        # into a new fieldless record, which surfaces later as a phantom ANCHOR
        # LOST saying the document moved when it did not.
        if not rec.get("id"):
            if amendment:
                return self._json({"error": "amendment with no id"}, 400)
            rec["id"] = store.new_id()
        # Every page carries the document it was built for. One temp directory
        # holds every rendered page for a repo, and a browser window outlives the
        # server that opened it — so a stale window for document A, reloaded
        # against a server now annotating B, would post A's notes into B's
        # corpus, stamped with A's name and invisible in both. The page already
        # sends `doc`; this is the only place that can compare it.
        if rec.get("doc") and rec["doc"] != self.doc_key:
            print("REFUSED a record for %s; this server is annotating %s"
                  % (rec["doc"], self.doc_key))
            return self._json(
                {"error": "this page was built for %s, but this server is "
                          "annotating %s — refusing to write into the wrong "
                          "corpus" % (rec["doc"], self.doc_key), "wrong_doc": True}, 409)

        # An amendment naming an id the corpus never held is refused, not
        # appended. Appended, it becomes a live record carrying nothing but that
        # id — no blk, no text, no note — and the page then has to render a card
        # for it. Every field reads `undefined`, and the reader is told an
        # annotation lost its place in a document nobody has touched.
        if amendment:
            damage = []
            try:
                known = store.read_all(self.out_path, include_deleted=True,
                                       problems=damage) or []
            except store.CorpusUnreadable as e:
                print("REFUSED an amendment: %s" % e)
                return self._json({"error": str(e), "unreadable": True}, 409)
            if not any(r.get("id") == rec["id"] for r in known):
                # read_raw skips a line it cannot parse. So "the id is not here"
                # and "the id is here on a line that will not parse" reach this
                # point identically, and answering 404 for the second is the
                # wrong diagnosis — it sends the reader to look for a document
                # edit that never happened. The problems list is what tells them
                # apart, which is the whole reason it is collected.
                if damage:
                    print("REFUSED an amendment against a damaged corpus: %s" % rec["id"])
                    return self._json(
                        {"error": "%d line(s) of %s could not be read, so whether"
                                  " %s is among them is unknown — resolve the file"
                                  " by hand rather than writing over it"
                                  % (len(damage), self.out_path, rec["id"]),
                         "damaged": len(damage)}, 409)
                print("REFUSED an amendment naming an unknown id: %s" % rec["id"])
                return self._json(
                    {"error": "no annotation with id %s to amend" % rec["id"]}, 404)
        if rec.get("edited") and not rec.get("note"):
            return self._json({"error": "edit with no note"}, 400)
        if not amendment:
            missing = [k for k in self.REQUIRED if not rec.get(k)]
            if missing:
                return self._json({"error": "annotation missing %s" % ", ".join(missing)}, 400)
            rec["at"] = store.now()
            rec.setdefault("doc", self.doc_key)
        else:
            rec.setdefault("at_amended", store.now())
            if rec.get("resolved"):
                rec.setdefault("resolved_at", store.now())

        try:
            store.append(self.out_path, rec)
        except store.CorpusUnreadable as e:
            # Reported, never absorbed — the same standard the GET path keeps.
            print("REFUSED TO WRITE to %s: %s" % (self.out_path, e))
            return self._json({"error": str(e), "unreadable": True}, 500)
        except OSError as e:
            # The page must be able to say "server up, write refused", which is a
            # different sentence from "no server" and the only one that says what
            # to actually fix.
            print("COULD NOT SAVE to %s: %s" % (self.out_path, e))
            return self._json({"error": "could not write %s: %s" % (self.out_path, e)}, 500)
        try:
            count = len(store.read_all(self.out_path) or [])
        except store.CorpusUnreadable as e:
            # The write landed; the count did not. Saying so beats returning 0,
            # which is a number that looks like an answer.
            print("WROTE, BUT CANNOT COUNT %s: %s" % (self.out_path, e))
            count = None
        # The whole stored record goes back, so any field stamped here reaches
        # the page rather than the page's own local copy diverging from the file.
        return self._json({"ok": True, "id": rec["id"], "record": rec, "count": count})


# A Chromium browser started with --app gives a window with no address bar, no
# tab strip and no bookmarks — the document and nothing else. Three platforms,
# so three sets of candidates. A bare name is resolved with `shutil.which` and an
# absolute one by existence: the win32 and linux lists lead with names on PATH,
# which beats guessing an install location, while the darwin list carries no PATH
# candidates at all, so there the guess is the only route.
APP_BROWSERS = {
    "win32": [
        "chrome", "msedge", "brave",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
    "darwin": [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ],
}
APP_BROWSERS["linux"] = ["google-chrome", "chromium", "chromium-browser",
                         "brave-browser", "microsoft-edge"]


def open_app_window(url, profile_dir):
    """Open the page in a chrome-less window. Returns the browser used, or None
    when there was none to use — the caller says so. Only an OSError is reported
    from here, because only that carries a reason worth printing.

    Reports, never gates: a missing browser must not stop the server, because the
    URL is printed either way and it can be opened by hand.

    The separate --user-data-dir is what makes --app reliable. Without it, an
    already-running Chrome answers the command by opening a tab in the existing
    window and the app flags are ignored entirely.
    """
    for cand in APP_BROWSERS.get(sys.platform, APP_BROWSERS["linux"]):
        exe = shutil.which(cand) if not os.path.isabs(cand) else (
            cand if os.path.exists(cand) else None)
        if not exe:
            continue
        try:
            subprocess.Popen(
                [exe, "--app=%s" % url,
                 "--user-data-dir=%s" % profile_dir,
                 "--no-first-run", "--no-default-browser-check",
                 "--window-size=1280,900"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return os.path.basename(exe)
        except OSError as e:
            print("could not start %s: %s" % (exe, e))
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("document",
                    help="a .md/.txt file, an OpenSpec change directory, or a change id")
    ap.add_argument("--port", type=int, default=8741)
    ap.add_argument("--root", help="repo root (default: resolved from git)")
    ap.add_argument("--page", help="the rendered page (default: the temp-dir path)")
    ap.add_argument("--out", help="annotations file (default: cla.io/annotations/<path>.jsonl)")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--tab", action="store_true",
                    help="open an ordinary browser tab instead of a chrome-less app window")
    a = ap.parse_args(argv)

    # A change is a directory of files that are only reviewable together, so it
    # is one target, one corpus and one page. Resolved first: a bare change id is
    # neither a file nor a directory, and would otherwise read as "no such
    # document" for a change that plainly exists.
    root = os.path.abspath(a.root) if a.root else store.repo_root(a.document)
    change_dir = openspec_change.find_change(a.document, root)
    if change_dir:
        doc, is_change = change_dir, True
    elif os.path.isfile(a.document):
        doc, is_change = os.path.abspath(a.document), False
    else:
        print("no such document or change: %s" % a.document)
        return 1
    pages = render_doc.page_dir(root)
    default_page = ("change-" + os.path.basename(doc) + ".html" if is_change
                    else store.page_name(doc, root))
    page = os.path.abspath(a.page) if a.page else os.path.join(pages, default_page)
    # Resolved once, here, and used everywhere. `os.chdir` below changes what a
    # relative path means, so a guard computed before it and a write computed
    # after it were checking and writing to two different files.
    out = os.path.abspath(a.out) if a.out else store.path_for(doc, root)

    if not os.path.exists(page):
        print("no page at %s" % page)
        print("build it first:  python3 %s %s"
              % ("render_change.py" if is_change else "render_doc.py", a.document))
        return 1

    serve_dir = os.path.dirname(page)
    os.chdir(serve_dir)
    Handler.out_path = out
    Handler.doc_path = doc
    Handler.doc_key = store.doc_key(doc, root)
    Handler.root = root
    Handler.page_path = page
    Handler.is_change = is_change
    url = "http://127.0.0.1:%d/%s" % (a.port, os.path.basename(page))

    # Bound to the loopback address and nowhere else. It has no authentication
    # because it does not need any, and that stays true only while it is local.
    class Server(ThreadingHTTPServer):
        # HTTPServer sets allow_reuse_address = 1. On Windows that permits
        # binding a port ALREADY IN ACTIVE USE: the second bind succeeds, every
        # request is answered by the first server, and the second document's
        # annotations are appended to the first document's corpus with nothing
        # reported anywhere. On POSIX the bind fails and the user is told. There
        # is no CI here, so this only ever showed up on the machine it broke on.
        allow_reuse_address = False
        daemon_threads = True

    try:
        srv = Server(("127.0.0.1", a.port), Handler)
    except OSError as e:
        print("could not bind port %d: %s" % (a.port, e))
        print("another server is probably already up — try --port %d" % (a.port + 1))
        # This one IS a gate, deliberately. Serving a second document on a port
        # already held would send its annotations to the first document's corpus.
        return 1

    problems = []
    try:
        rows = store.read_all(out, problems=problems)
    except store.CorpusUnreadable as e:
        print("CORPUS UNREADABLE — not serving until this is resolved")
        print("  %s" % e)
        return 1
    openc, done = store.split(rows or [])

    print("document  %s" % Handler.doc_key)
    print("page      %s" % url)
    print("saving to %s" % out)
    if rows is None:
        print("          no annotations yet; this is the first pass")
    else:
        print("          %d open, %d resolved" % (len(openc), len(done)))
    if problems:
        print("          %d line(s) could not be read:" % len(problems))
        for p in problems:
            print("            %s" % p)
    print("stop with ctrl-c")

    if not a.no_open:
        # Outside `pages`, which is the HTTP document root: SimpleHTTPRequestHandler
        # serves that tree with directory listings and no hidden-file filter, so
        # the app window's cookies, local storage and history were fetchable.
        prof = os.path.join(os.path.dirname(pages.rstrip("\\/")) or pages,
                            "cla-annotate-profile")

        def launch():
            if not a.tab and open_app_window(url, prof):
                return
            if not a.tab:
                print("no Chromium browser found for an app window; opening a normal tab")
            webbrowser.open(url)

        threading.Timer(0.4, launch).start()

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        # read_all returns None when there is no corpus yet — a state printed on
        # startup — so len() on it crashed the exit message, and an unreadable
        # corpus escaped as a traceback.
        try:
            rows = store.read_all(out)
        except store.CorpusUnreadable as e:
            print("\nstopped. CORPUS UNREADABLE: %s" % e)
        else:
            print("\nstopped. %s in %s"
                  % ("no annotations yet" if rows is None else "%d annotations" % len(rows), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
