# MediHub

## Project plan

- [Medical device integration platform — research, architecture, stack, and development plan](docs/DEVICE_INTEGRATION_PLATFORM_PLAN.md)

Bangladesh is a required deployment target; the plan includes a country-specific feasibility assessment and pilot gates.

## Development status

The first synthetic-only vertical slice is underway:

- Pydantic domain contracts, adapter/destination ports, a deterministic simulator, and an NDJSON CLI.
- A conservative route policy: synthetic data needs explicit test-destination acceptance; live data needs a matching, active, confirmed patient/device association and synchronized observation time.
- Async SQLAlchemy event persistence, eligible outbox intents, and policy holds committed atomically, with event-ID deduplication and collision detection.
- A durable routing-hold ledger that stores only destination IDs and stable reason codes; it has no free-text payloads or automatic override workflow.
- A privacy-minimized lifecycle audit ledger that commits event, route, and outbox transitions atomically; see [audit scope and limitations](docs/AUDIT_TRAIL.md).
- A single-item outbox dispatcher with database leases, attempt history, ACK/rejection handling, bounded exponential retries, and expired-lease recovery. Delivery is at-least-once; receivers should deduplicate on the stable event ID.
- A bounded, synthetic-only NDJSON replay CLI that validates events and demonstrates event-store deduplication without sending to a receiver.
- A generic synthetic FHIR R4 Observation mapper and in-process test receiver used by the end-to-end `medihub demo` command; it opens no network connection.
- A bounded synthetic Load & Capacity Lab (`medihub load-demo`) that measures aggregate local ingest/outbox throughput and acknowledgement latency; it uses in-memory SQLite and the in-process test receiver, not a production stack.
- A synthetic operations dashboard with a live in-memory event/outbox feed and a demo-only management workbench for simulator devices, mapping previews, bounded revision history/compare/restore, synthetic golden-vector QA, delivery-fault drills, and terminal-failure triage/replay; it has no physical-device controls or external destination configuration.
- A small generic FHIR R4 Observation shape check; it omits patient context and does not claim Bangladesh Core profile or facility-contract conformance.
- A Phase 0 integration-discovery worksheet and strict local TOML profile preflight; it reports safe blocker codes and never enables connectivity.
- A machine-readable source-to-canonical-to-destination mapping worksheet and strict linter; it never executes transformations or activates mappings.
- An offline mapping workbench that applies exact-match, versioned synthetic-only mappings to bounded synthetic fixtures; it has no database or destination connection.
- A file-backed synthetic recovery drill that simulates an expired outbox lease, a gateway engine restart, a transient receiver failure, and queue drain without external connectivity.
- Alembic migrations for SQLite development and PostgreSQL; CI is configured to exercise PostgreSQL 16 and concurrent row claims.

This is not production-ready storage. Persisted event JSON can contain patient identifiers if supplied. Use synthetic data only until facility-approved access controls, encryption, retention, backups/recovery, and operational/security controls are implemented. There is not yet a real device protocol, destination connector, operator review workflow, management API, or EHR/SHR integration. The dashboard below includes in-memory synthetic setup controls but is not a production operator control plane: it has no authentication, persistence, real device control, or external API connection. The audit ledger is metadata-only, unauthenticated, and not tamper-evident or a compliance claim. The replay command is local/test-only and does not deliver events. The simulator uses `example.invalid` terminology identifiers.

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

### Phase 0: integration discovery

The first device, receiving system, facility, and patient/device association workflow are not yet specified. MediHub therefore remains synthetic-only and does not implement a live connector. Review [the Phase 0 worksheet and gates](docs/INTEGRATION_DISCOVERY.md), copy `config/integration-profile.example.toml` to the Git-ignored `config/integration-profile.local.toml`, complete it locally, then run:

```bash
python -m medihub validate-profile config/integration-profile.local.toml
```

The command reports schema validity, readiness, and stable safe codes only; it never echoes profile values, and `connectivity_enabled` is always `false`. Completed profiles may contain sensitive facility/vendor details: keep them local, and never store secrets or PHI. Even `discovery_complete` is not production authorization or a conformance claim.

