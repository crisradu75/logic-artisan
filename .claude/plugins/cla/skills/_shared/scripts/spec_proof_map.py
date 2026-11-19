"""The spec map reader of `check_spec_proof.py`: the map section and the links in it.

Walks markdown the way a renderer would (fences, list nesting, block quotes,
lazy continuation, code spans, reference definitions) so a link in a code span
or a fence is not counted as a link. Pure text. Not a command: import it, or
run `check_spec_proof.py`.
"""

from __future__ import annotations

import posixpath
import re
from pathlib import Path

from spec_proof_parse import CheckerError, FACTS_RELPATH, _FENCE_LINE, _opens_fence
from spec_proof_prose import _BACKTICK_RUN, _render_code_spans


_MAP_HEADING = re.compile(r"^##\s+Spec map\s*$", re.I)
# An ATX heading of any level (up to 3 spaces of indent, optional closing hashes). `_reads_as_map_heading`
# uses it to find a heading that reads as "Spec map" but is not the exact form above (`### Spec map`,
# `## Spec map:`, `## Spec  maps`, `## **Spec-map**`): reported, never silently read as no declaration.
_ATX_HEADING = re.compile(r"^ {0,3}#{1,6}[ \t]+(.*?)[ \t]*#*[ \t]*$")
# For the backstop in `read_spec_map`: a line that, once indent, list markers and quote markers are set aside,
# is an ATX "Spec map" heading, or the text of a setext one (followed by a `===` or `---` underline) in any of the
# forms `_map_words` reads ("Spec maps", "Spec-map", "**Spec map**").
_LINE_PREFIX = re.compile(r"^(?:\s+|>|[-*+]\s+|\d+[.)]\s+)+")
_HEADING_LIKE = re.compile(r"^#{1,6}\s*spec\s+map\s*#*\s*$", re.I)
_SETEXT_UNDERLINE = re.compile(r"^(?:=+|-{2,})\s*$")
_ANY_HEADING = re.compile(r"^#{1,6}\s")
_HTML_COMMENT = re.compile(r"<!--.*?-->")

_BULLET = re.compile(r"^[-*+]\s+(.+?)\s*$")
_CODE_START = re.compile(r"^`([^`]+)`")
# A reference definition `[label]: target` (group 1 is the label, group 2 the target). Inline targets are read by `_scan_links`.
# It must fill the line (a destination and an optional title, nothing after): `[^1]: see [beta](..)` is prose with a link.
_REF_DEF = re.compile(r"^\s{0,3}\[([^\]^][^\]]*)\]:\s*<?([^\s>]+)>?(?:\s+[\"'(].*)?\s*$")


_ITEM = re.compile(r"^([ \t]*)([-*+]|\d{1,9}[.)])([ \t]+|$)")

# (character, run length, indent, line it opened on, inside a list item, depth of block quote it opened in)
Fence = tuple[str, int, int, int, bool, int]

# One level of block quote marker: up to 3 spaces, `>`, and one optional space.
_QUOTE_MARK = re.compile(r"^ {0,3}>[ \t]?")


def _strip_quote(line: str) -> tuple[str, int]:
    """`line` without its block quote markers, and how many it had (its quote depth, 0 outside a quote). A line
    holds the content of the quote it sits in, so the markers are set aside as a list marker is."""
    depth = 0
    while True:
        m = _QUOTE_MARK.match(line)
        if not m:
            return line, depth
        line, depth = line[m.end():], depth + 1


# A line that starts a new block, so it cannot be a lazy continuation of a paragraph: an ATX heading, a
# thematic break, a block quote, or an HTML comment (which can interrupt a paragraph). (A fence or a list
# marker is checked beside it.)
_NEW_BLOCK = re.compile(r"^(?:#{1,6}(?:[ \t]|$)|(?:-[ \t]*){3,}$|(?:\*[ \t]*){3,}$|(?:_[ \t]*){3,}$|>|<!--)")


