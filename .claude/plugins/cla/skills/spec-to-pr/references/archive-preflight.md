# spec-to-pr — before archiving

1. Run `openspec validate <change-name> --strict` and fix what it reports in this PR. It fails a
   MODIFIED block that drops a live scenario and a malformed delta. A MODIFIED heading the live spec
   does not have only prints an `Archive would refuse this delta` line and exits 0: treat that line as
   a failure too.
2. If the change retired a script or file, grep `openspec/specs/<capability>/spec.md` for the retired
   path and fix stale references now, so they ship with the archive commit.
3. After any hand edit under `openspec/specs/`, run `openspec validate --specs`. A stray second
   `## Requirements` heading hides every requirement below it while the file still reads fine.
