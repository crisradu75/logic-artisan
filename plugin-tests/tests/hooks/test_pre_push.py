"""The `pre-push` guard that replaced `block-direct-push-to-main.py`.

The hook it replaces guessed a push's destination by parsing the command
string, and lost to every spelling variant git accepts. These tests assert the
property that made the replacement worth the swap: the guard reads the REFSPEC
git resolved, so the command's spelling is irrelevant by construction — there
is no `git.exe` / `-C` / quoting case to test, because none of them can reach
this code path differently.

What IS worth testing is the ref parsing itself: which refs are refused, that
a normal feature push is untouched, that a multi-ref push is refused if ANY of
its refs targets the default branch, and that the documented override works.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_PRE_PUSH = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "hooks" / "git" / "pre-push"
_SH = shutil.which("sh")

# Every hook here is a POSIX sh script; git runs it under its bundled sh even
# on Windows. A machine without `sh` cannot run the real hook either, so
# skipping is honest rather than a hidden gap.
pytestmark = pytest.mark.skipif(_SH is None, reason="no POSIX sh on PATH")

_ZERO = "0" * 40
_SHA = "a" * 40
# The hook's own overrides. An exported one turns a refusal into a pass, so every
# run starts with both cleared and a test that wants one sets it itself.
_HATCHES = ("ALLOW_PUSH_TO_MAIN", "ALLOW_TAG_REWRITE")


def _run(stdin_text: str, env_extra: dict | None = None):
    import os

    env = {**os.environ, **(env_extra or {})}
    for hatch in _HATCHES:
        env.pop(hatch, None)
    if env_extra:
        env.update(env_extra)
    # Bytes in, not `text=True`: text mode writes every "\n" to the child as
    # "\r\n" on Windows, so the last field of each line (the remote sha) would
    # carry a stray "\r" that git never sends, and an all-zero sha would not read
    # as zero. Git writes bare "\n" to a hook's stdin on every platform.
    done = subprocess.run(
        [_SH, str(_PRE_PUSH)],
        input=stdin_text.encode("utf-8"),
        capture_output=True,
        env=env,
    )
    done.stdout = done.stdout.decode("utf-8", errors="replace")
    done.stderr = done.stderr.decode("utf-8", errors="replace")
    return done


def _line(remote_ref: str, local_sha: str = _SHA) -> str:
    return f"refs/heads/x {local_sha} {remote_ref} {_ZERO}\n"


# requirement: git-guards / Direct pushes to main are refused
@pytest.mark.parametrize("branch", ["main", "master"])
def test_refuses_a_push_to_the_default_branch(branch):
    r = _run(_line(f"refs/heads/{branch}"))
    assert r.returncode == 1
    assert branch in r.stderr
    assert "refusing to push" in r.stderr


def test_allows_a_feature_branch_push():
    r = _run(_line("refs/heads/feature/thing"))
    assert r.returncode == 0
    assert r.stderr.strip() == ""


def test_allows_a_branch_whose_name_merely_contains_main():
    # `refs/heads/maintenance` must not be caught by a substring match — the
    # case-arm is an exact ref comparison, and this pins it.
    r = _run(_line("refs/heads/maintenance"))
    assert r.returncode == 0


def test_refuses_a_deletion_of_the_default_branch():
    # A delete arrives with an all-zero LOCAL sha and the same remote ref.
    r = _run(_line("refs/heads/main", local_sha=_ZERO))
    assert r.returncode == 1


def test_refuses_a_multi_ref_push_when_any_ref_targets_main():
    r = _run(_line("refs/heads/feature/a") + _line("refs/heads/main"))
    assert r.returncode == 1


def test_allows_a_multi_ref_push_of_only_feature_branches():
    r = _run(_line("refs/heads/feature/a") + _line("refs/heads/feature/b"))
    assert r.returncode == 0


# requirement: git-guards / Direct pushes to main are refused
def test_the_documented_override_works():
    r = _run(_line("refs/heads/main"), {"ALLOW_PUSH_TO_MAIN": "1"})
    assert r.returncode == 0


def test_an_override_of_anything_but_1_does_not_disarm_the_guard():
    # A guard that treats any non-empty value as "on" disarms on a stray
    # `ALLOW_PUSH_TO_MAIN=0`, which reads as the opposite of what it does.
    r = _run(_line("refs/heads/main"), {"ALLOW_PUSH_TO_MAIN": "0"})
    assert r.returncode == 1


def test_empty_stdin_is_allowed():
    # `git push` with nothing to do hands the hook no lines at all.
    r = _run("")
    assert r.returncode == 0


def _git(cwd, *args):
    subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


# requirement: git-guards / A push to the remote's own default branch is refused
def test_refuses_a_push_to_the_remotes_own_default_branch(tmp_path):
    """A repo whose default branch is not main or master is guarded too: the hook reads the
    branch `refs/remotes/<remote>/HEAD` names, for the remote git passes as $1."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/develop")
    run = lambda ref, *args: subprocess.run(  # noqa: E731
        [_SH, str(_PRE_PUSH), *args], input=_line(ref), capture_output=True, text=True,
        encoding="utf-8", errors="replace", cwd=tmp_path,
    )
    refused = run("refs/heads/develop", "origin", "https://example.invalid/repo.git")
    assert refused.returncode == 1 and "develop" in refused.stderr
    assert run("refs/heads/feature/x", "origin", "u").returncode == 0
    assert run("refs/heads/main", "origin", "u").returncode == 1, "main stays refused"
    # A URL that matches no configured remote has no remote-tracking HEAD: only main and master are refused.
    other = "https://example.invalid/other.git"
    assert run("refs/heads/develop", other, other).returncode == 0
    assert run("refs/heads/main", other, other).returncode == 1