def _interrupts_paragraph(line: str, item: re.Match[str]) -> bool:
    """True when the list item `item` matched on `line` can start inside a paragraph. A bullet can; an ordered
    item only when it numbers from 1; an empty one never does. Otherwise (`2026.` at the start of a run-on
    line) the text goes on."""
    return bool(line[item.end():].strip()) and (item.group(2) in ("-", "+", "*") or item.group(2)[:-1] == "1")


class _Lists:
    """What `_fence_step` remembers between lines about the list items still open.

    `cols` holds the column where each open item's content begins. `lazy` is True when the last line was
    paragraph text, so that a following plain line indented less than the item still belongs to it
    (CommonMark's paragraph continuation text, "laziness"). `in_quote` is True when the last line sat in a
    block quote, so that only the line that opens the quote counts as the start of a block."""

    def __init__(self) -> None:
        self.cols: list[int] = []
        self.lazy = False
        self.in_quote = False


def _fence_step(line: str, n: int, fence: Fence | None, lists: _Lists) -> tuple[Fence | None, bool]:
    """Advance a code-fence tracker by one line: (new state, whether the line is a fence line or inside one).

    The state is None outside a fence. `lists` is the caller's `_Lists`, which this function keeps.
    List items follow the CommonMark rule: an item stays open while lines are indented to its content
    column, and ends at a less indented line, EXCEPT that a plain line directly after paragraph text (no blank
    line, not a heading, thematic break, quote, fence or list marker) is a lazy continuation of that paragraph
    and leaves the item open. A blank line, a fence or a heading ends the laziness.
    A fence opens on a run of 3 or more backticks (whose info string holds no backtick) or tildes at ANY
    indent: a fence inside a list item sits 4 or more spaces in and still renders as a fence, so a cap of 3
    would miss it and count a link shown in an example. A list marker before the run (`- ```) counts as
    indent. It closes on a bare run of the same character at least as long, indented at most 3 spaces deeper
    than the opener, so a more deeply indented run inside the fence is content. A fence opened inside a
    list item also ends at the first non-blank line indented less than its opener, as the item does on the
    page; a fence at the top level does not, since its content may sit less indented than its opener. A
    fence left open at the end hides the rest of the file, as on the page.
    Block quote markers (`> `) are set aside before a line is read, so a fence opened inside a quote is a
    fence; it ends where the quote does, at the first line with no marker, blank lines included. A line
    inside a fence that was opened outside a quote is read whole, markers and all. A fence opened at quote
    depth 2 also ends at the first line of depth 1: the inner quote ended there and took its fence with it."""
    in_quote_fence = fence is not None and fence[5] > 0
    orig_indent = len(line) - len(line.lstrip())
    core, quoted = _strip_quote(line)
    if in_quote_fence and quoted < fence[5]:
        fence = None  # the quote holding the fence has ended, and the fence with it; read this line afresh
    entering = False  # whether this line opens a block quote (the line before it was not quoted)
    if fence is None or in_quote_fence:
        line = core
        entering = bool(quoted) and not lists.in_quote
        lists.in_quote = bool(quoted)
    indent = len(line) - len(line.lstrip())
    if fence is not None and fence[4] and line.strip() and indent < fence[2]:
        fence = None  # the list item holding the fence has ended, and the fence with it; read this line afresh
    paragraph = False  # whether this line is paragraph text, which a following plain line may continue lazily
    if fence is None and line.strip():
        core = line.lstrip()
        item = _ITEM.match(line)
        # (only on a line indented to the open item: a less indented marker is outside its paragraph, and starts a list)
        if item and lists.lazy and (not lists.cols or indent >= lists.cols[-1]) and not _interrupts_paragraph(line, item):
            item = None  # `2026.` on a run-on line is text, not a list marker
        # The line that opens a quote starts a block too; its `>` was set aside above, so `_NEW_BLOCK` no longer sees
        # it, and it ends the list items that sit deeper than the `>` itself. The lines after it belong to the quote.
        starts_block = bool(entering or _NEW_BLOCK.match(core) or _opens_fence(_FENCE_LINE.match(line)) or item)
        if not (lists.lazy and not starts_block):
            while lists.cols and lists.cols[-1] > (orig_indent if entering else indent):
                lists.cols.pop()
        if item:
            gap = len(item.group(3))
            col = len(item.group(1)) + len(item.group(2)) + (gap if 0 < gap < 5 else 1)
            lists.cols.append(col)
            line = " " * col + line[item.end():]
        paragraph = not _NEW_BLOCK.match(core) and not _opens_fence(_FENCE_LINE.match(line)) and bool(line.strip())
    m = _FENCE_LINE.match(line)
    if fence is not None:
        lists.lazy = False
        closes = m and m.group(2)[0] == fence[0] and len(m.group(2)) >= fence[1] and not m.group(3).strip()
        if closes and len(m.group(1)) <= fence[2] + 3:
            return None, True
        return fence, True
    lists.lazy = paragraph
    if _opens_fence(m):
        lists.lazy = False
        return (m.group(2)[0], len(m.group(2)), len(m.group(1)), n, bool(lists.cols), quoted), True
    return None, False


