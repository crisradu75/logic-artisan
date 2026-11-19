"""The change page's derived panes: the spec diffs, the overview and the coverage.

Reads the main specs a delta changes, shapes their diff cards, and builds the
overview and coverage views from the change model. Not a command: import it, or
run `render_change.py`.
"""

import html
import os
import openspec_change as OC

from render_change_markup import _unplaced, after_block, esc_attr, heading_lookup


def _path_parts(change_dir):
    """The folder's path split into parts, case-folded by `os.path.normcase`,
    which folds case on Windows only — so `Changes\\Archive` is
    `changes/archive` on Windows and stays as written elsewhere, including on a
    case-insensitive macOS volume."""
    return os.path.normcase(os.path.normpath(os.path.abspath(change_dir))).split(os.sep)


def is_archived(change_dir):
    """Whether the change sits in `openspec/changes/archive/`."""
    parts = _path_parts(change_dir)
    return len(parts) >= 3 and parts[-2] == "archive" and parts[-3] == "changes"


def read_skip_specs(change_dir):
    """The change's `skip_specs` flag from its `.openspec.yaml`. A file that is
    absent or unreadable sets nothing: the flag only ever quiets a finding, so
    losing it shows the reader more, never less."""
    try:
        with open(os.path.join(change_dir, ".openspec.yaml"), "r", encoding="utf-8") as fh:
            return OC.skip_specs_set(fh.read())
    except (OSError, UnicodeDecodeError):
        return False


def main_specs_dir(change_dir):
    """The main specs folder that belongs to this change, or None.

    Derived from the change folder, never from the repo root, because a change
    may live in a store of its own: `<x>/openspec/changes/<id>` and
    `<x>/openspec/changes/archive/<id>` both answer `<x>/openspec/specs`. A
    change folder in neither place has no main specs folder, and answers None
    rather than borrowing the repo's, which may belong to another store."""
    real = os.path.normpath(os.path.abspath(change_dir)).split(os.sep)
    parts = _path_parts(change_dir)
    if is_archived(change_dir):
        base = real[:-3]
    elif len(parts) >= 2 and parts[-2] == "changes":
        base = real[:-2]
    else:
        return None
    return os.path.join(os.sep.join(base) or os.sep, "specs")


NO_SPECS_DIR = ("this change folder is not under openspec/changes/ or "
                "openspec/changes/archive/, so it has no main specs to compare against")


def main_spec_path(specs_dir, cap):
    # A capability is a path, posix-spelled in its key.
    return os.path.join(specs_dir, *cap.split("/"), "spec.md")


def read_main_specs(specs_dir, caps):
    """`{capability: text}` for each main spec, None where there is none, and the
    exception where one exists and cannot be read.

    A main spec that cannot be read becomes a note on its requirement rather
    than a failed build: the change's own files are what the page is for, and
    the server's rebuild only reports OSError, UnicodeDecodeError and
    ChangeUnreadable — anything else would reach the reader as "Failed to
    fetch". Main specs are never added to the page's files, so they never
    become tabs and never count toward "N files".
    """
    out = {}
    for cap in caps:
        p = main_spec_path(specs_dir, cap)
        if not os.path.isfile(p):
            out[cap] = None
            continue
        try:
            with open(p, "r", encoding="utf-8") as fh:
                out[cap] = fh.read()
        except UnicodeDecodeError as e:
            out[cap] = ValueError("not valid UTF-8 (%s at byte %d)" % (e.reason, e.start))
        except OSError as e:
            out[cap] = e
    return out


