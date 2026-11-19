"""Sentence counting and the Purpose-section checks of `check_spec_proof.py`.

Pure text: a sentence counter that masks code spans, URLs and abbreviations,
and the Purpose paragraph reader. Not a command: import it, or run
`check_spec_proof.py`.
"""

from __future__ import annotations

import re

from spec_proof_parse import _H2, _PURPOSE_H, SpecFile, _fence_after


# A path of a live spec (group 1) or of a delta in an active or archived change (group 2), relative to the repo root.
_SPEC_PATH = re.compile(r"^openspec/(?:specs/([^/]+)|changes/(?:archive/)?[^/]+/specs/([^/]+))/")


_ABBREVIATIONS = {
    "inc", "ltd", "corp", "approx", "etc", "vs", "cf", "dr", "mr", "mrs",
    "fig", "vol", "dept", "nos",
}
# A sentence ends at ., ! or ? (plus any closing quote, bracket or emphasis mark) followed by
# whitespace and then ANYTHING: the next sentence may open with a code span, digit, quote,
# paren or bold, so no capital letter is required.
_SENT_END = re.compile(r"([.!?])((?:[\"')\]”’]|\*\*|[*_])*)\s+(?=(\S))")
_URL = re.compile(r"(?:https?://|www\.)\S*[^\s.,;:!?)\]]")


# A code span opens and closes with a backtick run of the same length (CommonMark).
_CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)")


_BACKTICK_RUN = re.compile(r"(?<!`)`+(?!`)")


def _render_code_spans(t: str, open_len: int = 0, later_closer=None) -> tuple[str, int]:
    """(`t` with each code span replaced by `CODE`, the length of a backtick run left open at its end).

    Backtick runs pair the way a Markdown page pairs them: left to right, each opener with the next run of
    the same length, so a backtick with no partner stays literal. Used for links, where what renders matters.
    A span can run over the lines of one paragraph, so the caller carries state from line to line:
    `open_len` is the run a line before left open (0 for none), and the text of `t` up to the first run of
    that length is inside the span. `later_closer(length)` says whether a later line of the paragraph holds
    a run of that length; only then does an unpaired run on `t` open a span, which hides the rest of `t`.
    With no `later_closer`, an unpaired run stays literal, as at the end of a paragraph."""
    out, pos = "", 0
    if open_len:
        closer = next((m for m in _BACKTICK_RUN.finditer(t) if len(m.group()) == open_len), None)
        if closer is None:
            return "", open_len  # the whole line is inside the span
        out, pos = "CODE", closer.end()
    runs = [m for m in _BACKTICK_RUN.finditer(t, pos)]
    i = 0
    while i < len(runs):
        length = len(runs[i].group())
        partner = next((k for k in range(i + 1, len(runs)) if len(runs[k].group()) == length), None)
        if partner is not None:
            out += t[pos:runs[i].start()] + "CODE"
            pos, i = runs[partner].end(), partner + 1
        elif later_closer is not None and later_closer(length):
            return out + t[pos:runs[i].start()] + "CODE", length
        else:
            i += 1
    return out + t[pos:], 0


def _mask_code_spans(t: str) -> str:
    """Replace each code span with `CODE` for the sentence count. A page pairs a stray backtick with the
    next one and hides the text between them, but an author who left one stray meant the later pair as the
    span, so when any backtick is left unpaired no span is masked and every backtick is dropped. That
    over-counts when a real span holds a period and a stray sits elsewhere in the text (`Run `a. b` and
    ` more.` counts 2): a note that may say 'more than one sentence' for a text that has one. The other
    choice, masking the pairs and dropping the leftover, under-counts the case the test pins instead
    (`A stray ` mark. Then `code` here.`), and no rule tells the two apart."""
    masked = _CODE_SPAN.sub("CODE", t)
    return t.replace("`", "") if "`" in masked else masked


