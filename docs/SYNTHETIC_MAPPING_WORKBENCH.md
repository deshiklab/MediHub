# Offline synthetic mapping workbench

## Purpose and hard boundary

The mapping workbench exercises versioned code/unit lookup and bounded numeric transformation against **synthetic events only**. It is an offline dry run: the command does not write to the event store, create an outbox intent, invoke a destination adapter, or connect to any device/EHR.

The engine refuses non-synthetic events, patient/encounter context, and any device/firmware/adapter scope not explicitly named by the synthetic mapping set. It matches exact code-system/code and unit-system/code tuples; it never guesses from display labels. The built-in example is scoped only to MediHub's arbitrary simulator metric and is not a medical mapping, clinical validation, Bangladesh Core mapping, or facility contract.

This executable synthetic mapping set is distinct from `device-mapping.local.toml`: the latter is a discovery/review worksheet and is never executed. Neither artifact activates live mappings.

## Run a dry run

```sh
python -m medihub simulate --count 3 --seed 7 \
  --start-at 2026-10-07T08:00:00Z > /tmp/medihub-synthetic.ndjson

python -m medihub map-synthetic /tmp/medihub-synthetic.ndjson \
  --mapping config/synthetic-mapping.example.toml
```

The CLI validates the input with the existing bounded synthetic-NDJSON loader, loads a strict local TOML mapping set, maps the full batch in memory, and only then emits newline-delimited mapped results. A failed event prevents partial output. Results contain event IDs, synthetic device IDs, exact source/normalized code and unit pairs, decimal values, and mapping-set ID/version; they contain no patient fields, raw frames, or source-message IDs.

## Mapping contract

- Every mapping set declares `scope = "synthetic_only"`, a version, and exact manufacturer/model/firmware and adapter/version scope. The domain model has no live-enablement flag or runtime destination.
- Each entry matches the exact source metric system/code and source unit system/code. `display` text is not a key.
- Supported operations are `identity` and `linear` (`source × scale + offset`). Identity requires neutral scale/offset. Linear scale must be nonzero; scale and offset are bounded to ±10¹².
- The result is rounded half-even to the configured 0–9 decimal places and rejected if its absolute magnitude exceeds 10¹⁸. The existing event contract parses readings as floats; the workbench converts their canonical string representation to `Decimal` for its bounded transform and serializes decimal results as strings. It cannot recover precision already lost before mapping, which is acceptable only for this synthetic mechanics demo.
- Duplicate source signatures are rejected at configuration load. Missing mappings, scope mismatches, patient context, and numeric failures return stable codes without echoing input values.

Use `config/synthetic-mapping.example.toml` as the only committed example. Copy it to the Git-ignored `config/synthetic-mapping.local.toml` for local synthetic experiments. Do not put real device details, patient data, credentials, restricted vendor material, or production receiver endpoints in it.

This workbench proves only the mechanics of exact-match lookup and arithmetic using synthetic values. Real mappings remain blocked until the authorized device data dictionary, target canonical semantics, exact facility destination contract, owners, and synthetic acceptance vectors have been reviewed; a successful dry run does not change that gate.