def _reads_as_map_heading(line: str) -> bool:
    """True for an ATX heading whose words are "spec map" (or "spec maps") once emphasis, underscores,
    hyphens, non-breaking spaces and trailing punctuation are set aside."""
    m = _ATX_HEADING.match(line)
    return bool(m) and _map_words(m.group(1))


def _map_words(text: str) -> bool:
    """True when `text` is the words "spec map" (or "spec maps") once emphasis, underscores, hyphens,
    non-breaking spaces and trailing punctuation are set aside."""
    return re.sub(r"[\s_\-*`]+", " ", text).strip(" .:").lower() in ("spec map", "spec maps")


def _map_heading_like_lines(lines: list[str]) -> list[int]:
    """The 1-based numbers of the lines that look like the "Spec map" heading, in any fence, comment, list
    item or quote. Prose that only says the words, inline code, and a longer heading (`## Spec map notes`)
    do not look like it."""
    found = []
    for i, line in enumerate(lines):
        core = _LINE_PREFIX.sub("", line)
        if _HEADING_LIKE.match(core):
            found.append(i + 1)
        elif _map_words(core) and i + 1 < len(lines) and _SETEXT_UNDERLINE.match(_LINE_PREFIX.sub("", lines[i + 1])):
            found.append(i + 1)
    return found


