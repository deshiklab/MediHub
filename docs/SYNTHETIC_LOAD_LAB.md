# Synthetic Load & Capacity Lab

`medihub load-demo` runs a finite, synthetic batch through MediHub's current local path:

1. The deterministic synthetic device simulator emits patient-free observations.
2. The ingestion policy writes events and eligible outbox rows to a fresh in-memory SQLite database.
3. The outbox dispatcher delivers to the in-process synthetic FHIR-shaped receiver.
4. The CLI prints one aggregate JSON summary; it does not print event IDs, measurements, or resource bodies.

The lab is bounded to **1,000 unique requested events** per run. It never reads `MEDIHUB_DATABASE_URL`, writes the normal local database, or opens a network connection. It uses no patient data and does not exercise a physical device or external receiver.

## Run it

```bash
python -m medihub load-demo --count 100 --seed 7 \
  --start-at 2026-10-07T08:00:00Z --duplicate-every 10
```

`--count` is the number of unique synthetic events requested (default `100`, allowed range `1–1000`). `--duplicate-every N` redelivers every Nth event with its original ID; `0` disables duplicates. `--interval-ms` changes the synthetic event-time spacing and defaults to `1000`. Seed, site, device, and start-time arguments configure the deterministic fixture, not a real installation.

The command emits one JSON object with aggregate counters, simulator health, and explicit `data_mode`, `storage`, `transport`, `network_enabled`, and `production_benchmark` fields. `events_read` includes redeliveries, while `events_requested` and `events_inserted` count the unique batch; `duplicate_events` reports repeated IDs. Delivery attempts, acknowledgements, rejections, retryable failures, and permanent failures describe the local test receiver, and `unique_test_receipts` confirms how many distinct IDs it accepted.

## Metric interpretation

- `duration_ms` measures the sequential ingest-and-drain portion of the run. It excludes engine/table initialization and cleanup.
- `events_per_second` is unique inserted events divided by that duration.
- `acknowledgements_per_second` is acknowledged deliveries divided by the same end-to-end duration.
- `acknowledgement_latency_ms_p50` and `acknowledgement_latency_ms_p95` use the nearest-rank percentile over successfully acknowledged unique events. Each sample runs from immediately before that event's ingest call until the dispatch call returns after recording its local acknowledgement; it therefore includes ingestion/acknowledgement database writes and time waiting behind the rest of this sequential batch, not just receiver execution time. Empty samples report `0`.

These figures are **local functional profiling only**. They are not production benchmarks, capacity or hardware-sizing estimates, facility/Site SLO evidence, network or receiver performance, clinical readiness, or a validated concurrency/load test. The path is sequential, uses in-memory SQLite, and has a synthetic FHIR-shaped receiver; it does not model the deployment database, hardware, network, authentication, real vendor behavior, or facility workflow. Compare runs only as rough observations in the same controlled local environment. Do not use them to approve a deployment or make a clinical/safety decision.

The small receiver checks a generic FHIR R4 Observation shape only. It does not assert Bangladesh Core profile or facility-contract conformance. Bangladesh deployment feasibility, data governance, security, and site acceptance gates remain as described in the [platform plan](DEVICE_INTEGRATION_PLATFORM_PLAN.md); this command does not change them.
