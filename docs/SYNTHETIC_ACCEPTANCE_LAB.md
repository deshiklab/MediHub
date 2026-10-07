# Synthetic acceptance and resilience lab

**Status:** Offline implementation-level checks only
**Scope:** Synthetic events, local SQLite, and in-process receivers; not facility acceptance
**Patient data:** Not used
**Network access:** Disabled

## Purpose

`medihub acceptance-demo` is a bounded workflow that runs the repository's existing synthetic pipeline checks together. It is intended as a repeatable code-level regression gate before any later, separately authorized integration testing. It does **not** configure a device, activate a mapping, connect to an EHR/EMR, contact Bangladesh's SHR, or qualify a hospital site.

Run it from the repository root:

```bash
python -m medihub acceptance-demo \
  --count 10 \
  --seed 7 \
  --duplicate-every 2 \
  --start-at 2026-10-07T08:00:00Z
```

`--count` is the number of unique synthetic events used by the batch stages. It is bounded to **2–100** so the recovery and load stages remain practical. `--duplicate-every 0` disables duplicate emissions; otherwise every Nth source event is emitted twice with the same event ID. The default is 10 unique events and a duplicate every two events.

The JSON output contains stage summaries, aggregate pass/fail assertions, and local load measurements. Exit status is `0` when all assertions pass, `1` when the run completes but an assertion fails, and `2` when the command or a stage cannot run. Failure messages use stable safe codes or exception types, not event payloads.

## What it exercises

| Stage | Checks |
|---|---|
| Pipeline and deduplication | Simulator → ingestion → event store/outbox → synthetic FHIR-shaped in-process receiver; expected duplicate count, unique inserts, acknowledgements, and unique receipts. |
| Mapping | Exact-scope, identity mapping of the simulator's `example.invalid` scalar code and dimensionless unit using a built-in synthetic-only mapping; verifies complete, non-partial, synthetic-only results. |
| Routing and fault/replay | Persists one expected policy hold for a destination that does not accept synthetic data; injects one retryable failure, then one terminal rejection; exercises the guarded synthetic terminal replay; verifies the final acknowledgement and empty pending queue. |
| Restart recovery | Calls the existing file-backed recovery drill, including an unfinished lease, simulated process restart, transient failure, retry, and queue drain. Its temporary SQLite database is removed at exit. |
| Bounded load | Calls the existing in-memory load lab with the same unique-event count and duplicate setting; reports aggregate throughput and acknowledgement latency without asserting environment-dependent performance thresholds. |

The command combines these stages rather than sharing a single database between them: the pipeline/fault stages use in-memory SQLite, the recovery stage uses a disposable temporary SQLite file, and all receivers are in-process. It does not read `MEDIHUB_DATABASE_URL`, persist a report, or open sockets.

## Reading the result

- `status` and `checks` report only the implemented synthetic invariants.
- `pipeline`, `mapping`, `fault_drill`, `restart_recovery`, and `bounded_load` contain aggregate evidence for each stage.
- `network_enabled` is always `false`; the fault injector and load summary also report their transport limits.
- `facility_qualification` is always `not_performed`. A passing run means only that these repository scenarios passed locally.
- Load rates and latency are useful for comparing code changes in a consistent environment. They are not a throughput guarantee, production benchmark, hospital SLO, or capacity sign-off.

## Safety and validation limits

The source is MediHub's deterministic scalar simulator, not a medical device. The mapping and generic FHIR R4 shape are synthetic examples, not BD-Core profile validation or an actual receiving-system contract. The local receiver cannot establish network behavior, authentication, authorization, server capability, message acknowledgement semantics, facility workflow, patient association, operational readiness, or regulatory status.

Do not use real observations, patient identifiers, facility credentials, or production endpoints with this command. Do not describe a passing result as device certification, clinical validation, Bangladesh Core conformance, production readiness, or site acceptance. Those require the named Bangladesh facility, approved device/interface, receiving-system contract, patient-context workflow, security/privacy review, and the responsible clinical/biomedical/IT owners.

The workflow follows a staged synthetic-test-harness pattern also seen in public projects such as [healthcare-test-data-lab](https://github.com/Nirmitee-tech/healthcare-test-data-lab), used here as architectural research only. MediHub does not import that project's code, test data, or facility contracts.
