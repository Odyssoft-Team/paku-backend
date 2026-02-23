import os
from pathlib import Path


def _is_unit_test(path: Path) -> bool:
    parts = [p.lower() for p in path.parts]
    try:
        tests_index = parts.index("tests")
    except ValueError:
        return False

    # Only `tests/unit/**` are always runnable without env/DB.
    return len(parts) > tests_index + 1 and parts[tests_index + 1] == "unit"


def pytest_ignore_collect(collection_path, config):
    """Allow running pytest locally without a database.

    The app imports the DB engine at import-time (`app.core.db`) and raises if
    `DATABASE_URL` is missing. Many integration tests import `app.main`, which
    would crash during collection.

    Policy:
    - Always collect `tests/unit/**`.
    - If `DATABASE_URL` is not set, ignore any other path that lives under a
      `tests` directory (including `app/**/tests/**`).
    """

    path = Path(str(collection_path))

    if _is_unit_test(path):
        return False

    if os.getenv("DATABASE_URL"):
        return False

    parts = [p.lower() for p in path.parts]
    return "tests" in parts
