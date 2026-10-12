"""Mutation batch for test_agent_definitions.py.

Each mutant breaks one thing the agent-definition guard claims to catch: a forbidden tool
left out of the list, a model check loosened, a required key no longer required, or a shipped
reviewer changed to something the guard must refuse.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/conformance/test_agent_definitions.py
"""

from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
DEV = Path(__file__).resolve().parents[2]
AGENTS = PLUGIN / "agents"
GUARD = DEV / "tests" / "conformance" / "test_agent_definitions.py"
CODE_REVIEWER = AGENTS / "code-reviewer.md"
HUNTER = AGENTS / "silent-failure-hunter.md"
DOC_SWEEPER = AGENTS / "doc-sweeper.md"

TARGETS = [GUARD]
TOOLS = '_FORBIDDEN_TOOLS = ("Edit", "Write", "NotebookEdit", "Bash")'

MUTANTS = [
    ("the guard stops forbidding Edit", GUARD, TOOLS,
     '_FORBIDDEN_TOOLS = ("Write", "NotebookEdit", "Bash")', TARGETS),
    ("the guard stops forbidding Write", GUARD, TOOLS,
     '_FORBIDDEN_TOOLS = ("Edit", "NotebookEdit", "Bash")', TARGETS),
    ("the guard stops forbidding NotebookEdit", GUARD, TOOLS,
     '_FORBIDDEN_TOOLS = ("Edit", "Write", "Bash")', TARGETS),
    ("the guard stops forbidding Bash", GUARD, TOOLS,
     '_FORBIDDEN_TOOLS = ("Edit", "Write", "NotebookEdit")', TARGETS),
    ("the guard accepts any model name", GUARD,
     'if fields.get("model") not in _MODELS:', 'if False:', TARGETS),
    ("the guard accepts an unknown model name", GUARD,
     '_MODELS = ("haiku", "sonnet", "opus")', '_MODELS = ("haiku", "sonnet", "opus", "gpt")', TARGETS),
    ("the guard no longer requires a name", GUARD,
     'for key in ("name", "description")', 'for key in ("description",)', TARGETS),
    ("the guard no longer requires a description", GUARD,
     'for key in ("name", "description")', 'for key in ("name",)', TARGETS),
    ("the guard accepts an empty tools list", GUARD,
     'if not isinstance(tools, list) or not tools:', 'if not isinstance(tools, list):', TARGETS),
    ("the guard accepts a tools value that is not a list", GUARD,
     'if not isinstance(tools, list) or not tools:', 'if not tools:', TARGETS),
    ("the guard accepts a file with no frontmatter", GUARD,
     'if not lines or lines[0].strip() != "---":', 'if not lines:', TARGETS),
    ("the code reviewer gains Bash", CODE_REVIEWER,
     'tools: ["Read", "Grep", "Glob"]', 'tools: ["Read", "Grep", "Glob", "Bash"]', TARGETS),
    ("the silent-failure hunter gains Edit", HUNTER,
     'tools: ["Read", "Grep", "Glob"]', 'tools: ["Read", "Grep", "Glob", "Edit"]', TARGETS),
    ("the silent-failure hunter loses its model", HUNTER, "model: opus\n", "", TARGETS),
    ("an existing helper agent names an unknown model", DOC_SWEEPER,
     "model: haiku", "model: gpt", TARGETS),
    ("the code reviewer is renamed", CODE_REVIEWER,
     "name: code-reviewer", "name: reviewer", TARGETS),
]
