import ast
from pathlib import Path

SERVER = Path(__file__).parents[1] / "homefinder" / "server"
FORBIDDEN = ("homefinder.learner", "sklearn", "PIL", "imagehash", "playwright")


def test_server_does_not_import_worker_only_libs():
    for py in SERVER.rglob("*.py"):
        tree = ast.parse(py.read_text("utf-8"))
        for node in ast.walk(tree):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            for n in names:
                assert not n.startswith(FORBIDDEN), f"{py} imports {n}"
