import os
from pathlib import Path


def _is_under_unit_tests(path: Path) -> bool:
    parts = [p.lower() for p in path.parts]
    try:
        tests_index = parts.index("tests")
    except ValueError:
        return False
    return len(parts) > tests_index + 1 and parts[tests_index + 1] == "unit"


def pytest_ignore_collect(collection_path, config):
    """Skip integration tests when DATABASE_URL isn't configured.

    Most existing tests import `app.main`, which imports the DB engine at import-time.
    If `DATABASE_URL` is not set, collection fails before we can mark tests as skipped.

    Strategy:
    - Always collect `tests/unit/**`.
    - If `DATABASE_URL` is missing, ignore other tests under any `*/tests/*` folder.
    """

    path = Path(str(collection_path))

    if _is_under_unit_tests(path):
        return False

    if os.getenv("DATABASE_URL"):
        return False

    parts = [p.lower() for p in path.parts]
    if "tests" in parts:
        return True

    return False