def _diff_note(rec, spec):
    """The note for a requirement with no word diff. `spec` is the path of the
    main spec this requirement was compared against — or would have been — as
    the reader should look for it; None when the change has no specs folder."""
    if spec is None:
        return "no base · " + NO_SPECS_DIR
    return {
        "archived": "no base · this change is archived, and archiving wrote its "
                    "text into %s, so the text it replaced is gone. Not the same "
                    "as unchanged." % spec,
        "no-main-spec": "no base · %s does not exist" % spec,
        "unreadable": "no base · %s could not be read: %s" % (spec, rec["why"]),
        "not-in-main": "no base · %s has no requirement with this exact name" % spec,
        # Only what was measured: the same words in the same order. Markup,
        # list markers and line breaks are not compared.
        "same": "no word-level difference from %s" % spec,
    }[rec["state"]]


def diff_markup(rec, spec):
    """One requirement's card: its word diff against the main spec at `spec`,
    or the note saying why there is none. The words compared are the body as a
    reader sees it — markup and list markers off — from below the heading
    through its last scenario. `rd-del`/`rd-ins`, not `<del>`/`<ins>`, which
    the document's own markdown already uses."""
    if rec["state"] != "diff" or spec is None:
        return ('<div class="rd rd-note"><span class="rd-h">%s</span></div>'
                % html.escape(_diff_note(rec, spec), quote=False))
    parts = []
    for tag, words in rec["ops"]:
        if tag == "gap":
            parts.append('<span class="rd-gap">… %d unchanged word%s …</span>'
                         % (words, "" if words == 1 else "s"))
            continue
        text = html.escape(" ".join(words), quote=False)
        parts.append(text if tag == "eq" else
                     '<span class="rd-%s">%s</span>' % (tag, text))
    return ('<div class="rd"><span class="rd-h">changes against %s</span>'
            '<p class="rd-t">%s</p></div>'
            % (html.escape(spec, quote=False), " ".join(parts)))


def spec_label(specs_dir, root, cap):
    """The main spec's path as the note names it: relative to the repo root
    when it is inside it, in full otherwise, with forward slashes. None when
    there is no specs folder."""
    if specs_dir is None:
        return None
    p = os.path.abspath(main_spec_path(specs_dir, cap))
    try:
        rel = os.path.relpath(p, os.path.abspath(root)) if root else p
    except ValueError:                       # another drive, on Windows
        rel = p
    if rel.startswith(".."):
        rel = p
    return rel.replace(os.sep, "/")


def diff_cards(model, bodies, ctxs, specs_dir=None, root=None):
    """Put each MODIFIED requirement's diff card under its heading — a sibling,
    placed with `after_block`, never inside the heading's block. A heading that
    cannot be placed is recorded in `model["unplaced"]`."""
    by_id = {c["id"]: c for c in model["claims"]}
    for cid, rec in model.get("diffs", {}).items():
        c = by_id.get(cid)
        if not c:
            continue
        blk, why = heading_lookup(ctxs.get(c["file"]), c)
        if not blk:
            _unplaced(model, c, "diff", why)
            continue
        card = diff_markup(rec, spec_label(specs_dir, root, rec["cap"]))
        bodies[c["file"]] = after_block(bodies[c["file"]], blk, card)
    return bodies


BUCKET_LABELS = {"covered": "covered", "uncovered": "uncovered",
                 "unchecked": "not checkable"}


