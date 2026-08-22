"""The corpus: where it lives, what a line means, and what it refuses.

Every refusal here was cheap to write and expensive to omit — each one is a way
a corpus can quietly stop being a record of what was objected to without anyone
noticing it happened.
"""
import json
import os

import pytest

import annotations_store as store


@pytest.fixture
def repo(tmp_path):
    """A directory that reads as a repo root: a `.git` present, but not a real
    repository, so `repo_root` exercises its walk-up fallback deterministically
    whether or not the temp dir happens to sit inside a checkout."""
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "spec.md").write_text("# Spec\n\nBody.\n", encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------- paths


def test_corpus_mirrors_the_document_path(repo):
    got = store.path_for(str(repo / "docs" / "spec.md"), str(repo))
    assert got == str(repo / "cla.io" / "annotations" / "docs" / "spec.md.jsonl")


def test_same_basename_in_two_directories_does_not_collide(repo):
    (repo / "a").mkdir()
    (repo / "b").mkdir()
    a = store.path_for(str(repo / "a" / "README.md"), str(repo))
    b = store.path_for(str(repo / "b" / "README.md"), str(repo))
    assert a != b
    # Flattening the path would make these the same file, and one document's
    # annotations would be read as the other's.
    assert "README.md.jsonl" in a and "README.md.jsonl" in b


def test_document_outside_the_repo_gets_a_stable_external_home(repo, tmp_path):
    outside = tmp_path.parent / "elsewhere.md"
    outside.write_text("hi\n", encoding="utf-8")
    key = store.doc_key(str(outside), str(repo))
    assert key.startswith(store.EXTERNAL_DIR + "/")
    assert key == store.doc_key(str(outside), str(repo))          # stable
    assert ".." not in store.path_for(str(outside), str(repo))


def test_rel_to_root_refuses_a_sibling_that_merely_shares_a_prefix(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    sibling = tmp_path / "proj-notes"
    sibling.mkdir()
    # A naive startswith on the root string calls this one "inside", and its
    # annotations are then filed under the wrong repo.
    assert store.rel_to_root(str(sibling / "x.md"), str(root)) is None
    assert store.rel_to_root(str(root / "x.md"), str(root)) == "x.md"


def test_rel_to_root_is_case_insensitive_where_the_filesystem_is(tmp_path):
    root = tmp_path / "Proj"
    root.mkdir()
    spelled = os.path.join(str(root).replace("Proj", "Proj"), "Doc.md")
    assert store.rel_to_root(spelled, str(root)) == "Doc.md"
    if os.path.normcase("A") == os.path.normcase("a"):            # Windows
        assert store.rel_to_root(str(root / "Doc.md"),
                                 str(root).replace("Proj", "PROJ")) == "Doc.md"


def test_page_name_separates_documents_that_flatten_alike(repo):
    a = store.page_name(str(repo / "a" / "b.md"), str(repo))
    b = store.page_name(str(repo / "a-b.md"), str(repo))
    assert a != b, "two documents sharing one page file each rebuild over the other"
    assert a.endswith(".html") and not set(a) & set('/\\:*?"<>|')


def test_repo_root_walks_up_to_the_marker(repo):
    deep = repo / "docs"
    assert os.path.normcase(store.repo_root(str(deep))) == os.path.normcase(str(repo))


# ---------------------------------------------------------------- the merge rule


def test_later_lines_merge_onto_earlier_ones(tmp_path):
    p = str(tmp_path / "c.jsonl")
    store.append(p, {"id": "a1", "text": "was", "note": "florid", "at": "2026-01-01T00:00:00Z"})
    store.append(p, {"id": "a1", "resolved": True, "was": "was", "now": "now",
                     "resolved_at": "2026-02-02T00:00:00Z"})
    rows = store.read_all(p)
    assert len(rows) == 1
    # Replacing wholesale is the obvious implementation and it drops the note and
    # the text the moment anything else is written against that id.
    assert rows[0]["note"] == "florid"
    assert rows[0]["text"] == "was"
    assert rows[0]["resolved"] is True


def test_the_original_date_survives_a_later_line(tmp_path):
    p = str(tmp_path / "c.jsonl")
    store.append(p, {"id": "a1", "text": "t", "note": "n", "at": "2026-01-01T00:00:00Z"})
    store.append(p, {"id": "a1", "note": "n2", "edited": True, "at": "2026-09-09T00:00:00Z"})
    # When the objection was made is evidence. A later line carrying its own `at`
    # would redate every annotation to the day it was answered.
    assert store.read_all(p)[0]["at"] == "2026-01-01T00:00:00Z"


def test_the_merge_rule_is_not_vacuous(tmp_path):
    """Turning the rule off must change the answer, or the test above proves
    nothing about the rule.

    A parameter, not a module global. As a global it was a test seam shipped in
    the plugin that any caller could flip for the whole process — taking the `at`
    exemption with it, and restoring exactly the behaviour the docstring calls
    wrong."""
    p = str(tmp_path / "c.jsonl")
    store.append(p, {"id": "a1", "text": "t", "note": "n"})
    store.append(p, {"id": "a1", "deleted": False, "resolved": True})
    assert "note" not in store.read_all(p, merge=False)[0]
    assert "note" in store.read_all(p)[0]


def test_a_tombstone_hides_but_never_removes(tmp_path):
    p = str(tmp_path / "c.jsonl")
    store.append(p, {"id": "a1", "text": "t", "note": "n"})
    store.append(p, {"id": "a1", "deleted": True})
    assert store.read_all(p) == []
    kept = store.read_all(p, include_deleted=True)
    assert len(kept) == 1 and kept[0]["note"] == "n"
    assert len(store.read_raw(p)) == 2                       # both lines on disk


def test_a_resolved_annotation_is_kept_not_hidden(tmp_path):
    p = str(tmp_path / "c.jsonl")
    store.append(p, {"id": "a1", "text": "t", "note": "n"})
    store.append(p, {"id": "a1", "resolved": True})
    # Hiding it here is how the corpus would quietly become a list of open
    # complaints; the page is what takes it off the reading surface.
    rows = store.read_all(p)
    assert len(rows) == 1 and rows[0]["resolved"] is True
    assert store.split(rows) == ([], rows)


# ---------------------------------------------------------------- damage


def test_a_missing_file_is_not_an_empty_one(tmp_path):
    p = str(tmp_path / "nope.jsonl")
    assert store.read_all(p) is None
    store.append(p, {"id": "a1", "text": "t", "note": "n"})
    assert store.read_all(p) == store.read_all(p)
    assert store.read_all(str(tmp_path / "still-nope.jsonl")) is None


def test_unparseable_lines_are_counted_not_swallowed(tmp_path):
    p = tmp_path / "c.jsonl"
    p.write_text('{"id":"a1","note":"n","text":"t"}\nnot json at all\n{"no":"id"}\n',
                 encoding="utf-8")
    problems = []
    rows = store.read_all(str(p), problems=problems)
    assert len(rows) == 1
    # A corpus that lost half its records must not read the same as one that
    # never had any.
    assert len(problems) == 2
    assert "line 2" in problems[0] and "line 3" in problems[1]


def test_a_merge_conflict_refuses_to_load(tmp_path):
    p = tmp_path / "c.jsonl"
    p.write_text('{"id":"a1","note":"n","text":"t"}\n<<<<<<< HEAD\n{"id":"a2"}\n'
                 '=======\n{"id":"a3"}\n>>>>>>> other\n', encoding="utf-8")
    # Reading past the markers accepts both sides and fabricates a corpus.
    with pytest.raises(store.CorpusUnreadable) as e:
        store.read_all(str(p))
    assert "conflict" in str(e.value)


def test_a_conflicted_file_refuses_the_append_too(tmp_path):
    p = tmp_path / "c.jsonl"
    p.write_text("<<<<<<< HEAD\n", encoding="utf-8")
    # Checked before writing rather than after: the write is the thing that
    # cannot be taken back.
    with pytest.raises(store.CorpusUnreadable):
        store.append(str(p), {"id": "a1", "text": "t", "note": "n"})
    assert p.read_text(encoding="utf-8") == "<<<<<<< HEAD\n"


def test_invalid_utf8_raises_the_reportable_error(tmp_path):
    p = tmp_path / "c.jsonl"
    p.write_bytes(b'{"id":"a1","note":"\xff\xfe"}\n')
    # A bare UnicodeDecodeError is not CorpusUnreadable, so every caller
    # tracebacks instead of reporting and the page gets a naked 500.
    with pytest.raises(store.CorpusUnreadable):
        store.read_all(str(p))


# ---------------------------------------------------------------- the append


def test_a_torn_line_is_closed_off_before_the_next_append(tmp_path):
    p = tmp_path / "c.jsonl"
    p.write_bytes(b'{"id":"a1","text":"t","note":"n"}')      # no trailing newline
    store.append(str(p), {"id": "a2", "text": "t2", "note": "n2"})
    rows = store.read_all(str(p))
    # Appending onto the fragment makes the pair parse as neither, costing the
    # new annotation as well as the torn one.
    assert [r["id"] for r in rows] == ["a1", "a2"]


def test_the_file_stays_lf_on_every_platform(tmp_path):
    p = tmp_path / "c.jsonl"
    store.append(str(p), {"id": "a1", "text": "t", "note": "n"})
    store.append(str(p), {"id": "a2", "text": "t", "note": "n"})
    raw = p.read_bytes()
    # Text mode writes CRLF on Windows and the next POSIX append writes LF into
    # the same committed file, which is the end of the append-only diff.
    assert b"\r\n" not in raw
    assert raw.count(b"\n") == 2


def test_non_ascii_is_stored_unescaped_and_reads_back_identical(tmp_path):
    p = str(tmp_path / "c.jsonl")
    note = "the em dash — and a Greek Σ"
    store.append(p, {"id": "a1", "text": "t", "note": note})
    assert store.read_all(p)[0]["note"] == note


def test_ids_do_not_collide_inside_one_second(tmp_path):
    seen = {store.new_id() for _ in range(500)}
    # The reader keys on id and merges, so a collision silently welds two notes
    # into one record.
    assert len(seen) == 500


def test_append_creates_the_parent_directory(tmp_path):
    p = str(tmp_path / "cla.io" / "annotations" / "deep" / "x.md.jsonl")
    store.append(p, {"id": "a1", "text": "t", "note": "n"})
    assert json.loads(open(p, encoding="utf-8").read())["id"] == "a1"


def test_documents_with_annotations_is_the_inverse_of_doc_key(repo):
    for rel in ("docs/spec.md", "README.md"):
        store.append(store.path_for(str(repo / rel), str(repo)),
                     {"id": "a", "text": "t", "note": "n"})
    assert store.documents_with_annotations(str(repo)) == ["README.md", "docs/spec.md"]