def read_spec_map(root: Path, notes: list[str] | None = None) -> list[str] | None:
    """The paths or globs under `## Spec map` in the facts file, or None when the repo declares no map.

    A bullet is `- <path or glob>`, or `` - `<path or glob>` `` followed by any prose. A heading with
    no bullet, a second heading, or a line under it that is not a bullet raises: a declaration read
    loosely would turn the rule off without a word.

    With no declaration read, a line OUTSIDE any fence or comment that looks like the heading raises
    too (`##Spec map`, `- ## Spec map`). The same line INSIDE a fence or comment, which is how a facts
    file shows the format, is only a note: it is appended to `notes` when the caller passes a list."""
    facts = root / FACTS_RELPATH
    if not facts.is_file():
        return None
    try:
        lines = facts.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise CheckerError(f"cannot read {FACTS_RELPATH}: {exc}") from exc
    heads = []
    fence = None
    lists = _Lists()
    in_comment = False
    hidden_lines = set()  # lines inside a fence or an HTML comment, which cannot declare anything
    for n, line in enumerate(lines, 1):
        if fence is None:
            # A heading inside an HTML comment is not a declaration. (A line that begins with a comment is raw HTML.)
            if in_comment:
                in_comment = "-->" not in line
                hidden_lines.add(n)
                continue
            if line.lstrip().startswith("<!--"):
                _fence_step(line, n, None, lists)  # the comment starts a block, which ends the list item before it
                in_comment = "-->" not in line
                hidden_lines.add(n)
                continue
        fence, hidden = _fence_step(line, n, fence, lists)
        if hidden:
            hidden_lines.add(n)
            continue
        if _MAP_HEADING.match(line.rstrip()):
            heads.append(n)
        elif _reads_as_map_heading(line):
            raise CheckerError(f"{FACTS_RELPATH}:{n}: {line.strip()!r} reads as the spec map heading but is not '## Spec map'; write it exactly so, or rename it")
    if fence is not None:
        # The fence swallowed the rest of the file. A file with no map heading after it declares no map and
        # stays quiet; one with a heading after it has had its declaration hidden, which must not read as none.
        for n in range(fence[3] + 1, len(lines) + 1):
            if _MAP_HEADING.match(lines[n - 1].rstrip()) or _reads_as_map_heading(lines[n - 1]):
                raise CheckerError(f"{FACTS_RELPATH}:{fence[3]}: a code fence is never closed, so the spec map heading on line {n} is not read; close the fence")
    if not heads:
        # Backstop: the scans above can be fooled by Markdown a renderer reads differently from this line scan.
        # A line that looks like the "Spec map" heading, with no declaration read, may be a declaration that was
        # missed, and the guard going quiet is the one outcome this rule must not have. Prose that merely says
        # the words does not trigger it. Inside a fence or comment the line is most likely an example of the
        # format, so it is a note and never fails the run.
        like = _map_heading_like_lines(lines)
        shown = [n for n in like if n not in hidden_lines]
        if shown:
            raise CheckerError(f"{FACTS_RELPATH}:{shown[0]}: looks like the 'Spec map' heading but was not read as a declaration; write it exactly as '## Spec map'")
        if notes is not None:
            notes += [f"NOTE spec-map: {FACTS_RELPATH}:{n}: looks like the 'Spec map' heading but sits inside a code fence or comment, so it is not read as a declaration" for n in like]
        return None
    if len(heads) > 1:
        raise CheckerError(f"{FACTS_RELPATH}: '## Spec map' appears on lines {', '.join(map(str, heads))}; keep one")
    patterns = []
    for n in range(heads[0] + 1, len(lines) + 1):
        line = lines[n - 1].strip()
        if not line or (line.startswith("<!--") and line.endswith("-->")):
            continue
        if _ANY_HEADING.match(line):
            break
        m = _BULLET.match(line)
        if not m:
            raise CheckerError(f"{FACTS_RELPATH}:{n}: expected a '- <path or glob>' bullet under '## Spec map', got {line!r}")
        code = _CODE_START.match(m.group(1))
        pattern = (code.group(1) if code else m.group(1)).strip().replace("\\", "/")
        patterns.append(pattern.removeprefix("./"))
    if not patterns:
        raise CheckerError(f"{FACTS_RELPATH}:{heads[0]}: '## Spec map' lists no path; add a '- <path or glob>' bullet or remove the heading")
    return patterns


def _label_key(label: str) -> str:
    """A reference label as the page matches it: case folded, runs of whitespace as one space."""
    return " ".join(label.split()).casefold()


def _indented_code(line: str, cols: list[int], lazy: bool) -> bool:
    """True when `line` is a line of an indented code block, which renders no link.

    That is a non-blank line at least 4 columns past the content column of the list item it sits in (`cols`,
    as the line before it left them; column 0 outside a list), unless the line before it was paragraph text
    (`lazy`), in which case it only continues that paragraph."""
    if lazy or not line.strip():
        return False
    expanded = line.expandtabs(4)
    indent = len(expanded) - len(expanded.lstrip(" "))
    base = max((c for c in cols if c <= indent), default=0)
    return indent - base >= 4


