"""Mutation batch for test_meter.py.

Each mutant breaks one behaviour the meter tests pin: per-file message keys, the
model a later copy inherits, the unreadable-file exit, the table's per-model rows
and their order, and the JSON totals.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_meter.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
METER = DEV / "scripts" / "meter.py"
GUARD = DEV / "tests" / "consistency" / "test_meter.py"

TARGETS = [GUARD]

MUTANTS = [
    (
        "message ids are merged across files",
        METER,
        "key = (str(file), message_id)",
        'key = ("", message_id)',
        TARGETS,
    ),
    (
        "the table lists models in reverse order",
        METER,
        "rows = sorted(totals.items())",
        "rows = sorted(totals.items(), reverse=True)",
        TARGETS,
    ),
    (
        "a model row prints the grand total instead of its own",
        METER,
        'table += [[model, *(f"{row[name]:,}" for name in names)] for model, row in rows]',
        'table += [[model, *(f"{grand[name]:,}" for name in names)] for model, row in rows]',
        TARGETS,
    ),
    (
        "the JSON drops the message count",
        METER,
        'row["messages"] += 1',
        'row["messages"] += 0',
        TARGETS,
    ),
    (
        "a copy without a model is filed under <unknown> again",
        METER,
        'model = messages[key][0] if key in messages else "<unknown>"',
        'model = "<unknown>"',
        TARGETS,
    ),
    (
        "a copy without a model takes no model even with no earlier copy",
        METER,
        'model = messages[key][0] if key in messages else "<unknown>"',
        'model = messages[key][0] if key in messages else "opus"',
        TARGETS,
    ),
    (
        "an unreadable transcript raises instead of exiting 1",
        METER,
        "    except OSError as exc:\n        print(f\"meter: cannot read",
        "    except ZeroDivisionError as exc:\n        print(f\"meter: cannot read",
        TARGETS,
    ),
]
