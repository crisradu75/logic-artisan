"""sweep_changes.py: the command that measures the link detector over a corpus of changes.

Its numbers are what the thresholds in `openspec_change.py` cite, so what matters is that it
reads every change it is pointed at, says so out loud when it cannot, and writes nothing.
"""
import hashlib
import os
import subprocess
import sys

import openspec_change as OC
import sweep_changes as SW

PROPOSAL = """# Proposal: demo

## Why

Because.

## What Changes

- Delete `src/legacy/sync-engine/` entirely
- A warm-ink palette with restrained typography

## Impact

- Consumers stop receiving updates
"""

TASKS = """# Tasks: demo

## 1. Delete

- [x] 1.1 Remove `src/legacy/sync-engine/` via `git rm -r`
- [ ] 1.2 Apply the warm palette and restrained typography
"""


def make_change(root, name, proposal=PROPOSAL, tasks=None, where=("openspec", "changes")):
    d = os.path.join(str(root), *where, name)
    os.makedirs(d)
    with open(os.path.join(d, "proposal.md"), "w", encoding="utf-8") as fh:
        fh.write(proposal)
    if tasks is not None:
        with open(os.path.join(d, "tasks.md"), "w", encoding="utf-8") as fh:
            fh.write(tasks)
    return d


def run(capsys, *argv):
    code = SW.main(list(argv))
    return code, capsys.readouterr().out


def summary_line(out):
    return [ln for ln in out.splitlines() if " changes read, " in ln][0]


def test_a_root_with_no_changes_exits_1_and_names_every_root(tmp_path, capsys):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    code, out = run(capsys, str(a), str(b))
    assert code == 1
    assert out.strip() == "no OpenSpec changes found under: %s, %s" % (a, b)


def test_a_missing_root_is_the_same_as_an_empty_one(tmp_path, capsys):
    code, out = run(capsys, str(tmp_path / "nope"))
    assert code == 1 and "no OpenSpec changes found" in out


def test_no_root_given_sweeps_the_working_directory(tmp_path, monkeypatch, capsys):
    make_change(tmp_path, "demo", tasks=TASKS)
    monkeypatch.chdir(tmp_path)
    code, out = run(capsys)
    assert code == 0
    assert summary_line(out).startswith("1 changes read, 0 unreadable")


def test_a_row_carries_the_same_counts_the_model_computes(tmp_path):
    d = make_change(tmp_path, "demo", tasks=TASKS)
    row = SW.measure(d)
    cov = OC.build(d, {"proposal": PROPOSAL, "tasks": TASKS})["coverage"]
    assert row["name"] == "demo"
    assert row["files"] == 2
    assert row["promises"] == cov["stats"]["promises"] > 0
    assert row["covered"] == len(cov["covered"])
    assert row["uncovered"] == len(cov["uncovered"])
    assert row["unchecked"] == len(cov["unchecked"])
    assert row["undone"] == len(cov["undone"])
    # The delete promise is met by task 1.1: a row of zeros would also "match" an empty model.
    assert row["covered"] >= 1


def test_a_directory_with_no_proposal_is_not_a_change(tmp_path):
    d = make_change(tmp_path, "demo")
    os.remove(os.path.join(d, "proposal.md"))
    assert SW.measure(d) is None


def test_the_table_and_summary_agree_with_the_rows(tmp_path, capsys):
    make_change(tmp_path, "alpha", tasks=TASKS)
    make_change(tmp_path, "beta")
    code, out = run(capsys, str(tmp_path))
    assert code == 0
    lines = out.splitlines()
    assert lines[0].split() == ["change", "files", "prom", "cov", "unc", "n/chk", "links"]
    assert lines[1].split()[0] == "alpha" and lines[2].split()[0] == "beta"
    base = os.path.join(str(tmp_path), "openspec", "changes")
    rows = [SW.measure(os.path.join(base, n)) for n in ("alpha", "beta")]
    total = sum(r["promises"] for r in rows)
    covered = sum(r["covered"] for r in rows)
    assert "%d promises" % total in summary_line(out)
    assert "covered        %5d (%.0f%%)" % (covered, 100.0 * covered / total) in out
    assert "changes with nothing covered: 1" in out        # beta has promises and no tasks
    assert "changes with no promise parsed: 0" in out


def test_quiet_prints_the_summary_and_no_table(tmp_path, capsys):
    make_change(tmp_path, "alpha", tasks=TASKS)
    code, out = run(capsys, "--quiet", str(tmp_path))
    assert code == 0
    assert "alpha" not in out
    assert out.splitlines()[0].strip() == "" and summary_line(out).startswith("1 changes read")


