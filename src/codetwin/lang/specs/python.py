"""Python: analysed and run by the built-in Python adapter (lang/python.py: ast, pytest and coverage.py), so the
grammar, import and runner fields of a tree-sitter spec are not used. Detection and test globs live here like
every other language's."""
from ..spec import Spec

SPEC = Spec(
    name="python",
    grammars={".py": "python"},
    test_globs=["test_*.py", "*_test.py", "**/tests/**/*.py", "**/test/**/*.py"],
    markers=["pyproject.toml", "setup.py", "setup.cfg"],
    adapter="python",
    default=True,
)