_REF_LABEL = re.compile(r"\[((?:[^\[\]\\]|\\.)*)\]")
_INLINE_TARGET = re.compile(r"\(\s*<?([^)\s>]+)")


def _scan_links(masked: str, openers: list[tuple[int | None, bool]]) -> tuple[list[str], set[str]]:
    """(targets of the inline links, labels the reference links use) on one line with its code spans and
    comments already taken out.

    Only what renders as a link counts. An escaped bracket (`\\[x\\](..)`) opens nothing, an image
    (`![x](..)`) is not a link, and a `](..)` with no `[` before it is text. A reference link is
    `[text][label]`, `[label][]` or `[label]`; whether the label is defined is for the caller.

    `openers` holds the brackets still open: (position after the bracket, whether it opens an image). The
    caller keeps the list from line to line of one paragraph, so link text wrapped over two lines is one link;
    this function leaves the brackets it did not close in it, with the position gone (None), since the
    position belongs to a line that is over. A reference whose label is that text cannot be read then."""
    targets: list[str] = []
    labels: set[str] = set()
    i = 0
    while i < len(masked):
        c = masked[i]
        if c == "\\":
            i += 2
            continue
        if c == "!" and masked[i + 1:i + 2] == "[":
            openers.append((i + 2, True))
            i += 2
            continue
        if c == "[":
            openers.append((i + 1, False))
        elif c == "]" and openers:
            start, image = openers.pop()
            nxt = masked[i + 1:i + 2]
            if nxt == "(":
                m = _INLINE_TARGET.match(masked, i + 1)
                if m and not image:
                    targets.append(m.group(1))
            else:
                m = _REF_LABEL.match(masked, i + 1) if nxt == "[" else None
                if not image:
                    label = m.group(1) if m and m.group(1).strip() else (masked[start:i] if start is not None else "")
                    if label.strip():
                        labels.add(_label_key(label))
                if m:  # the `[label]` after the text is not an opener of its own
                    i = m.end()
                    continue
        i += 1
    openers[:] = [(None, image) for _, image in openers]
    return targets, labels


def _ends_paragraph(core: str) -> bool:
    """True when `core`, a line with its quote markers set aside, cannot continue the paragraph before it: a
    blank line, a heading, a rule, an underline, a fence, an HTML comment or a list item that can interrupt."""
    stripped = core.strip()
    if not stripped or _NEW_BLOCK.match(core.lstrip()) or _SETEXT_UNDERLINE.match(stripped):
        return True
    if _opens_fence(_FENCE_LINE.match(core)):
        return True
    item = _ITEM.match(core)
    return bool(item) and _interrupts_paragraph(core, item)


# The HTML blocks that can interrupt a paragraph (CommonMark types 1-6). Type 7, any other tag such as `<span>`,
# cannot, so a line opening one continues a paragraph like text.
_HTML_INTERRUPT = re.compile(
    r"<(?:(?:script|pre|style|textarea)(?:[\s>]|$)|!--|\?|![A-Za-z]|!\[CDATA\[|/?(?:address|article|aside|base|"
    r"basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|"
    r"figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|legend|li|link|main|menu|menuitem|nav|"
    r"noframes|ol|optgroup|option|p|param|search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|"
    r"ul)(?:[\s/>]|$))",
    re.IGNORECASE,
)


