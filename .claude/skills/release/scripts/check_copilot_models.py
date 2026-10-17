#!/usr/bin/env python3
"""Refuse a release when a Copilot model ID the helper agents rely on is not in GitHub's table.

WHY THIS EXISTS. `plugin-tests/scripts/sync_copilot_agents.py` writes a Copilot model ID into
each Copilot copy of a helper agent (its `MODEL_MAP`). GitHub's docs say an ID Copilot cannot
honour falls back to the session's model without failing, so a renamed model costs the agent
its model choice and nothing reports it. Nothing else reads the IDs against GitHub's list, so
this does, once per release, against the table on GitHub's page.

The page is the rendered Copilot CLI command reference, section "Supported models":

    https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference

EXIT CONTRACT, three-valued on purpose:

    0  every MODEL_MAP ID is listed in the table
    1  one or more IDs are missing: each is named with its alias, in one run
    2  could not do the job: the page could not be fetched, it has no supported-models
       section or no rows in it, or MODEL_MAP is empty

Exit 2 is load-bearing for the same reason as in `check_shipped_tree.py`: a page whose layout
changed would otherwise read as "no ID is missing" over a table that was never read. A release
that gets 2 stops and reports it; it does not go on without the check.

The tests build a page with the same layout and pass a fake fetch, so they make no network call.
Stdlib only.
"""

from __future__ import annotations

import http.client
import re
import sys
import urllib.request
from pathlib import Path

TABLE_URL = "https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference"

EXIT_OK = 0
EXIT_MISSING = 1
EXIT_CANNOT_RUN = 2

_SECTION_ID = 'id="supported-models"'
# The first cell of a row holds the model ID in a code span: <tr><td><code>ID</code></td>.
_ROW_ID = re.compile(r"<tr>\s*<td[^>]*>\s*<code>([^<]+)</code>")


def supported_ids(page: str) -> list[str]:
    """The model IDs in the page's "Supported models" table. Raises ValueError when the page
    has no such section or the section has no rows, so a changed layout is never read as empty."""
    start = page.find(_SECTION_ID)
    if start < 0:
        raise ValueError("the page has no 'supported-models' section")
    end = page.find("<h2", start)
    ids = _ROW_ID.findall(page[start:] if end < 0 else page[start:end])
    if not ids:
        raise ValueError("the 'supported-models' section lists no model rows")
    return ids


def missing_ids(model_map: dict[str, str], listed: list[str]) -> dict[str, str]:
    """The `alias -> ID` pairs of `model_map` whose ID is not in `listed`."""
    return {alias: model_id for alias, model_id in model_map.items() if model_id not in listed}


def fetch_page(url: str = TABLE_URL, timeout: int = 30) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "cla-release-check"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https URL
        return response.read().decode("utf-8")


def _model_map() -> dict[str, str]:
    scripts = Path(__file__).resolve().parents[4] / "plugin-tests" / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import sync_copilot_agents

    return dict(sync_copilot_agents.MODEL_MAP)


def main(fetch=fetch_page, model_map: dict[str, str] | None = None) -> int:
    try:
        ids = _model_map() if model_map is None else model_map
    except Exception as err:  # the import runs another script, so any failure there must exit 2, not trace back
        print(f"cannot check: MODEL_MAP could not be read from sync_copilot_agents.py: {err}", file=sys.stderr)
        return EXIT_CANNOT_RUN
    if not ids:
        print("cannot check: MODEL_MAP is empty", file=sys.stderr)
        return EXIT_CANNOT_RUN
    try:
        listed = supported_ids(fetch())
    # URLError and timeouts are OSError, a cut-off body is HTTPException, bad bytes are ValueError.
    except (OSError, http.client.HTTPException, ValueError) as err:
        print(f"cannot read GitHub's supported-models table at {TABLE_URL}: {err}", file=sys.stderr)
        return EXIT_CANNOT_RUN
    absent = missing_ids(ids, listed)
    if absent:
        for alias, model_id in absent.items():
            print(f"MISSING {model_id} (the Copilot ID for '{alias}') is not in GitHub's supported models", file=sys.stderr)
        print(f"listed: {', '.join(listed)}", file=sys.stderr)
        return EXIT_MISSING
    print(f"ok: all {len(ids)} Copilot model IDs are listed ({len(listed)} models in the table)")
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