# requirement: git-guards / A push to the remote's own default branch is refused
def test_a_push_to_a_remotes_url_gets_that_remotes_default_branch_check(tmp_path):
    url = "https://example.invalid/repo.git"
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "remote", "add", "origin", url)
    _git(tmp_path, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/develop")
    run = lambda ref, u: subprocess.run(  # noqa: E731
        [_SH, str(_PRE_PUSH), u, u], input=_line(ref), capture_output=True, text=True,
        encoding="utf-8", errors="replace", cwd=tmp_path,
    )
    refused = run("refs/heads/develop", url)
    assert refused.returncode == 1 and "develop" in refused.stderr
    assert run("refs/heads/feature/x", url).returncode == 0
    assert run("refs/heads/main", url).returncode == 1, "main stays refused"
    # A URL that is not that remote's is not matched to it.
    assert run("refs/heads/develop", url + ".x").returncode == 0
    # A remote's push URL, and a second push URL, match it too.
    push = "https://example.invalid/push.git"
    push2 = "https://example.invalid/push2.git"
    _git(tmp_path, "remote", "set-url", "--push", "origin", push)
    _git(tmp_path, "remote", "set-url", "--add", "--push", "origin", push2)
    assert run("refs/heads/develop", push).returncode == 1
    assert run("refs/heads/develop", push2).returncode == 1


# ------------------------------------------------------------------ tags
#
# A consumer that fetched a tag has that tree, so the hook refuses to delete a
# tag on the remote or to point one the remote has at another object. The stdin
# tests pin the decision on each field; the bare-repo tests below run real
# pushes, so the lines are the ones git itself writes.

_OTHER = "b" * 40


def _tag_line(local_sha: str, remote_sha: str, tag: str = "v1.0.0") -> str:
    local_ref = "(delete)" if set(local_sha) == {"0"} else f"refs/tags/{tag}"
    return f"{local_ref} {local_sha} refs/tags/{tag} {remote_sha}\n"


# requirement: git-guards / A push that deletes or moves a tag on the remote is refused
@pytest.mark.parametrize("tag", ["v1.0.0", "cla--v2.4.0", "nightly"])
def test_refuses_a_tag_delete_of_any_name(tag):
    r = _run(_tag_line(_ZERO, _SHA, tag))
    assert r.returncode == 1
    assert f"refusing to delete tag '{tag}'" in r.stderr
    assert "ALLOW_TAG_REWRITE=1" in r.stderr, "the refusal names its override"


def test_refuses_a_tag_move():
    r = _run(_tag_line(_OTHER, _SHA))
    assert r.returncode == 1
    assert "refusing to move tag 'v1.0.0'" in r.stderr
    assert "ALLOW_TAG_REWRITE=1" in r.stderr
    # A non-forced `git push --tags` with one stale local tag is now refused whole,
    # so the message names the way out that is not an override.
    assert "git fetch --tags --force" in r.stderr


def test_allows_a_new_tag():
    r = _run(_tag_line(_SHA, _ZERO))
    assert r.returncode == 0
    assert r.stderr.strip() == ""


def test_allows_a_tag_the_remote_already_has_at_the_same_object():
    r = _run(_tag_line(_SHA, _SHA))
    assert r.returncode == 0


def test_a_sha256_zero_is_read_as_no_object():
    # A SHA-256 repo writes 64 zeros: a delete there is still a delete, and a new
    # tag there is still new.
    z64, a64 = "0" * 64, "a" * 64
    assert _run(_tag_line(z64, a64)).returncode == 1
    assert _run(_tag_line(a64, z64)).returncode == 0


def test_the_tag_override_lifts_only_the_tag_refusal():
    assert _run(_tag_line(_ZERO, _SHA), {"ALLOW_TAG_REWRITE": "1"}).returncode == 0
    assert _run(_tag_line(_OTHER, _SHA), {"ALLOW_TAG_REWRITE": "1"}).returncode == 0
    assert _run(_line("refs/heads/main"), {"ALLOW_TAG_REWRITE": "1"}).returncode == 1


def test_the_main_override_does_not_lift_the_tag_refusal():
    assert _run(_tag_line(_ZERO, _SHA), {"ALLOW_PUSH_TO_MAIN": "1"}).returncode == 1
    assert _run(_tag_line(_OTHER, _SHA), {"ALLOW_PUSH_TO_MAIN": "1"}).returncode == 1


def test_a_tag_override_of_anything_but_1_does_not_disarm_the_guard():
    assert _run(_tag_line(_ZERO, _SHA), {"ALLOW_TAG_REWRITE": "0"}).returncode == 1


def test_a_ref_outside_refs_tags_named_like_a_tag_is_not_a_tag():
    # Only `refs/tags/*` is a tag: deleting a branch named `tags/x` is a branch delete.
    assert _run(_line("refs/heads/tags/v1.0.0", local_sha=_ZERO)).returncode == 0


class _Clone:
    """A clone of a local bare `origin` with the shipped hook installed the way
    the install line says: copied into `.git/hooks/pre-push`."""

    def __init__(self, tmp_path: Path):
        import os

        self.origin = tmp_path / "origin.git"
        self.work = tmp_path / "work"
        empty = tmp_path / "empty.gitconfig"
        empty.write_text("", encoding="utf-8")
        self.env = {k: v for k, v in os.environ.items() if k not in _HATCHES}
        self.env.update({
            # A global `core.hooksPath` (Husky, lefthook) would point git away
            # from `.git/hooks` and every refusal below would pass by accident.
            "GIT_CONFIG_GLOBAL": str(empty), "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
        })
        self.git(tmp_path, "init", "-q", "--bare", "-b", "main", str(self.origin))
        self.work.mkdir()
        self.git(self.work, "init", "-q", "-b", "main")
        self.git(self.work, "remote", "add", "origin", str(self.origin))
        self.commit("one")
        self.git(self.work, "push", "-q", "origin", "main")
        hook = self.work / ".git" / "hooks" / "pre-push"
        shutil.copyfile(_PRE_PUSH, hook)
        hook.chmod(0o755)

    def git(self, cwd: Path, *args: str, env_extra: dict | None = None, check: bool = True):
        r = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
            errors="replace", env={**self.env, **(env_extra or {})},
        )
        if check:
            assert r.returncode == 0, f"git {args} failed: {r.stderr}"
        return r

    def commit(self, message: str) -> None:
        self.git(self.work, "commit", "-q", "--allow-empty", "-m", message)

    def push(self, *args: str, env_extra: dict | None = None):
        return self.git(self.work, "push", "origin", *args, env_extra=env_extra, check=False)

    def tag(self, name: str, annotated: bool, *extra: str) -> None:
        kind = ["-a", "-m", name] if annotated else []
        self.git(self.work, "tag", *kind, *extra, name)

    def remote_ref(self, ref: str) -> str | None:
        r = self.git(self.origin, "rev-parse", "--verify", "-q", ref, check=False)
        return r.stdout.strip() or None


