"""Mutation batch for test_review_sizing_names_reviewers.py.

Each mutant breaks one link the guard checks: a routing row losing its agent file, a row naming
a file that does not exist, the section scope widened, or one of the guard's own comparisons
switched off.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_review_sizing_names_reviewers.py
"""

from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
DEV = Path(__file__).resolve().parents[2]
ROUTING = PLUGIN / "skills" / "_shared" / "references" / "model-routing.md"
GUARD = DEV / "tests" / "consistency" / "test_review_sizing_names_reviewers.py"

TARGETS = [GUARD]

MUTANTS = [
    ("the routing row for code-reviewer loses its file", ROUTING,
     "`${CLAUDE_PLUGIN_ROOT}/agents/code-reviewer.md`, ", "", TARGETS),
    ("the routing row for silent-failure-hunter loses its file", ROUTING,
     ", `${CLAUDE_PLUGIN_ROOT}/agents/silent-failure-hunter.md` |", " |", TARGETS),
    ("the routing row for comment-analyzer loses its file", ROUTING,
     "; `${CLAUDE_PLUGIN_ROOT}/agents/comment-analyzer.md` |", " |", TARGETS),
    ("a routing row names an agent file that does not exist", ROUTING,
     "agents/comment-analyzer.md`", "agents/comment-analyser.md`", TARGETS),
    ("the sizing table drops silent-failure-hunter", ROUTING,
     "| High risk | `code-reviewer` + `silent-failure-hunter` | Opus |",
     "| High risk | `code-reviewer` | Opus |", TARGETS),
    ("the guard reads the whole file instead of the Routing table", GUARD,
     'section = text.split("\\n## Routing table", 1)[1].split("\\n## ", 1)[0]',
     'section = text', TARGETS),
    ("the guard stops checking each reviewer has a row", GUARD,
     'if f"{r}.md" not in named]', 'if False]', TARGETS),
    ("the guard stops checking the named file exists", GUARD,
     'if not (agents / f).is_file()]', 'if False]', TARGETS),
    ("the guard forgets one shipped reviewer", GUARD,
     '_SHIPPED_REVIEWERS = ("code-reviewer", "silent-failure-hunter", "comment-analyzer")',
     '_SHIPPED_REVIEWERS = ("code-reviewer", "silent-failure-hunter")', TARGETS),
]
