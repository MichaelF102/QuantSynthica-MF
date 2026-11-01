"""Architectural rule: quant_engine must not import web, database or app code."""
import ast
from pathlib import Path

FORBIDDEN = {"fastapi", "starlette", "sqlalchemy", "alembic", "psycopg", "redis", "streamlit", "app", "uvicorn"}
ROOT = Path(__file__).resolve().parents[1] / "quant_engine"


def test_no_forbidden_imports():
    bad = []
    for f in ROOT.rglob("*.py"):
        for node in ast.walk(ast.parse(f.read_text())):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            bad += [(str(f), n) for n in names if n.split(".")[0] in FORBIDDEN]
    assert not bad, bad