def test_a_change_with_no_promise_does_not_divide_by_zero(tmp_path, capsys):
    make_change(tmp_path, "empty", proposal="# Proposal: empty\n\n## Why\n\nBecause.\n")
    code, out = run(capsys, str(tmp_path))
    assert code == 0
    assert "0 promises" in out and "covered            0 (0%)" in out
    assert "changes with no promise parsed: 1" in out
    assert "changes with nothing covered: 0" in out      # nothing promised, so nothing broken


def test_a_long_change_name_is_cut_to_fit_its_column(tmp_path, capsys):
    make_change(tmp_path, "x" * 60)
    _code, out = run(capsys, str(tmp_path))
    assert ("x" * 46) in out and ("x" * 47) not in out


def test_archived_changes_are_swept_too(tmp_path, capsys):
    make_change(tmp_path, "live")
    make_change(tmp_path, "2026-01-01-old", where=("openspec", "changes", "archive"))
    _code, out = run(capsys, "--quiet", str(tmp_path))
    assert summary_line(out).startswith("2 changes read")


def test_a_root_given_twice_is_read_once(tmp_path, capsys):
    make_change(tmp_path, "demo")
    _code, out = run(capsys, "--quiet", str(tmp_path), str(tmp_path))
    assert summary_line(out).startswith("1 changes read")


def test_several_roots_are_pooled(tmp_path, capsys):
    a, b = tmp_path / "a", tmp_path / "b"
    make_change(a, "one")
    make_change(b, "two")
    _code, out = run(capsys, "--quiet", str(a), str(b))
    assert summary_line(out).startswith("2 changes read")


def test_a_malformed_change_is_counted_and_does_not_end_the_sweep(tmp_path, capsys, monkeypatch):
    make_change(tmp_path, "good")
    make_change(tmp_path, "bad")
    real = OC.build

    def build(change_dir, texts, *a, **kw):
        if os.path.basename(change_dir) == "bad":
            raise ValueError("planted")
        return real(change_dir, texts, *a, **kw)

    monkeypatch.setattr(OC, "build", build)
    code, out = run(capsys, str(tmp_path))
    assert code == 0
    assert "  ! bad: ValueError: planted" in out
    assert summary_line(out).startswith("1 changes read, 1 unreadable")
    assert "good" in out


def test_a_non_utf8_companion_file_is_reported_and_the_change_still_counts(tmp_path, capsys):
    d = make_change(tmp_path, "demo")
    with open(os.path.join(d, "tasks.md"), "wb") as fh:
        fh.write(b"# Tasks\n\n- [ ] 1.1 caf\xe9 \xff\xfe\n")
    code, out = run(capsys, str(tmp_path))
    assert code == 0
    assert "  ! demo: UnicodeDecodeError:" in out
    assert summary_line(out).startswith("1 changes read")
    assert SW.measure(d)["files"] == 1               # only the proposal could be read


def test_a_non_utf8_proposal_is_reported_by_name(tmp_path, capsys):
    d = make_change(tmp_path, "demo")
    with open(os.path.join(d, "proposal.md"), "wb") as fh:
        fh.write(b"# Proposal\n\n## What Changes\n\n- caf\xe9\n")
    code, out = run(capsys, str(tmp_path))
    assert code == 0
    assert "  ! demo: UnicodeDecodeError:" in out
    assert SW.measure(d) is None


def test_the_sweep_writes_nothing(tmp_path, capsys):
    make_change(tmp_path, "demo", tasks=TASKS)

    def snapshot():
        out = {}
        for dirpath, _dirs, names in os.walk(str(tmp_path)):
            for n in names:
                p = os.path.join(dirpath, n)
                with open(p, "rb") as fh:
                    out[p] = (hashlib.sha256(fh.read()).hexdigest(), os.stat(p).st_mtime_ns)
            out[dirpath] = sorted(os.listdir(dirpath))
        return out

    before = snapshot()
    run(capsys, str(tmp_path))
    run(capsys, "--quiet", str(tmp_path))
    assert snapshot() == before


def test_the_cli_prints_non_ascii_change_names_under_an_ascii_locale(tmp_path):
    make_change(tmp_path, "ștergere-ț")
    script = os.path.join(os.path.dirname(SW.__file__), "sweep_changes.py")
    env = {k: v for k, v in os.environ.items() if k != "PYTHONUTF8"}
    # Paths decode as UTF-8 but stdout is strict ASCII, as on a Windows codepage.
    env.update(LC_ALL="C.UTF-8", PYTHONIOENCODING="ascii")
    r = subprocess.run([sys.executable, script, str(tmp_path)], capture_output=True, env=env)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    assert "ștergere-ț" in r.stdout.decode("utf-8")
    r = subprocess.run([sys.executable, script, str(tmp_path / "empty")], capture_output=True, env=env)
    assert r.returncode == 1
