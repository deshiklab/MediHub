# Synthetic restart and outbox recovery drill

## Purpose and safety boundary

`medihub recovery-demo` exercises the existing durable event/outbox state machine with synthetic events in a temporary, file-backed SQLite database. It intentionally leaves a delivery lease unfinished, disposes and reopens the database engine, advances a deterministic clock beyond the lease, injects one receiver outage, retries, and drains the queue to an in-process synthetic FHIR test sink.

The drill does not read or modify `MEDIHUB_DATABASE_URL`, create a persistent database in the repository, or connect to a device, external network, FHIR server, or EHR. Its temporary database is removed when the command exits. Output is aggregate counts and stable status codes only; it contains no event IDs, values, patient context, or raw payloads.

## Run it

```sh
python -m medihub recovery-demo --count 3 --seed 7 \
  --duplicate-every 2 --start-at 2026-10-07T08:00:00Z
```

The drill accepts 1–100 synthetic events. Duplicate redelivery is optional and demonstrates event-ID deduplication before the recovery sequence. A successful run reports one simulated process restart, one expired lease recovered, one injected retryable receiver failure plus the expired-lease attempt, acknowledged deliveries, and zero pending deliveries.

## What it verifies

- Events, delivery intents, attempt history, and audit transitions survive closing and reopening the SQLAlchemy engine over the same SQLite file.
- A claim left in `sent` with an expired lease is recovered and its prior attempt is recorded with the `lease_expired` code.
- The worker records a transient adapter exception without exposing exception text, retries, and eventually records acknowledgement.
- Duplicate synthetic input does not create duplicate event/outbox rows or duplicate test receipts.
- The queue drains without patient context or an external receiver.

## What it does not verify

This is a deterministic same-process **engine restart simulation**, not a forced process kill, power-loss test, filesystem/disk-full test, backup/restore test, SQLite corruption test, or PostgreSQL concurrency test. The temporary schema is created from ORM metadata rather than from a deployed migration run. The test sink's deduplication state is in-process and is not evidence of any real receiver's idempotency behavior. The drill is not a device integration, clinical validation, production-readiness check, Bangladesh Core conformance test, or Phase 0 approval.

Real site recovery qualification still needs an approved facility/device/destination contract, migrations and backup/restore verification, and supervised outage testing on the target edge hardware and storage.