@pytest.fixture
def clone(tmp_path):
    return _Clone(tmp_path)


def test_the_bare_repo_clone_runs_the_hook(clone):
    # Non-vacuity partner for every refusal below: the copied hook is the one git
    # runs. A push to main from the clone is refused by it.
    clone.commit("two")
    r = clone.push("main")
    assert r.returncode != 0 and "cla: refusing to push directly to 'main'" in r.stderr


# requirement: git-guards / A push that deletes or moves a tag on the remote is refused
@pytest.mark.parametrize("annotated", [False, True], ids=["lightweight", "annotated"])
@pytest.mark.parametrize("spelling", [("--delete", "v1.0.0"), (":refs/tags/v1.0.0",)],
                         ids=["--delete", "empty-source refspec"])
def test_a_real_tag_delete_is_refused(clone, annotated, spelling):
    clone.tag("v1.0.0", annotated)
    assert clone.push("v1.0.0").returncode == 0, "creating the tag is allowed"
    before = clone.remote_ref("refs/tags/v1.0.0")
    assert before
    r = clone.push(*spelling)
    assert r.returncode != 0
    assert "refusing to delete tag 'v1.0.0'" in r.stderr
    assert clone.remote_ref("refs/tags/v1.0.0") == before, "the remote still has the tag"