def count_sentences(text: str) -> int:
    """How many sentences `text` holds: 0 for blank text, else the boundaries found plus one.

    A period is not a boundary after an abbreviation (`Inc.`, `approx.`, `etc.`), a dotted
    initialism (`U.S.`, `e.g.`), or `No.` before a digit. A code span, a URL, a link target
    and an ellipsis (`...` or the one-character form) are masked first, so a period inside
    them never counts, and an ellipsis never ends a sentence. This errs toward fewer
    boundaries: a missed second sentence is a missed note, a false one is noise. The one known
    exception is an unpaired backtick (see `_mask_code_spans`)."""
    t = _mask_code_spans(" ".join(text.split()))
    t = re.sub(r"\]\([^)]*\)", "]", t)
    t = _URL.sub("URL", t)
    t = re.sub(r"\.{3,}|…", ",", t)
    if not t:
        return 0
    boundaries = 0
    for m in _SENT_END.finditer(t):
        if m.group(1) == ".":
            prev = re.search(r"(\S+)$", t[: m.start()])
            word = re.sub(r"^[\"'(\[*_“‘]+", "", prev.group(1)) if prev else ""
            if re.fullmatch(r"(?:[A-Za-z]\.)+[A-Za-z]", word) or word.lower() in _ABBREVIATIONS:
                continue
            if word.lower() == "no" and m.group(3).isdigit():
                continue
        boundaries += 1
    return boundaries + 1


def _ends_a_sentence(line: str) -> bool:
    """True when `line` closes a sentence at its end, judged as `count_sentences` judges it: more text after
    it would start another (so an abbreviation such as `Inc.` at the end of a wrapped line does not)."""
    return count_sentences(line + " x") > 1


def _purpose_paragraphs(text: str) -> list[list[str]] | None:
    """The paragraphs (runs of non-blank lines, each line stripped) under `## Purpose` (any case),
    up to the next `##` heading. None if there is no Purpose."""
    paras: list[list[str]] = []
    cur: list[str] = []
    found, fence = False, None
    for line in text.splitlines():
        was_fenced = fence is not None
        fence = _fence_after(line, fence)
        if not was_fenced and fence is None:
            if _PURPOSE_H.match(line):
                found = True
                continue
            if found and _H2.match(line):
                break
        if not found:
            continue
        if line.strip():
            cur.append(line.strip())
        elif cur:
            paras.append(cur)
            cur = []
    if cur:
        paras.append(cur)
    return paras if found else None


def _spec_names_in(paths: set[str]) -> set[str]:
    """The spec names whose live file, or whose delta in any change (active or archived), is among `paths`."""
    out = set()
    for p in paths:
        m = _SPEC_PATH.match(p)
        if m:
            out.add(m.group(1) or m.group(2))
    return out


def purpose_notes(files: list["SpecFile"], touched: set[str] | None = None) -> list[str]:
    """One NOTE line per live spec whose Purpose is not a `**Serves:**` line plus exactly one sentence.

    `touched` is the set of spec names the branch changes (`_spec_names_in`); only those are noted, so an
    older spec the branch leaves alone does not repeat its note on every run. None means every live spec.

    A blank line after the first paragraph makes that whole paragraph the Serves line, so a hard-wrapped
    Serves line is one line, unless its first line already ends a sentence: then that line alone is the
    Serves line and the rest of the paragraph is text after it. With no blank line the Purpose is one
    paragraph and its first line is the Serves line, the rest being the sentence.

    Advisory: the repo's spec rules call this form advisory, so these are notes, never problems."""
    notes = []
    for f in files:
        if f.kind != "live" or (touched is not None and f.spec not in touched):
            continue
        paras =_purpose_paragraphs(f.text)
        why = None
        if paras is None:
            why = "has no '## Purpose' section"
        elif not paras or re.match(r"(?i)tbd\b", paras[0][0].lstrip("*_ ")):
            why = "Purpose is empty or TBD"
        else:
            if len(paras) > 1 and len(paras[0]) > 1 and _ends_a_sentence(paras[0][0]):
                # The first line already closes the Serves sentence, so the next line is the sentence after it,
                # and the paragraphs below are more text after that: not one long Serves line.
                serves_lines, rest = paras[0][:1], paras[0][1:] + [ln for p in paras[1:] for ln in p]
            elif len(paras) > 1:
                serves_lines, rest = paras[0], [ln for p in paras[1:] for ln in p]
            else:
                serves_lines, rest = paras[0][:1], paras[0][1:]
            m = re.match(r"\*\*Serves:\*\*\s*(.*)$", " ".join(serves_lines))
            if m and re.match(r"(?i)\W*tbd\b", m.group(1)):
                why = "Purpose is empty or TBD"
            elif not m or not m.group(1).strip():
                why = "Purpose does not open with a '**Serves:** <who or what it serves>' line"
            elif count_sentences(m.group(1)) > 1:
                why = "the Serves line holds more than one sentence"
            else:
                n = count_sentences(" ".join(rest))
                if n == 0:
                    why = "Purpose has no sentence after the Serves line"
                elif n > 1:
                    why = f"Purpose has {n} sentences after the Serves line, expected one"
        if why:
            notes.append(f"NOTE purpose: {f.rel}: {why}")
    return notes
