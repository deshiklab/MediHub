# MediHub

## Project plan

- [Medical device integration platform — research, architecture, stack, and development plan](docs/DEVICE_INTEGRATION_PLATFORM_PLAN.md)

Bangladesh is a required deployment target; the plan includes a country-specific feasibility assessment and pilot gates.

## Development status

The first synthetic-only vertical slice is underway:

- Pydantic domain contracts, adapter/destination ports, a deterministic simulator, and an NDJSON CLI.
- A conservative route policy: synthetic data needs explicit test-destination acceptance; live data needs a matching, active, confirmed patient/device association and synchronized observation time.
- Async SQLAlchemy event persistence and an outbox committed in one transaction, with event-ID deduplication and collision detection.
- A single-item outbox dispatcher with database leases, attempt history, ACK/rejection handling, bounded exponential retries, and expired-lease recovery. Delivery is at-least-once; receivers should deduplicate on the stable event ID.
- A bounded, synthetic-only NDJSON replay CLI that validates events and demonstrates event-store deduplication without sending to a receiver.
- An in-process synthetic receiver and end-to-end `medihub demo` command; it opens no network connection.
- Alembic migrations for SQLite development and PostgreSQL; CI is configured to exercise PostgreSQL 16 and concurrent row claims.

This is not production-ready storage. Persisted event JSON can contain patient identifiers if supplied. Use synthetic data only until facility-approved access controls, encryption, retention, backups/recovery, and operational/security controls are implemented. There is not yet a real device protocol, destination connector, operator review UI, management API, or EHR/SHR integration. The replay command is local/test-only and does not deliver events. The simulator uses `example.invalid` terminology identifiers.

## Local development

Requires Python 3.11 or newer. Python 3.12 is the planned production baseline.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
pytest
```

Run an end-to-end synthetic check (in-memory SQLite and an in-process test receiver; it opens no network connection):

```bash
python -m medihub demo --count 5 --seed 7 \
  --start-at 2026-10-07T08:00:00Z
```

The JSON summary reports ingested events, duplicates, acknowledgements, test receipts, and simulator health. It is not a FHIR/HL7 integration test.

Create the local SQLite schema for persistent replay (the default database file is ignored by Git):

```bash
alembic upgrade head
```

Emit five deterministic synthetic scalar readings as newline-delimited JSON:

```bash
python -m medihub simulate --count 5 --seed 7 \
  --start-at 2026-10-07T08:00:00Z
```

Deterministic fault controls include `--duplicate-every`, `--reverse-adjacent-pairs`, `--clock-drift-ms-per-sample`, `--disconnect-after` / `--disconnect-for`, and `--firmware-version`. Unsupported firmware degrades adapter health and emits no observations.

Store a generated fixture locally, then replay it twice to see idempotent deduplication (`MEDIHUB_DATABASE_URL` can point to another migrated development database):

```bash
python -m medihub simulate --count 5 --seed 7 \
  --start-at 2026-10-07T08:00:00Z > /tmp/medihub-events.ndjson
python -m medihub replay /tmp/medihub-events.ndjson
python -m medihub replay /tmp/medihub-events.ndjson
```

Replay accepts only synthetic events without patient context, stores them without creating delivery intents, and prints counts only. CI runs Python 3.11 and 3.12 against PostgreSQL 16, applies migrations, and runs the test suite. Do not put real patient/device data in fixtures, command output, or source control.