def overview_pane(ov, labels):
    """The change's shape on one screen. Plain HTML with no `data-blk`, like the
    coverage pane, so nothing in it can be annotated; data only, no prose about
    the page. Where a part of the change gave nothing to show, the pane says
    "nothing parsed" and what it looked for, because an empty heading reads as
    an empty change. A promise links back to its bullet through `cov-go`, the
    coverage pane's own link, so the one click handler serves both."""
    out = ['<h1 style="margin-top:1.4rem">Overview</h1>']
    def none(text):
        return '<p class="ov-none">%s</p>' % html.escape(text, quote=False)

    if ov["why"]:
        out.append('<p class="ov-why">%s</p>' % html.escape(ov["why"], quote=False))
    elif ov["why_state"] == "empty":
        out.append(none("nothing parsed · the proposal's ## Why section is empty"))
    else:
        out.append(none("nothing parsed · the proposal has no ## Why section"))

    out.append('<div class="ov"><h2 id="ov-promises">Promises — %d</h2>' % len(ov["promises"]))
    if ov["promises"]:
        out.append('<ul class="ov-list">')
        for c, bucket in ov["promises"]:
            chips = '<span class="ov-chip ov-%s">%s</span>' % (bucket, BUCKET_LABELS[bucket])
            if c["id"] in ov["breaking"]:
                chips += '<span class="ov-chip ov-breaking">breaking</span>'
            text = html.escape(_clip(c["text"], PROMISE_CLIP), quote=False)
            link = ('<span class="cov-go" data-go-blk="%s">%s</span>'
                    % (esc_attr(c["blk"]), text) if c.get("blk")
                    else '<span class="cov-dead">%s</span>' % text)
            out.append('<li class="ov-p">%s %s</li>' % (chips, link))
        out.append("</ul>")
    else:
        out.append(none("nothing parsed · no top-level bullets under the proposal's "
                        "## What Changes"))
    out.append("</div>")

    out.append('<div class="ov"><h2 id="ov-requirements">Requirements</h2>')
    if ov["skip_specs"] and not ov["reqs"]:
        out.append(none("no spec changes (skip_specs)"))
    elif ov["skip_specs"]:
        # Shown, never hidden behind the flag: OpenSpec's own validate refuses
        # this combination, and the reader needs to see both halves of it.
        out.append(none("conflict · .openspec.yaml sets skip_specs, but this change "
                        "has spec deltas"))
    elif not ov["reqs"]:
        out.append(none("no spec deltas"))
    if ov["reqs"]:
        groups = ["ADDED", "MODIFIED", "REMOVED"]
        renamed = any(ov["renamed"].values())
        head = "".join("<th>%s</th>" % g.lower() for g in groups)
        if renamed:
            head += "<th>renamed</th>"
        out.append('<div class="tw"><table class="ov-reqs"><thead><tr><th>capability</th>'
                   '<th></th>%s</tr></thead><tbody>' % head)
        for cap, counts in ov["reqs"].items():
            cells = "".join('<td class="ov-n">%d</td>' % counts[g] for g in groups)
            if renamed:
                cells += '<td class="ov-n">%d</td>' % ov["renamed"].get(cap, 0)
            kind = ov["status"].get(cap, "unknown")
            out.append('<tr><td><code>%s</code></td><td><span class="ov-chip ov-%s">%s</span>'
                       '</td>%s</tr>' % (html.escape(cap, quote=False), kind, kind, cells))
        out.append("</tbody></table></div>")
    out.append("</div>")

    done, total = ov["tasks"]
    out.append('<div class="ov"><h2 id="ov-tasks">Tasks</h2>')
    if not ov["tasks_file"]:
        out.append(none("nothing parsed · this change has no tasks.md"))
    elif not total:
        out.append(none("nothing parsed · tasks.md holds no task lines (a list item "
                        "starting with a checkbox, such as - [ ])"))
    else:
        out.append('<p class="ov-tasks"><span class="ov-n">%d of %d done</span>'
                   '<span class="ov-bar"><i style="width:%.1f%%"></i></span></p>'
                   % (done, total, 100.0 * done / total))
    out.append("</div>")
    return "".join(out)


PROMISE_CLIP = 300


def _clip(text, n):
    """`text` cut to `n` characters, with an ellipsis when anything was cut."""
    return text if len(text) <= n else text[:n].rstrip() + "…"


