"""
TASK-003 proof-only benchmark harness.

Measures a representative Tool1 read-query shape against the isolated Docker
Compose database. The output is a repeatable local measurement, not a
production latency target, SLA, or final physical-design claim.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import time
from pathlib import Path


COMPOSE_SERVICE = "db"
PSQL_USER = "tip"
PSQL_DB = "tip_test"
PROOF_SCHEMA = "task003_db_design_proof"
PROOF_TABLE = "market_bar_proof"
REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = REPO_ROOT / "migrations" / "task003_db_design_proof.sql"


def psql(*, command: str | None = None, stdin_sql: str | None = None) -> subprocess.CompletedProcess:
    args = [
        "docker",
        "compose",
        "exec",
        "--no-TTY",
        COMPOSE_SERVICE,
        "psql",
        "--username",
        PSQL_USER,
        "--dbname",
        PSQL_DB,
        "--set",
        "ON_ERROR_STOP=1",
        "--tuples-only",
        "--no-align",
    ]
    if command is not None:
        args.extend(["--command", command])
    return subprocess.run(
        args,
        cwd=REPO_ROOT,
        input=stdin_sql,
        capture_output=True,
        text=True,
    )


def run_sql(command: str) -> str:
    result = psql(command=command)
    if result.returncode != 0:
        raise RuntimeError(
            f"psql exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result.stdout.strip()


def apply_migration() -> None:
    run_sql(f"DROP SCHEMA IF EXISTS {PROOF_SCHEMA} CASCADE;")
    result = psql(stdin_sql=MIGRATION_PATH.read_text(encoding="utf-8"))
    if result.returncode != 0:
        raise RuntimeError(
            "proof migration failed\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


def seed_rows(rows: int) -> None:
    run_sql(
        f"""
        WITH generated AS (
            SELECT
                i,
                '2026-01-02 09:30:00+00'::timestamptz
                    + (i || ' minutes')::interval AS bar_time
            FROM generate_series(0, {rows - 1}) AS s(i)
        )
        INSERT INTO {PROOF_SCHEMA}.{PROOF_TABLE}
          (source_system, instrument_ref, venue_ref, bar_time, valid_range,
           open_price, high_price, low_price, close_price, volume)
        SELECT
          'benchmark_feed',
          'benchmark_instrument',
          'benchmark_venue',
          bar_time,
          tstzrange(bar_time, bar_time + interval '1 minute', '[)'),
          100 + i,
          101 + i,
          99 + i,
          100.5 + i,
          1000 + i
        FROM generated;
        """
    )


def measure_query(iterations: int) -> tuple[list[float], int]:
    query = (
        f"SELECT bar_time, close_price "
        f"FROM {PROOF_SCHEMA}.{PROOF_TABLE} "
        "WHERE source_system = 'benchmark_feed' "
        "AND instrument_ref = 'benchmark_instrument' "
        "AND venue_ref = 'benchmark_venue' "
        "AND bar_time >= '2026-01-02 09:30:00+00' "
        "AND bar_time < '2026-01-02 10:30:00+00' "
        "ORDER BY bar_time "
        "LIMIT 100;"
    )

    durations_ms: list[float] = []
    rows_returned = 0
    for _ in range(iterations):
        started = time.perf_counter()
        output = run_sql(query)
        durations_ms.append((time.perf_counter() - started) * 1000)
        rows_returned = 0 if not output else len(output.splitlines())
    return durations_ms, rows_returned


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--iterations", type=int, default=5)
    args = parser.parse_args()

    if args.rows < 1:
        raise SystemExit("--rows must be at least 1")
    if args.iterations < 1:
        raise SystemExit("--iterations must be at least 1")

    apply_migration()
    seed_rows(args.rows)
    durations_ms, rows_returned = measure_query(args.iterations)

    measurement = {
        "task": "TASK-003-db-design-proof",
        "schema": PROOF_SCHEMA,
        "table": PROOF_TABLE,
        "dataset_rows": args.rows,
        "iterations": args.iterations,
        "query_shape": "source_system/instrument_ref/venue_ref equality plus bar_time range",
        "rows_returned": rows_returned,
        "min_query_ms": round(min(durations_ms), 3),
        "avg_query_ms": round(statistics.fmean(durations_ms), 3),
        "max_query_ms": round(max(durations_ms), 3),
        "environment": {
            "database": "Docker Compose db service",
            "compose_service": COMPOSE_SERVICE,
            "client": "docker compose exec psql",
        },
        "disclaimer": (
            "Measured proof-only result; not a production SLA or final physical design."
        ),
    }
    print(json.dumps(measurement, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
