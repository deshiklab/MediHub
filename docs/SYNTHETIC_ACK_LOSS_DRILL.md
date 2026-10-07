# Synthetic acknowledgement-loss and idempotency drill

**Status:** Offline resilience scenario only
**Data:** Deterministic patient-free synthetic event
**Persistence:** Disposable file-backed SQLite outbox
**Transport:** In-process test receiver; network disabled

## Why this failure matters

A destination can accept an event and commit it while MediHub fails to receive or persist the acknowledgement. MediHub cannot infer whether the remote write happened merely because its connection timed out. Retrying is necessary for at-least-once delivery, but a receiver that does not deduplicate a stable identifier may create a duplicate record.

The supported reliability claim is therefore **at-least-once delivery with a stable event ID and receiver-specific idempotency where available**. This drill deliberately avoids claiming exactly-once delivery across independent systems.

## Scenario

The acceptance lab runs this sequence against the local synthetic FHIR-shaped receiver:

1. Persist one synthetic event and its outbox intent.
2. The worker sends it; the in-process receiver accepts the event and records its event ID.
3. The one-shot `ack_lost_once` injector suppresses the receiver's acknowledgement and returns the safe retryable code `synthetic_test_ack_lost_after_acceptance` to the worker.
4. Close and reopen the file-backed SQLite engine to simulate a worker restart.
5. The restarted worker retries the same outbox intent with the same event ID.
6. The receiver recognizes the already-seen ID, acknowledges the retry, and keeps one unique receipt.

Expected aggregate evidence:

| Metric | Expected |
|---|---:|
| Outbox/receiver delivery attempts | 2 |
| Retryable lost-ack outcomes | 1 |
| Acknowledged attempts | 1 |
| Receiver duplicate attempts | 1 |
| Unique receiver receipts | 1 |
| Final acknowledged outbox rows | 1 |
| Pending outbox rows | 0 |

No event ID, event payload, device ID, or patient value is included in the acceptance summary.

## Run it

This scenario is part of the combined workflow:

```bash
python -m medihub acceptance-demo --count 10 --seed 7 \
  --duplicate-every 2 --start-at 2026-10-07T08:00:00Z
```

The API Setup dashboard also offers **“Lose one acknowledgement after acceptance”** as a one-shot fault mode. It is in-process, synthetic-only, and does not perform a network request.

## Research note

A public GitHub example, [1](https://github.com/willfragoso/carequeue), describes a transactional outbox, at-least-once delivery, and an idempotent consumer in a fictional support workflow. It was reviewed for the pattern only; MediHub imports no code or test data from it and assumes nothing about a clinical destination's contract.

## Limits and future site test

The worker restart is simulated inside one Python process. The test receiver intentionally remains alive as a stand-in for the remote system and keeps its deduplication set in memory. The local test therefore verifies MediHub's retry state transition and the test receiver's stable-ID behavior; it does **not** prove that a real EHR, interface engine, or Bangladesh SHR endpoint commits idempotently, retains deduplication state across its own restart, or uses the same acknowledgement semantics.

Before a site pilot, agree with the named receiver on its actual idempotency key, duplicate response behavior, ACK/HTTP response meaning, and retention scope. Verify those behaviors in the receiver's approved synthetic test environment using the facility contract. Do not enable live delivery on the strength of this drill alone.
