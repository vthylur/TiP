-- TASK-003 proof-only PostgreSQL + TimescaleDB physical-design migration.
--
-- This is not the final Tool1 market-data schema. The key/range model below is
-- deliberately labeled proof-only and exists only to demonstrate that the
-- selected database stack can enforce this class of storage constraint.

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE SCHEMA IF NOT EXISTS task003_db_design_proof;

CREATE TABLE task003_db_design_proof.market_bar_proof (
    source_system text NOT NULL,
    instrument_ref text NOT NULL,
    venue_ref text NOT NULL,
    bar_time timestamptz NOT NULL,
    valid_range tstzrange NOT NULL,
    open_price numeric(20, 10) NOT NULL,
    high_price numeric(20, 10) NOT NULL,
    low_price numeric(20, 10) NOT NULL,
    close_price numeric(20, 10) NOT NULL,
    volume numeric(20, 10) NOT NULL,
    loaded_at timestamptz NOT NULL DEFAULT now(),
    CHECK (NOT isempty(valid_range)),
    CHECK (lower(valid_range) < upper(valid_range))
);

SELECT create_hypertable(
    'task003_db_design_proof.market_bar_proof',
    'bar_time',
    if_not_exists => TRUE
);

CREATE UNIQUE INDEX market_bar_proof_unique_identity
ON task003_db_design_proof.market_bar_proof (
    source_system,
    instrument_ref,
    venue_ref,
    bar_time,
    lower(valid_range),
    upper(valid_range)
);

CREATE INDEX market_bar_proof_representative_read
ON task003_db_design_proof.market_bar_proof (
    source_system,
    instrument_ref,
    venue_ref,
    bar_time
);

ALTER TABLE task003_db_design_proof.market_bar_proof
ADD CONSTRAINT market_bar_proof_no_overlapping_valid_range
EXCLUDE USING gist (
    source_system WITH =,
    instrument_ref WITH =,
    venue_ref WITH =,
    bar_time WITH =,
    valid_range WITH &&
);