# requirement: git-guards / A push that deletes or moves a tag on the remote is refused
@pytest.mark.parametrize("annotated", [False, True], ids=["lightweight", "annotated"])
def test_a_real_tag_move_is_refused(clone, annotated):
    clone.tag("v1.0.0", annotated)
    assert clone.push("v1.0.0").returncode == 0
    before = clone.remote_ref("refs/tags/v1.0.0")
    clone.commit("two")
    clone.tag("v1.0.0", annotated, "-f")
    r = clone.push("--force", "v1.0.0")
    assert r.returncode != 0
    assert "refusing to move tag 'v1.0.0'" in r.stderr
    assert clone.remote_ref("refs/tags/v1.0.0") == before, "the remote tag did not move"


def test_re_creating_an_annotated_tag_on_the_same_commit_is_a_move(clone):
    # The tag OBJECT changes even though the commit does not; a consumer that
    # verified the old object sees a different one.
    clone.tag("v1.0.0", True)
    assert clone.push("v1.0.0").returncode == 0
    clone.git(clone.work, "tag", "-f", "-a", "-m", "again", "v1.0.0")
    r = clone.push("--force", "v1.0.0")
    assert r.returncode != 0 and "refusing to move tag" in r.stderr


def test_a_real_lightweight_to_annotated_swap_is_a_move(clone):
    clone.tag("v1.0.0", False)
    assert clone.push("v1.0.0").returncode == 0
    clone.tag("v1.0.0", True, "-f")
    assert clone.push("--force", "v1.0.0").returncode != 0


# requirement: git-guards / A push that deletes or moves a tag on the remote is refused
@pytest.mark.parametrize("annotated", [False, True], ids=["lightweight", "annotated"])
def test_a_real_new_tag_goes_through(clone, annotated):
    clone.tag("v1.0.0", annotated)
    r = clone.push("v1.0.0")
    assert r.returncode == 0, r.stderr
    assert clone.remote_ref("refs/tags/v1.0.0")
    # A second release beside it, pushed with --tags: the unchanged first tag
    # rides along and is not a move.
    clone.commit("two")
    clone.tag("v1.1.0", annotated)
    r = clone.push("--tags")
    assert r.returncode == 0, r.stderr
    assert clone.remote_ref("refs/tags/v1.1.0")


# requirement: git-guards / A push that deletes or moves a tag on the remote is refused
def test_the_real_override_lets_a_delete_and_a_move_through(clone):
    clone.tag("v1.0.0", True)
    clone.tag("v2.0.0", False)
    assert clone.push("v1.0.0", "v2.0.0").returncode == 0
    r = clone.push("--delete", "v1.0.0", env_extra={"ALLOW_TAG_REWRITE": "1"})
    assert r.returncode == 0, r.stderr
    assert clone.remote_ref("refs/tags/v1.0.0") is None
    clone.commit("two")
    clone.tag("v2.0.0", False, "-f")
    r = clone.push("--force", "v2.0.0", env_extra={"ALLOW_TAG_REWRITE": "1"})
    assert r.returncode == 0, r.stderr
    assert clone.remote_ref("refs/tags/v2.0.0") == clone.git(clone.work, "rev-parse", "HEAD").stdout.strip()


