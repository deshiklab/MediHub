# Offline receiver-contract acceptance scenarios

## Boundary

`medihub contract-test` checks how MediHub's local contract model interprets a completed receiver worksheet. It runs only against a temporary, deterministic synthetic model. It does **not** call the named receiver, open a socket, execute a FHIR/HL7 adapter, confirm a sandbox, or prove that the real receiver matches the documented contract. The report sets `network_enabled`, `connectivity_enabled`, and `real_receiver_tested` to `false` and identifies the target as `local_synthetic_contract_model`.

The local SQLite inbox stores only a fixed synthetic test key, a normalized ACK code, and simulated receipt time. The disposable database is removed after the run. No event payload, patient data, receiver name, contract ID, or file path is included in results.

## Run it

First require the contract worksheet to be structurally complete and contract-documented:

```bash
python -m medihub validate-contract config/receiver-contract.local.toml
```

Then run the contract scenarios:

```bash
python -m medihub contract-test config/receiver-contract.local.toml
```

For bounded idempotency retention, declare the maximum retry/redelivery age the receiver must cover:

```bash
python -m medihub contract-test config/receiver-contract.local.toml \
  --required-idempotency-horizon-seconds 86400
```

The required horizon is a sender/site policy input, not a value inferred by MediHub; it must be between 1 second and 10 years. Retention must be **strictly greater** than the declared horizon so a retry at the expiry boundary cannot race with deletion. Indefinite retention does not require this argument. The command performs no wall-clock waits; times in the scenarios are synthetic.

Exit codes are `0` when every scenario passes, `1` when a documented assumption fails a scenario, and `2` when preflight is incomplete or a bounded-retention horizon is missing/invalid. Output contains aggregate booleans and stable scenario/result codes only.

## Scenario decision table

| Scenario | Local setup | Pass decision |
|---|---|---|
| Application ACK | Model one first receipt using a documented application-level success code. | The modeled result is acknowledged, non-duplicate, and creates one receipt. A transport-only ACK is blocked by preflight. |
| Duplicate delivery | Submit the same synthetic key twice immediately. | A documented safe duplicate outcome acknowledges the retry and keeps one receipt. `creates_duplicate`, `conflict`, and unknown outcomes are blocked before scenarios run. |
| Lost ACK, then retry | Model receiver acceptance, suppress the first ACK as a synthetic timeout, then retry the same key. | `transport_timeout` is classified retryable; the retry is acknowledged as duplicate without a second receipt. |
| Receiver restart | Commit one receipt, close the SQLite connection, reopen it, and redeliver the same key. | The documented restart-persistent idempotency assumption is modeled and one receipt remains. This is a local file-reopen test, not a real process or receiver test. |
| Permanent rejection | Select a documented permanent response code. | The response is classified as permanent rather than retryable. No external rejection is sent or observed. |
| Timeout | Evaluate the normalized `transport_timeout` outcome. | It is explicitly retryable and not simultaneously classified as permanent. |
| Retention horizon | Store once, advance synthetic time to the required redelivery horizon, then retry. | The retry remains deduplicated and retention is indefinite or strictly longer than the declared horizon. |
| Interface-version drift | Compare the pinned interface version with a deliberately altered local test version. | A mismatch is rejected before the model would dispatch. No remote capability statement is fetched. |

## ACK, retention, and idempotency decision matrix

| Contract fact | Acceptance decision |
|---|---|
| ACK level is `application`, with a documented meaning and success code | Model the success ACK; transport-only or unknown semantics remain blocked. |
| Idempotency key is known and has a normalized location | Continue; `none` or `unknown` is blocked. |
| Duplicate response is `same_acknowledgement` or `acknowledged_as_duplicate` | Model one unique receipt after retry. |
| Duplicate response is `conflict` | Block for explicit review of whether conflict reliably means “already accepted.” |
| Duplicate handling creates another record, or is unknown | Block. |
| Receiver idempotency survives receiver restart | Model a connection close/reopen against the local SQLite inbox. `false` or unverified remains blocked. |
| Retention is indefinite | Run retention scenario without an extra horizon argument. |
| Retention is bounded and seconds are present | Require `--required-idempotency-horizon-seconds`; pass only when `retention_seconds > horizon`. |
| `transport_timeout` is permanent or unclassified | Preflight blocks; an ambiguous outcome must be retryable. |
| Retryable and permanent code sets overlap, or protocol code prefixes conflict | Contract schema is invalid; the harness does not run. |

## Reading results

A passed run means only that these local, synthetic scenarios are consistent with the *documented assumptions*. It is not evidence that a hospital interface engine or EHR implements those assumptions. In particular, the model's SQLite uniqueness rule and stored ACK must not be described as a real destination's durable idempotency behavior.

Use the contract report together with [Phase 0 discovery](INTEGRATION_DISCOVERY.md) and the [receiver-contract schema guide](RECEIVER_CONTRACT.md). Before any live connector, separately test the exact authorized receiver in its approved synthetic sandbox and retain the facility-reviewed evidence. Bangladesh Core conformance, SHR access, patient-association authority, privacy/hosting review, and regulatory assessment are independent gates.
