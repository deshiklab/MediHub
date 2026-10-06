# Device-to-receiver mapping worksheet

## Purpose and boundary

This worksheet captures the Phase 0 mapping path required by the platform plan:

```text
exact source field/code/unit/state → MediHub canonical field/code/unit → exact destination field/profile
```

It is a discovery/review artifact, **not** an executable mapping catalog. `medihub validate-mapping` checks TOML structure, required fields, duplicate source keys, and evidence gates; it does not transform observations, resolve terminology, validate clinical meaning, enable mappings, or connect to a device/receiver. `mapping_activation_enabled` is always `false`.

No source metric, unit conversion, clinical threshold, FHIR profile, HL7 segment, or facility field is assumed. Complete the worksheet only from the authorized device documentation/synthetic messages and the actual receiver contract. Unknowns remain unresolved rather than being guessed.

## Create and validate locally

1. Copy `config/device-mapping.example.toml` to `config/device-mapping.local.toml`.
2. Use the same `discovery_profile_id` as the related local integration profile.
3. Add one `[[entries]]` row per exact source metric-and-unit signature. Use opaque controlled document/ticket IDs in evidence `reference` values.
4. Run:

   ```sh
   python -m medihub validate-mapping config/device-mapping.local.toml
   ```

The command emits only `schema_valid`, a readiness label, stable blocker/error codes, and `mapping_activation_enabled: false`; it does not print worksheet values or the path. Exit codes are `0` for a structurally complete worksheet with its review gates recorded, `1` for unresolved worksheet items, and `2` for an unreadable, oversized, malformed, or schema-invalid file. A zero exit code is not clinical mapping approval, destination conformance, or authorization to run a connector.

The strict schema rejects unknown and misspelled fields. Completed worksheets can expose facility/vendor details; keep them local and use only organization-approved sharing. The repository ignores `config/device-mapping.local.toml` and `*.mapping.local.toml`. Never store credentials, PHI, raw source frames, network endpoints, or vendor-restricted message captures in the worksheet or Git.

## Fill each row

### Source identity and evidence

Record exact manufacturer, model, firmware version(s), authorized adapter/protocol version, vendor permission, technical specification, and approved sample/synthetic messages. For each row, identify the exact source element/path and state; write `not_applicable` only when the authorized source contract shows there is no state field. The source signature used for duplicate detection is the exact element and state plus metric system/code and unit system/code. Do not match on display text or a “similar” label.

### Canonical representation

Record the chosen MediHub canonical element/path, state semantics, metric system/code, and unit system/code only after the clinical/engineering owners agree on meaning. Include the approved transformation rule, including identity/no-conversion where applicable, conversion direction, precision/rounding, bounds, and quality/state handling. Use an explicit `not_applicable` state only when the signed-off mapping shows no state mapping is needed. The linter does not execute or validate the rule.

### Destination contract

Record the actual destination product, protocol/interface version, target field/segment/path, profile, state behavior, code system/code, and unit system/code from the signed/approved receiver contract. Use `not_applicable` for state only when the receiver contract establishes that no state is carried. Do not write base URLs, hostnames, ports, credentials, or patient identifiers here. A generic R4 mapper or public sandbox is not proof of site or Bangladesh Core conformance.

### Review and synthetic vectors

Every mapping row needs an approved evidence reference. The worksheet-level approval must point to the reviewed mapping document, and `synthetic_test_vectors` must point to synthetic examples and expected results covering code/unit conversions, invalid/unknown values, precision boundaries, and destination validation. Use non-patient synthetic examples only.

## Linter behavior

Stable blockers include missing source/firmware/interface details, missing destination contract details, missing source or canonical codes/units, missing destination paths/profiles, missing transformation rules, unapproved evidence gates, missing synthetic vectors, and duplicate mapping entry IDs or full source field/state/metric/unit signatures. The linter reports a generic code rather than a row value, so clinical or vendor details are not echoed to terminal or CI output.

A complete worksheet is still a reviewed *discovery artifact*, not a production mapping. Runtime mappings must be implemented and independently tested against the actual authorized source and receiving-system contract. Phase 0 remains open until its other gates—site sponsor, patient-association authority/workflow, network flow, privacy/legal/regulatory review, and operational ownership—are also satisfied.
