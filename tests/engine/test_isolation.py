import ast
import subprocess
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[2] / "app" / "engine"
FORBIDDEN = (
    "aiogram",
    "sqlalchemy",
    "redis",
    "asyncpg",
    "alembic",
    "aiohttp",
    "pydantic",
    "app.bot",
    "app.database",
    "app.config",
    "app.main",
    "app.services",
    "app.repositories",
    "app.utils",
    "app.scheduler",
)


def test_engine_sources_have_no_infrastructure_imports() -> None:
    for path in ENGINE.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert not name.startswith(FORBIDDEN), f"{path.name} imports {name}"


def test_engine_imports_without_loading_infrastructure() -> None:
    code = (
        "import sys, app.engine;"
        f"bad=[m for m in sys.modules if m.split('.')[0] in {FORBIDDEN[:7]!r}];"
        "assert not bad, bad"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
