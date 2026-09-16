"""
TASK-002 — Container database smoke test.

Proves:
  1. Docker Compose can start the isolated DB service (compose.yml db service).
  2. PostgreSQL becomes genuinely ready (health check passes before test runs).
  3. A real database connection succeeds (psql -c "SELECT 1").
  4. A real SQL query returns the expected result.
  5. TimescaleDB is installed/available in the running database.

Uses `psql` inside the running container via `docker compose exec` so no
Python database library is required.

Credentials are test-only development values defined in compose.yml.
No canonical/historical data is touched.
"""

import subprocess


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COMPOSE_SERVICE = "db"
_PSQL_USER = "tip"
_PSQL_DB = "tip_test"


def _psql(query: str) -> subprocess.CompletedProcess:
    """Run a SQL query through psql inside the Compose db service."""
    return subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "--no-TTY",
            _COMPOSE_SERVICE,
            "psql",
            "--username",
            _PSQL_USER,
            "--dbname",
            _PSQL_DB,
            "--tuples-only",
            "--no-align",
            "--command",
            query,
        ],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_postgresql_accepts_connection_and_query() -> None:
    """PostgreSQL is reachable and responds to a real query."""
    result = _psql("SELECT 1;")
    assert result.returncode == 0, (
        f"psql exited {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert result.stdout.strip() == "1", (
        f"Expected '1', got: {result.stdout!r}"
    )


def test_timescaledb_extension_is_available() -> None:
    """TimescaleDB extension is present in the PostgreSQL instance."""
    result = _psql(
        "SELECT default_version "
        "FROM pg_available_extensions "
        "WHERE name = 'timescaledb';"
    )
    assert result.returncode == 0, (
        f"psql exited {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    version = result.stdout.strip()
    assert version, (
        "timescaledb extension not found in pg_available_extensions. "
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    # Version string must be a non-empty dotted version, e.g. "2.17.2"
    assert "." in version, (
        f"Unexpected timescaledb version format: {version!r}"
    )
