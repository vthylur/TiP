"""
TASK-003 proof-only PostgreSQL + TimescaleDB physical-design integration test.

This test intentionally proves a class of database capabilities for Tool1:
Timescale-backed time-series storage, database-enforced uniqueness, prevention
of overlapping proof-only validity ranges, isolated schema behavior, and a
representative read-query shape.

Nothing in this file defines the final Tool1 canonical market-data identity,
production primary key, or production overlap semantics.
"""

import json
import subprocess
from pathlib import Path


_COMPOSE_SERVICE = "db"
_PSQL_USER = "tip"
_PSQL_DB = "tip_test"
_PROOF_SCHEMA = "task003_db_design_proof"
_PROOF_TABLE = "market_bar_proof"
_REPO_ROOT = Path(__file__).resolve().parents[1]
_MIGRATION_PATH = _REPO_ROOT / "migrations" / "task003_db_design_proof.sql"
_BENCHMARK_PATH = _REPO_ROOT / "scripts" / "task003_db_design_benchmark.py"


def _psql(
    *,
    command: str | None = None,
    stdin_sql: str | None = None,
) -> subprocess.CompletedProcess:
    """Run SQL through psql inside the isolated Compose database service."""
    args = [
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
        "--set",
        "ON_ERROR_STOP=1",
        "--tuples-only",
        "--no-align",
    ]
    if command is not None:
        args.extend(["--command", command])
    return subprocess.run(
        args,
        input=stdin_sql,
        capture_output=True,
        text=True,
    )