def coverage_pane(model, labels):
    cov = model["coverage"]
    st = cov["stats"]
    out = ['<h1 style="margin-top:1.4rem">Coverage</h1>',
           '<p class="cov-prov">read %d files · %d promises · %d claims · %d links · '
           '%d tasks (%d done)</p>'
           % (st["files"], st["promises"], st["claims"], st["links"],
              st["tasks"], st["tasks_done"]),
           '<p class="cov-note"><strong>Uncovered means no link was found</strong>, which is '
           'not the same as no link existing — every row says what was looked for. '
           'A bullet naming no file and no identifier gives nothing to match on at all; '
           'those are listed separately rather than counted against the change.</p>']

    def go(claim, inner, cls="cov-go"):
        if not claim.get("blk"):
            return '<span class="cov-dead">%s</span>' % inner
        return ('<span class="%s" data-go-blk="%s">%s</span>'
                % (cls, esc_attr(claim["blk"]), inner))

    def rows(items, css, heading):
        if not items:
            return ""
        buf = ['<div class="%s"><h2>%s — %d</h2>' % (css, heading, len(items))]
        for row in items:
            c = row["claim"]
            src = "%s · %s %s" % (labels.get(c["file"], c["file"]), c["kind"], c["num"])
            pays = "".join(
                '<div class="cov-pay"><span class="cov-pay-k%s">%s %s</span>%s</div>'
                % (" weak" if link["kind"] == "wording" else "",
                   labels.get(o["file"], o["file"]), o["num"],
                   go(o, html.escape(o["text"][:150], quote=False)))
                for o, link in row.get("pays", [])[:6])
            buf.append('<div class="cov-row">%s<p class="cov-claim">%s</p>'
                       '%s%s</div>'
                       % (go(c, src, "cov-go cov-src-go"),
                          go(c, html.escape(c["text"][:300], quote=False)),
                          '<span class="cov-why">%s</span>' % html.escape(row["why"])
                          if row.get("why") else "", pays))
        buf.append("</div>")
        return "".join(buf)

    if not st["promises"]:
        # "Nothing was parsed" and "nothing is wrong" printed identically, in the
        # one view whose whole purpose is saying what nothing answers.
        out.append('<div class="cov cov-bad"><h2>Nothing to check</h2>'
                   '<div class="cov-row"><span class="cov-src">proposal</span>'
                   '<p class="cov-claim">No <code>## What Changes</code> bullets were '
                   'found.</p><span class="cov-why">this tab has nothing to check — '
                   'coverage below is empty because nothing was parsed, not because '
                   'nothing is owed</span></div></div>')
    out.append(rows(cov["uncovered"], "cov cov-bad", "Uncovered"))
    out.append(rows(cov.get("undone", []), "cov cov-grey", "Not done"))
    out.append(rows(cov["unchecked"], "cov cov-grey", "Not checkable"))
    out.append(rows(cov["covered"], "cov", "Covered"))

    caps = [c for c in cov["capabilities"] if c["why"]]
    if caps:
        out.append('<div class="cov cov-bad"><h2>Capabilities — %d</h2>' % len(caps))
        for c in caps:
            out.append('<div class="cov-row"><span class="cov-src">capability</span>'
                       '<p class="cov-claim">%s</p><span class="cov-why">%s</span></div>'
                       % (html.escape(c["name"]), html.escape(c["why"])))
        out.append("</div>")

    # A requirement whose label or diff could not be put beside its heading is
    # listed here, never dropped: the page would otherwise show it as an
    # ordinary passage and say nothing.
    unplaced = model.get("unplaced", [])
    if unplaced:
        out.append('<div class="cov cov-grey"><h2>Not placed — %d</h2>' % len(unplaced))
        for row in unplaced:
            c = row["claim"]
            out.append('<div class="cov-row"><span class="cov-src">%s · requirement</span>'
                       '<p class="cov-claim">%s</p><span class="cov-why">its %s could not '
                       'be placed: %s</span></div>'
                       % (html.escape(labels.get(c["file"], c["file"])),
                          html.escape(c["text"]),
                          " and ".join(sorted(row["what"], key=("label", "diff").index)),
                          html.escape(row["why"])))
        out.append("</div>")
    return "".join(out)
