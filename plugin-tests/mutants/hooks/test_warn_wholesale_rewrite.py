"""Mutant batch for `tests/hooks/test_warn_wholesale_rewrite.py`.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_warn_wholesale_rewrite.py

`hooks/warn-wholesale-rewrite.py` warns, after a `Write`, when a tracked file was replaced by a
materially shorter one. It is quiet by design (most tests assert silence), so a mutant that makes it
speak too often or too rarely both matter. The mutants re-break one return path at a time:

- scoping: only `Write`, only a string path, only inside a repo;
- the baseline: `HEAD:./<path>` (the `./` is load-bearing), no baseline is silent, a git that ran and
  could not resolve the path says so on stderr, a binary baseline is silent;
- the two thresholds and the minimum baseline, each at its edge, and the reported numbers;
- the worktree fallback, `_repo_root_for`, and `_head_exists`.

Not in the batch: making a path outside any repo fall back to the project root. The inner
`relative_to` that follows raises the same `ValueError` and returns the same 0, so no input tells
the two apart. An unobservable mutant in a batch is a survivor by construction.

Anchors sit within one physical line, or take the file's own line ending. Paths resolve from this
file.
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]  # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
HOOK = PLUGIN / "hooks" / "warn-wholesale-rewrite.py"
TARGETS = [DEV / "tests" / "hooks" / "test_warn_wholesale_rewrite.py"]

_SPEC = [
    # ---- thresholds -----------------------------------------------------------------------
    ("the minimum baseline moves", "MIN_BASELINE_WORDS = 150", "MIN_BASELINE_WORDS = 151"),
    ("the minimum baseline is dropped",
     "    if baseline is None or baseline < MIN_BASELINE_WORDS:",
     "    if baseline is None:"),
    ("a baseline exactly at the minimum is skipped",
     "    if baseline is None or baseline < MIN_BASELINE_WORDS:",
     "    if baseline is None or baseline <= MIN_BASELINE_WORDS:"),
    ("a missing baseline is compared",
     "    if baseline is None or baseline < MIN_BASELINE_WORDS:",
     "    if baseline < MIN_BASELINE_WORDS:"),
    ("the keep ratio moves", "KEEP_RATIO = 0.85", "KEEP_RATIO = 0.80"),
    ("the dropped-words floor moves", "MIN_DROPPED_WORDS = 80", "MIN_DROPPED_WORDS = 81"),
    ("the dropped-words floor is dropped",
     "    if dropped < MIN_DROPPED_WORDS or new_words >= baseline * KEEP_RATIO:",
     "    if new_words >= baseline * KEEP_RATIO:"),
    ("the keep ratio is dropped",
     "    if dropped < MIN_DROPPED_WORDS or new_words >= baseline * KEEP_RATIO:",
     "    if dropped < MIN_DROPPED_WORDS:"),
    ("a file exactly at the keep ratio warns",
     "    if dropped < MIN_DROPPED_WORDS or new_words >= baseline * KEEP_RATIO:",
     "    if dropped < MIN_DROPPED_WORDS or new_words > baseline * KEEP_RATIO:"),
    ("a drop exactly at the floor is silent",
     "    if dropped < MIN_DROPPED_WORDS or new_words >= baseline * KEEP_RATIO:",
     "    if dropped <= MIN_DROPPED_WORDS or new_words >= baseline * KEEP_RATIO:"),
    ("the dropped count is reversed", "    dropped = baseline - new_words", "    dropped = new_words - baseline"),
    ("the percentage is of the new size",
     "    pct = round(100 * dropped / baseline)",
     "    pct = round(100 * dropped / new_words)"),
    ("the words are counted by lines",
     "    return len(text.split())",
     "    return len(text.splitlines())"),
    # ---- scoping --------------------------------------------------------------------------
    ("malformed JSON raises", "    except (json.JSONDecodeError, ValueError):\n        return 0\n    if not isinstance(payload, dict):",
     "    except KeyError:\n        return 0\n    if not isinstance(payload, dict):"),
    ("a non-object payload is read as one", "    if not isinstance(payload, dict):", "    if False:"),
    ("an Edit warns too", '    if payload.get("tool_name") != "Write":', "    if False:"),
    ("only an exact tool name is accepted",
     '    if payload.get("tool_name") != "Write":',
     '    if payload.get("tool_name") not in ("Write", "Edit", "MultiEdit"):'),
    ("a non-dict tool_input is read as a dict",
     '    raw_path = tool_input.get("file_path", "") if isinstance(tool_input, dict) else ""',
     '    raw_path = tool_input.get("file_path", "")'),
    ("a non-string path is used", "    if not isinstance(raw_path, str) or not raw_path:", "    if not raw_path:"),
    ("an empty path is used", "    if not isinstance(raw_path, str) or not raw_path:", "    if not isinstance(raw_path, str):"),
    ("a relative path resolves against the process cwd, not the project",
     "        file_path = (project_root / file_path) if not file_path.is_absolute() else file_path",
     "        file_path = file_path"),
    ("the project dir is ignored",
     '        project_root = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())).resolve()',
     "        project_root = Path(os.getcwd()).resolve()"),
    ("a path outside the project is dropped without trying its own repo",
     "        found = _repo_root_for(file_path)\n        if found is None:\n            return 0  # genuinely outside any repo; not ours to judge",
     "        found = None\n        if found is None:\n            return 0  # genuinely outside any repo; not ours to judge"),
    ("the repo root found for an outside path is not used",
     "        repo_root = found",
     "        repo_root = project_root"),
    # ---- the baseline ---------------------------------------------------------------------
    ("the baseline is read from the repo top level, not the repo dir",
     '["git", "-C", str(repo), "show", f"HEAD:./{rel_path}"],',
     '["git", "-C", str(repo), "show", f"HEAD:{rel_path}"],'),
    ("the baseline is read from the index",
     '["git", "-C", str(repo), "show", f"HEAD:./{rel_path}"],',
     '["git", "-C", str(repo), "show", f":./{rel_path}"],'),
    ("a baseline that cannot be decoded is counted",
     "    except UnicodeDecodeError:\n        return None  # binary blob: no word count to compare",
     "    except KeyError:\n        return None  # binary blob: no word count to compare"),
    ("a git that is missing or wedged raises",
     "    except (OSError, subprocess.SubprocessError):\n        # git absent, or wedged past the timeout.",
     "    except KeyError:\n        # git absent, or wedged past the timeout."),
    ("a git that fails is read as a baseline",
     "    if result.returncode != 0:\n        # No HEAD at all",
     "    if False:\n        # No HEAD at all"),
    ("a repo with no commits is diagnosed",
     "        if not _head_exists(repo):",
     "        if False:"),
    ("a path git cannot resolve is never announced",
     '        if "does not exist in" not in err and "exists on disk" not in err:',
     "        if False:"),
    ("an untracked file is announced as a defect",
     '        if "does not exist in" not in err and "exists on disk" not in err:',
     '        if "does not exist in" not in err:'),
    ("a file that exists on disk but not in HEAD is announced as a defect",
     '        if "does not exist in" not in err and "exists on disk" not in err:',
     '        if "exists on disk" not in err:'),
    ("the announcement is dropped from stderr",
     "                file=sys.stderr,\n            )\n        return None",
     "                file=sys.stdout,\n            )\n        return None"),
    ("the announcement is empty of git's reason",
     "({err.strip()[:160]})",
     "()"),
    ("the new file is read as bytes of another encoding",
     '        new_words = _word_count(file_path.read_text(encoding="utf-8"))',
     '        new_words = _word_count(file_path.read_text(encoding="utf-16"))'),
    ("a file that vanished raises",
     "    except (OSError, UnicodeDecodeError):\n        # File vanished",
     "    except KeyError:\n        # File vanished"),
    # ---- _head_exists / _repo_root_for -------------------------------------------------------
    ("a repo with no HEAD counts as having one",
     "        ).returncode == 0",
     "        ).returncode != 1000"),
    ("a failing git counts as having a HEAD",
     "    except (OSError, subprocess.SubprocessError):\n        return False",
     "    except (OSError, subprocess.SubprocessError):\n        return True"),
    ("the repo root is not asked for the file's own folder",
     '["git", "-C", str(file_path.parent), "rev-parse", "--show-toplevel"],',
     '["git", "rev-parse", "--show-toplevel"],'),
    ("a failing rev-parse yields a root",
     "    if result.returncode != 0:\n        return None\n    root = ",
     "    if False:\n        return None\n    root = "),
    ("an empty root is used",
     "    if not root:\n        return None",
     "    if False:\n        return None"),
    ("a file outside the repo root is judged",
     "        try:\n            rel = file_path.relative_to(found).as_posix()\n        except ValueError:\n            return 0",
     "        try:\n            rel = file_path.relative_to(found).as_posix()\n        except KeyError:\n            return 0"),
    ("the timeout is dropped",
     "_GIT_TIMEOUT_SECONDS = 3",
     "_GIT_TIMEOUT_SECONDS = None"),
    # ---- the message ---------------------------------------------------------------------------
    ("the warning goes to stderr instead of the hook output",
     "    print(json.dumps({",
     "    print(json.dumps({}), file=sys.stderr)\n    print(json.dumps({"),
    ("the warning names the wrong event",
     '            "hookEventName": "PostToolUse",',
     '            "hookEventName": "PreToolUse",'),
]

# Multi-line anchors take the file's own line ending, so the batch runs on LF and CRLF checkouts.
_NL = "\r\n" if b"\r\n" in HOOK.read_bytes() else "\n"
MUTANTS = [(name, HOOK, old.replace("\n", _NL), new.replace("\n", _NL), TARGETS) for name, old, new in _SPEC]
