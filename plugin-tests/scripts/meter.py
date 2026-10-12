"""Total the tokens a Claude Code session spent, split by model.

`measure_load.py` counts the words of plugin prose, which is not what a session
costs. This reads what the API billed: the `usage` block on every assistant
message in a session transcript, so a token-diet change can quote a measured
before and after per model. Run it on a copy of the transcript folder, never on
a live session.

Input is one `.jsonl` transcript or a folder. A folder is searched recursively,
so a session's `subagents/*.jsonl` files count with the main chat.

A transcript writes one record per content block, so one API message appears
several times with the same `message.id` and the same `usage`. Each message is
counted once. If the copies disagree, the last one wins, since streaming
finishes with the final output count.

Columns: input (uncached), cache-write, cache-read and output tokens, plus the
message count. Nothing is written except the table on stdout. Exit 1, with a
message on stderr, when the path is missing or no message carries `usage`.

    python3 plugin-tests/scripts/meter.py <transcript.jsonl | folder>
    python3 plugin-tests/scripts/meter.py <folder> --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

FIELDS = (
    ("input", "input_tokens"),
    ("cache_write", "cache_creation_input_tokens"),
    ("cache_read", "cache_read_input_tokens"),
    ("output", "output_tokens"),
)


def transcript_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(path.rglob("*.jsonl"))


def _tokens(usage: dict, key: str) -> int:
    value = usage.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def collect(files: list[Path]) -> dict[str, dict[str, int]]:
    """Return {model: {input, cache_write, cache_read, output, messages}}."""
    # (file, message id) -> (model, usage). The file is part of the key: a
    # subagent transcript is a separate conversation, so ids never repeat across
    # files and keying on the file keeps a copied folder from merging them.
    messages: dict[tuple[str, str], tuple[str, dict]] = {}
    anonymous = 0
    for file in files:
        with file.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                message = record.get("message") if isinstance(record, dict) else None
                if not isinstance(message, dict) or not isinstance(message.get("usage"), dict):
                    continue
                message_id = message.get("id")
                if not isinstance(message_id, str):
                    anonymous += 1
                    message_id = f"<no-id-{anonymous}>"
                model = message.get("model")
                messages[(str(file), message_id)] = (
                    model if isinstance(model, str) else "<unknown>",
                    message["usage"],
                )
    totals: dict[str, dict[str, int]] = {}
    for model, usage in messages.values():
        row = totals.setdefault(model, {name: 0 for name, _ in FIELDS} | {"messages": 0})
        for name, key in FIELDS:
            row[name] += _tokens(usage, key)
        row["messages"] += 1
    return totals


def render(totals: dict[str, dict[str, int]]) -> str:
    names = [name for name, _ in FIELDS] + ["messages"]
    rows = sorted(totals.items())
    grand = {name: sum(row[name] for _, row in rows) for name in names}
    table = [["model", *names]]
    table += [[model, *(f"{row[name]:,}" for name in names)] for model, row in rows]
    table.append(["TOTAL", *(f"{grand[name]:,}" for name in names)])
    widths = [max(len(line[i]) for line in table) for i in range(len(table[0]))]
    out = []
    for index, line in enumerate(table):
        out.append("  ".join(cell.ljust(widths[0]) if i == 0 else cell.rjust(widths[i]) for i, cell in enumerate(line)))
        if index == 0:
            out.append("  ".join("-" * width for width in widths))
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("path", type=Path, help="a .jsonl transcript or a folder of them")
    parser.add_argument("--json", action="store_true", help="print the totals as JSON")
    args = parser.parse_args(argv)

    if not args.path.exists():
        print(f"meter: {args.path} does not exist", file=sys.stderr)
        return 1
    files = transcript_files(args.path)
    totals = collect(files)
    if not totals:
        print(
            f"meter: no message with a `usage` field in {len(files)} transcript file(s) under {args.path}",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(totals, indent=2, sort_keys=True) if args.json else render(totals))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