def _continues_lazily(core: str) -> bool:
    """True when `core`, a line at a LOWER quote depth than the paragraph before it, continues that paragraph
    lazily (CommonMark): it is not blank and, with fewer than four spaces of indent, starts no block. That is
    stricter than `_ends_paragraph` in one way: the line is checked against the outer container, so a list item
    that could not interrupt a paragraph (`2.`, an empty `-`) still starts a list there and ends the quote. It
    is looser in two: a setext underline (`===`) cannot be lazy, so it is text, and an indented line cannot
    start a block, so it is text too. An HTML block ends the quote only if it is one that can interrupt a
    paragraph (`_HTML_INTERRUPT`). Erring either way is not safe here: a line wrongly read as lazy can hide a
    link the page shows, and one wrongly read as a block start can split a link the page shows."""
    if not core.strip():
        return False
    body = core.lstrip(" ")
    if len(core) - len(body) >= 4 or body.startswith("\t"):
        return True  # an indented line cannot start a block here, and indented code cannot interrupt a paragraph
    return not (
        _NEW_BLOCK.match(body)
        or _opens_fence(_FENCE_LINE.match(body))
        or _ITEM.match(body)
        or _HTML_INTERRUPT.match(body)
    )


def _later_closer_in(lines: list[str], n: int, depth: int):
    """A function that says whether a run of backticks of a given length sits on a line after line `n`
    (1-based) in the same paragraph, at quote depth `depth`: the lines up to the first one that ends the
    paragraph (`_ends_paragraph`) or sits in a deeper quote, which starts a new block. A line at a LOWER depth
    that `_continues_lazily` is a lazy continuation line: on the page it is still part of the quoted
    paragraph, so a span can close there. `_render_code_spans` asks it before it lets an unpaired run open a
    span over a line break."""
    def later_closer(length: int) -> bool:
        for line in lines[n:]:
            core, d = _strip_quote(line)
            if d > depth or (not _continues_lazily(core) if d < depth else _ends_paragraph(core)):
                return False
            if any(len(m.group()) == length for m in _BACKTICK_RUN.finditer(core)):
                return True
        return False
    return later_closer