For the source-to-canonical-to-destination worksheet, copy `config/device-mapping.example.toml` to the Git-ignored `config/device-mapping.local.toml`, fill it only from authorized device/synthetic messages and the actual receiver contract, then run:

```bash
python -m medihub validate-mapping config/device-mapping.local.toml
```

This linter checks worksheet completeness and safe review gates only. `mapping_activation_enabled` is always `false`; no device metric is normalized and no receiver contract is inferred. See [the worksheet guide](docs/DEVICE_MAPPING_WORKSHEET.md).

For an isolated synthetic-only mapping dry run (no database or receiver), generate a fixture and map it with the committed simulator example:

```bash
python -m medihub simulate --count 3 --seed 7 \
  --start-at 2026-10-07T08:00:00Z > /tmp/medihub-synthetic.ndjson
python -m medihub map-synthetic /tmp/medihub-synthetic.ndjson \
  --mapping config/synthetic-mapping.example.toml
```

The mapper rejects patient context and non-synthetic inputs and emits no partial output on failure. It does not run as part of ingestion. See [the synthetic workbench limits](docs/SYNTHETIC_MAPPING_WORKBENCH.md).

Exercise file-backed queue recovery using a disposable SQLite file and the in-process synthetic receiver:

```bash
python -m medihub recovery-demo --count 3 --seed 7 \
  --duplicate-every 2 --start-at 2026-10-07T08:00:00Z
```

The command simulates an engine restart after an unfinished lease, injects one retryable receiver failure, and reports aggregate recovery counts. Its temporary DB is removed at exit; it does not use `MEDIHUB_DATABASE_URL` or contact a device/external receiver. This is not a power-loss, backup/restore, production, or facility acceptance test. See [the drill limitations](docs/SYNTHETIC_RECOVERY_DRILL.md).

Launch the synthetic operations dashboard and demo-only setup workbench locally:

```bash
python -m medihub dashboard --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. The operations feed emits one synthetic event every two seconds, redelivers every fourth event for deduplication, and records a `synthetic_not_accepted` hold. The setup workbench can register/disable simulator-only rows, add and preview synthetic mapping drafts, inspect, compare, and restore mapping revisions as new inactive versions; run version-tagged golden mapping tests with stale-result detection; and send a test event to the in-process receiver. The receiver fault drill can inject one retryable outcome or terminal rejection on the next synthetic send, then observe the normal outbox behavior; it never opens a network connection. Inspecting a delivery shows an allowlisted synthetic timeline, and a terminal failure below the retry cap can be replayed with its original event ID; patient/raw payload fields are not exposed. Device/mapping settings and event history are ephemeral; the event store retains at most 500 events, holds, and their audit metadata in in-memory SQLite. There are no physical device connections, external endpoint/credential fields, or live activation. For an Arena browser preview, bind to `0.0.0.0`; this unauthenticated, non-persistent demo must not be exposed as a production service. See [management workbench limits](docs/SYNTHETIC_MANAGEMENT_WORKBENCH.md).

Run an end-to-end synthetic check (in-memory SQLite and an in-process test receiver; it opens no network connection):

```bash
python -m medihub demo --count 5 --seed 7 \
  --start-at 2026-10-07T08:00:00Z
```

The JSON summary reports ingested events, duplicates, acknowledgements, test receipts, and simulator health. The demo validates a small generic R4 Observation shape only; it is not a network integration test or a validator for Bangladesh Core FHIR profiles or a facility contract.

Run the bounded synthetic load lab (up to 1,000 unique events):

```bash
python -m medihub load-demo --count 100 --seed 7 \
  --start-at 2026-10-07T08:00:00Z --duplicate-every 10
```

It reports aggregate event, duplicate, delivery, throughput, and p50/p95 acknowledgement-latency metrics. It always uses in-memory SQLite and the in-process synthetic receiver, ignores `MEDIHUB_DATABASE_URL`, prints no event payloads, and never opens a network connection. Treat the numbers only as local functional profiling—not production sizing, site SLOs, network performance, clinical readiness, or a validated load test. See [the lab metric definitions and limits](docs/SYNTHETIC_LOAD_LAB.md).

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