def _run_sql(command: str) -> str:
    result = _psql(command=command)
    assert result.returncode == 0, (
        f"psql exited {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return result.stdout.strip()


def _run_sql_expect_failure(command: str) -> str:
    result = _psql(command=command)
    assert result.returncode != 0, (
        "Expected SQL command to fail, but it succeeded.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return result.stderr


def _apply_proof_migration() -> None:
    assert _MIGRATION_PATH.exists(), (
        "TASK-003 proof migration is required at "
        f"{_MIGRATION_PATH.relative_to(_REPO_ROOT)}"
    )
    _run_sql(f"DROP SCHEMA IF EXISTS {_PROOF_SCHEMA} CASCADE;")
    result = _psql(stdin_sql=_MIGRATION_PATH.read_text(encoding="utf-8"))
    assert result.returncode == 0, (
        f"proof migration failed with exit {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_task003_proof_schema_enforces_timescale_uniqueness_overlap_and_read_shape() -> None:
    """Proof-only DB design behavior is enforced by PostgreSQL + TimescaleDB."""
    migration_applied = False
    try:
        _apply_proof_migration()
        migration_applied = True

        hypertable_count = _run_sql(
            "SELECT count(*) "
            "FROM timescaledb_information.hypertables "
            f"WHERE hypertable_schema = '{_PROOF_SCHEMA}' "
            f"AND hypertable_name = '{_PROOF_TABLE}';"
        )
        assert hypertable_count == "1"

        exclusion_constraint_count = _run_sql(
            "SELECT count(*) "
            "FROM pg_constraint c "
            "JOIN pg_namespace n ON n.oid = c.connamespace "
            f"WHERE n.nspname = '{_PROOF_SCHEMA}' "
            "AND c.conname = 'market_bar_proof_no_overlapping_valid_range' "
            "AND c.contype = 'x';"
        )
        assert exclusion_constraint_count == "1"

        _run_sql(
            f"""
            INSERT INTO {_PROOF_SCHEMA}.{_PROOF_TABLE}
              (source_system, instrument_ref, venue_ref, bar_time, valid_range,
               open_price, high_price, low_price, close_price, volume)
            VALUES
              ('proof_feed', 'proof_instrument', 'proof_venue',
               '2026-01-02 09:30:00+00',
               tstzrange('2026-01-02 09:30:00+00', '2026-01-02 09:31:00+00', '[)'),
               100.00, 101.00, 99.50, 100.50, 1000);
            """
        )

        duplicate_error = _run_sql_expect_failure(
            f"""
            INSERT INTO {_PROOF_SCHEMA}.{_PROOF_TABLE}
              (source_system, instrument_ref, venue_ref, bar_time, valid_range,
               open_price, high_price, low_price, close_price, volume)
            VALUES
              ('proof_feed', 'proof_instrument', 'proof_venue',
               '2026-01-02 09:30:00+00',
               tstzrange('2026-01-02 09:30:00+00', '2026-01-02 09:31:00+00', '[)'),
               100.00, 101.00, 99.50, 100.50, 1000);
            """
        )
        assert (
            "market_bar_proof_unique_identity" in duplicate_error
            or "market_bar_proof_no_overlapping_valid_range" in duplicate_error
        )

        overlap_error = _run_sql_expect_failure(
            f"""
            INSERT INTO {_PROOF_SCHEMA}.{_PROOF_TABLE}
              (source_system, instrument_ref, venue_ref, bar_time, valid_range,
               open_price, high_price, low_price, close_price, volume)
            VALUES
              ('proof_feed', 'proof_instrument', 'proof_venue',
               '2026-01-02 09:30:00+00',
               tstzrange('2026-01-02 09:30:30+00', '2026-01-02 09:31:30+00', '[)'),
               100.10, 101.10, 99.60, 100.60, 1001);
            """
        )
        assert "market_bar_proof_no_overlapping_valid_range" in overlap_error

        _run_sql(
            f"""
            INSERT INTO {_PROOF_SCHEMA}.{_PROOF_TABLE}
              (source_system, instrument_ref, venue_ref, bar_time, valid_range,
               open_price, high_price, low_price, close_price, volume)
            VALUES
              ('proof_feed', 'proof_instrument', 'proof_venue',
               '2026-01-02 09:31:00+00',
               tstzrange('2026-01-02 09:31:00+00', '2026-01-02 09:32:00+00', '[)'),
               100.50, 101.50, 100.00, 101.00, 1002);
            """
        )

        representative_rows = _run_sql(
            f"""
            SELECT bar_time, close_price
            FROM {_PROOF_SCHEMA}.{_PROOF_TABLE}
            WHERE source_system = 'proof_feed'
              AND instrument_ref = 'proof_instrument'
              AND venue_ref = 'proof_venue'
              AND bar_time >= '2026-01-02 09:30:00+00'
              AND bar_time < '2026-01-02 09:32:00+00'
            ORDER BY bar_time
            LIMIT 100;
            """
        )
        assert representative_rows.splitlines() == [
            "2026-01-02 09:30:00+00|100.5000000000",
            "2026-01-02 09:31:00+00|101.0000000000",
        ]

        assert _BENCHMARK_PATH.exists(), (
            "TASK-003 proof benchmark harness is required at "
            f"{_BENCHMARK_PATH.relative_to(_REPO_ROOT)}"
        )
        benchmark = subprocess.run(
            [
                "python",
                str(_BENCHMARK_PATH),
                "--rows",
                "120",
                "--iterations",
                "3",
            ],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert benchmark.returncode == 0, (
            f"benchmark exited {benchmark.returncode}.\n"
            f"stdout: {benchmark.stdout}\nstderr: {benchmark.stderr}"
        )
        measurement = json.loads(benchmark.stdout)
        assert measurement["task"] == "TASK-003-db-design-proof"
        assert measurement["schema"] == _PROOF_SCHEMA
        assert measurement["table"] == _PROOF_TABLE
        assert measurement["dataset_rows"] == 120
        assert measurement["iterations"] == 3
        assert measurement["query_shape"] == (
            "source_system/instrument_ref/venue_ref equality plus bar_time range"
        )
        assert measurement["environment"]["database"] == "Docker Compose db service"
        assert measurement["disclaimer"] == (
            "Measured proof-only result; not a production SLA or final physical design."
        )
        assert measurement["min_query_ms"] >= 0
        assert measurement["avg_query_ms"] >= 0
    finally:
        if migration_applied:
            _run_sql(f"DROP SCHEMA IF EXISTS {_PROOF_SCHEMA} CASCADE;")