def test_a_real_branch_delete_is_unchanged(clone):
    clone.git(clone.work, "branch", "feature/a")
    assert clone.push("feature/a").returncode == 0
    r = clone.push("--delete", "feature/a")
    assert r.returncode == 0, r.stderr
    assert clone.remote_ref("refs/heads/feature/a") is None
    r = clone.push("--delete", "main")
    assert r.returncode != 0 and "refusing to push directly to 'main'" in r.stderr


def test_a_real_multi_ref_push_with_one_tag_delete_is_refused_whole(clone):
    clone.tag("v1.0.0", True)
    assert clone.push("v1.0.0").returncode == 0
    clone.git(clone.work, "branch", "feature/a")
    clone.tag("v1.1.0", True)
    r = clone.push("feature/a", "v1.1.0", ":refs/tags/v1.0.0")
    assert r.returncode != 0
    assert "refusing to delete tag 'v1.0.0'" in r.stderr
    # git aborts the whole push when the hook refuses: nothing else landed either.
    assert clone.remote_ref("refs/tags/v1.0.0")
    assert clone.remote_ref("refs/heads/feature/a") is None
    assert clone.remote_ref("refs/tags/v1.1.0") is None


def test_a_real_prune_push_that_would_delete_a_tag_is_refused(clone):
    # `--prune` writes a delete line for every remote tag the clone lacks, so the
    # hook sees it and refuses, unlike the mirror push below.
    clone.tag("v1.0.0", True)
    assert clone.push("v1.0.0").returncode == 0
    clone.git(clone.work, "tag", "-d", "v1.0.0")
    r = clone.push("--prune", "refs/tags/*:refs/tags/*")
    assert r.returncode != 0 and "refusing to delete tag 'v1.0.0'" in r.stderr
    assert clone.remote_ref("refs/tags/v1.0.0")


# requirement: git-guards / A push that deletes or moves a tag on the remote is refused
def test_a_mirror_push_deletes_a_remote_tag_without_consulting_the_hook(clone):
    """KNOWN LIMIT, pinned so it stays known: `git push --mirror` deletes every
    remote ref the clone lacks without writing a line for it on the hook's stdin,
    so the hook cannot refuse it. The hook still runs (it sees the refs the mirror
    updates); it is simply never told about the deletion. If git ever starts
    reporting these lines, this test fails and the requirement's exception can go."""
    clone.tag("v1.0.0", True)
    assert clone.push("v1.0.0").returncode == 0
    clone.git(clone.work, "tag", "-d", "v1.0.0")
    clone.git(clone.work, "branch", "feature/a")  # something the mirror creates, so the hook runs
    hook = clone.work / ".git" / "hooks" / "pre-push"
    log = clone.work.parent / "hook-stdin.log"
    real = clone.work.parent / "real-pre-push"
    shutil.copyfile(hook, real)
    hook.write_text(
        "#!/bin/sh\n"
        f"in=$(cat); printf '%s\\n' \"$in\" >> '{log.as_posix()}'\n"
        f"printf '%s\\n' \"$in\" | sh '{real.as_posix()}' \"$@\"\n",
        encoding="utf-8", newline="\n",
    )
    hook.chmod(0o755)
    r = clone.push("--mirror")
    assert r.returncode == 0, r.stderr
    seen = log.read_text(encoding="utf-8")
    assert "refs/heads/feature/a" in seen, "the hook ran for the ref the mirror created"
    assert "refs/tags/" not in seen, "git reported the tag deletion to the hook"
    assert clone.remote_ref("refs/tags/v1.0.0") is None, "the mirror push deleted the tag"



# requirement: git-guards / Direct pushes to main are refused
def test_a_mirror_push_deletes_a_protected_branch_without_consulting_the_hook(clone):
    """The same KNOWN LIMIT for a protected branch: a clone with no local `master`
    mirror-pushes, and git deletes the remote's `master` without telling the hook.
    An explicit `--delete master` from the same clone is still refused. (`master`,
    not `main`, because the remote itself refuses to delete its current branch,
    as GitHub refuses to delete the default branch.)"""
    clone.git(clone.work, "branch", "master")
    assert clone.push("master", env_extra={"ALLOW_PUSH_TO_MAIN": "1"}).returncode == 0
    clone.git(clone.work, "branch", "-D", "master")
    r = clone.push("--delete", "master")
    assert r.returncode != 0 and "refusing to push directly to 'master'" in r.stderr
    r = clone.push("--mirror")
    assert r.returncode == 0, r.stderr
    assert clone.remote_ref("refs/heads/master") is None, "the mirror push deleted master"
