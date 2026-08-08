<!--
  OVERLAY — per-repo, never synced (`*.local.md`, excluded by `discover.py`).

  The branch prefix `spec-to-pr` uses when it CREATES a feature branch and when
  `probe_state.py` LOOKS ONE UP. Both must agree, or a resume probe reports
  "nothing done yet" for work that is already finished — `rev-parse --verify
  --quiet` exits 1 with empty stderr on a miss, so the mismatch is silent.

  First non-comment, non-blank line wins. A trailing `/` is added if absent.
  `CLA_BRANCH_PREFIX` overrides this file. Default when neither is set: feature/

  This repo uses the default, so the line below is commented out. A repo on
  another convention (e.g. `claude/fix/`) uncomments and edits it.
-->

<!-- feature/ -->