def map_links(text: str) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """([(line number, target)], [(line number, problem)]) for the Markdown links in `text`.

    Links inside a code fence, an indented code block, a code span or an HTML comment are not links on the
    rendered page and are not read, nor are an image, an escaped `\\[x\\](..)` and a reference definition no link
    uses. Block quote markers are set aside first. Code spans pair as on the page, and a span can run over the lines of one paragraph (see `_render_code_spans`). Link text wrapped over several lines of one paragraph is one link.
    One pass, line by line, so a `<!--` quoted in a code span or fence opens nothing. A fence
    closes only on a bare line of the same character at least as long as the opener. A fence or a
    comment still open at the end hides the rest of the file, as on the page, and is returned as a
    problem naming the line it began on: otherwise every later link would vanish with no word said."""
    links: list[tuple[int, str]] = []
    defs: dict[str, tuple[int, str]] = {}  # normalised label -> (line, target) of its first reference definition
    openers: list[tuple[int | None, bool]] = []  # the brackets open at the end of the last line of this paragraph
    was_quoted = False  # whether the last line read sat in a block quote
    quote_para = False  # whether the last line read was paragraph text in a block quote, which a lazy line may continue
    used: set[str] = set()  # normalised labels some `[text][label]`, `[label][]` or `[label]` uses
    fence = None
    lists = _Lists()
    comment_from: int | None = None
    all_lines = text.splitlines()
    span_open = 0  # length of a backtick run left open on an earlier line of this paragraph, 0 for none
    for n, line in enumerate(all_lines, 1):
        if fence is None and comment_from is not None:
            if "-->" not in line:
                continue
            comment_from, line = None, ""  # what follows the closer on its line is raw HTML too
        cols_before, lazy_before = list(lists.cols), lists.lazy
        fence, hidden = _fence_step(line, n, fence, lists)
        if hidden:
            openers.clear()
            span_open = 0
            continue
        core, quoted = _strip_quote(line)
        if _indented_code(core, cols_before, lazy_before):
            was_quoted, quote_para = quoted, False  # (no brackets can be open here: code never interrupts a paragraph, and a blank line cleared them)
            continue
        # A lazy continuation line: unquoted text that continues a quoted paragraph still open on the line before.
        # It keeps that paragraph open, so the quote does not start again on the next `>` line, and its open
        # brackets go on. Only an OPEN quoted paragraph can be continued: after a blank `>` line or a heading the
        # quote's paragraph is over, and a plain line is a new block.
        lazy = not quoted and quote_para and _continues_lazily(core)
        if quoted and not was_quoted:
            openers.clear()  # a quote starts here; the text before it was another block
        elif was_quoted and not quoted and not lazy:
            openers.clear()  # the quote ends here, and this line starts another block
        was_quoted = quoted or lazy
        quote_para = (bool(quoted) and not _ends_paragraph(core)) or lazy
        stripped = core.lstrip()
        if stripped.startswith("<!--"):
            openers.clear()
            # A line that begins with a comment is an HTML block: all of it is raw HTML, up to the line holding `-->`.
            if "-->" not in stripped[4:]:
                comment_from = n
            continue
        breaks = not lazy and _ends_paragraph(core)  # a lazy line is paragraph text by definition
        if breaks:
            span_open = 0  # a span never runs over the end of its paragraph
        later = None if _NEW_BLOCK.match(stripped) else _later_closer_in(all_lines, n, quoted)
        rendered, span_open = _render_code_spans(core, span_open, later)
        masked = _HTML_COMMENT.sub("", rendered)
        start = masked.find("<!--")
        if start >= 0:
            masked, comment_from = masked[:start], n
        ref = _REF_DEF.match(masked)
        if ref:
            openers.clear()
            defs.setdefault(_label_key(ref.group(1)), (n, ref.group(2)))  # the first definition of a label is the one that counts
            continue
        item = _ITEM.match(core)
        # A new list item ends the paragraph before it, unless it is an ordered item that does not start at 1 or an
        # empty one: those cannot interrupt a paragraph, so on the page the text goes on.
        new_item = not lazy and bool(item) and bool(core[item.end():].strip()) and (item.group(2) in ("-", "+", "*") or item.group(2)[:-1] == "1")
        closes = not lazy and bool(_NEW_BLOCK.match(stripped) or _SETEXT_UNDERLINE.match(stripped.strip()))  # a heading, a rule or an underline
        if not stripped.strip() or closes or new_item:
            openers.clear()  # a blank line, a heading, a rule, an underline or a new list item ends the paragraph
        targets, labels = _scan_links(masked, openers)
        if closes:
            openers.clear()  # a heading's own unclosed bracket ends with it
        links += [(n, target) for target in targets]
        used |= labels
    # A definition renders nothing until a link uses its label, so an unused one links no spec.
    links += [(n, target) for label, (n, target) in defs.items() if label in used]
    links.sort(key=lambda link: link[0])
    issues = []
    if fence is not None:
        issues.append((fence[3], "a code fence is never closed, so the rest of the map is not read"))
    if comment_from is not None:
        issues.append((comment_from, "an HTML comment is never closed, so the rest of the map is not read"))
    return links, issues


def _link_path(map_rel: str, target: str) -> str | None:
    """The repo-relative path a link in the map file `map_rel` points at, or None for an empty target.

    The fragment and query are dropped, a relative target is resolved against the map file's folder and
    a leading `/` means the repo root. A URL or a path that leaves the repo lands on no spec path."""
    target = re.split(r"[#?]", target.replace("\\", "/"), maxsplit=1)[0]
    if not target:
        return None
    joined = target.lstrip("/") if target.startswith("/") else posixpath.join(posixpath.dirname(map_rel), target)
    return posixpath.normpath(joined)


def _glob_regex(pattern: str) -> re.Pattern[str]:
    """A repo-relative glob as a regex: `*` and `?` stay inside one folder, `**/` crosses folders, the rest is literal.

    Not `fnmatch`, where `*` also crosses `/`: a map declared as `docs/*.md` would then take in every
    nested file, and any link in one of them would count as the map linking that spec."""
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out))
