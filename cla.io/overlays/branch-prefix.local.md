---
branch_prefix: feature/
---

<!--
  OVERLAY — per-repo, never synced (`*.local.md`). It lives in `cla.io/overlays/`
  rather than beside the skill because a marketplace-installed plugin tree is a
  read-only cache, and a per-repo fact stored there would be unreachable.

  The branch prefix `spec-to-pr` uses when it CREATES a feature branch and when
  `probe_state.py` LOOKS ONE UP. Both must agree, or a resume probe reports
  "nothing done yet" for work that is already finished — `rev-parse --verify
  --quiet` exits 1 with empty stderr on a miss, so the mismatch is silent.

  FORMAT: flat `key: value` between `---` fences, the same shape every other
  overlay in the plugin uses. The value is taken VERBATIM — no trailing `/` is
  appended, so a flat prefix like `wip-` works as written.

  `CLA_BRANCH_PREFIX` overrides this file. With neither set the default is
  `feature/`, which is what this repo uses — stated explicitly above rather than
  left commented out, because a file that EXISTS but yields no value is a
  misconfiguration the reader warns about, and a warning on every run in the
  source repo is one nobody reads.
-->
