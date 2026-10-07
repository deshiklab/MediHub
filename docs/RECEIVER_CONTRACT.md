# Receiver contract preflight

## Purpose and boundary

`ReceiverContract` is a versioned, strict Pydantic worksheet for recording the behavior an approved receiver contract documents. `medihub validate-contract` checks that worksheet locally and reports safe, stable blocker codes. It does **not** open a socket, call a receiver, exercise a sandbox, configure a connector, or enable delivery.

A `contract_documented` result means only that the schema has the required documented fields and an approved evidence reference. It is not proof that the receiver behaves as described, an interoperability/conformance result, security approval, production authorization, or a facility pilot decision. `connectivity_enabled` is always `false`.

## Run it

1. Copy `config/receiver-contract.example.toml` to the Git-ignored `config/receiver-contract.local.toml`.
2. Complete the local copy only from the exact, approved receiver contract. Use opaque document/ticket identifiers as evidence references.
3. Run:

   ```bash
   python -m medihub validate-contract config/receiver-contract.local.toml
   ```

Exit codes are `0` for a structurally valid `contract_documented` worksheet, `1` for a valid worksheet with unresolved/unsafe facts, and `2` for an unreadable, oversized, malformed, or schema-invalid file. The JSON result contains only `schema_valid`, `readiness`, stable `blockers`, sanitized `errors`, and `connectivity_enabled`. It does not print worksheet values or the path.

## Contract fields

The strict schema version is `1.0`. Unknown fields are rejected (`extra="forbid"`); this intentionally prevents credentials or arbitrary endpoint fields from becoming part of this worksheet.

- **Receiver identity:** local contract ID, related Phase 0 discovery profile ID, receiver product name, protocol (`fhir_r4` or `hl7_v2`), and exact interface/profile version.
- **Evidence:** `contract_evidence` must reference an approved controlled document or decision record. It must not contain a URL, secret, or file path.
- **Acknowledgement:** level (`application`, `transport_only`, or `unknown`), documented meaning (`accepted`, `durably_stored`, `queued`, `processed`, or `unknown`), and normalized success-code tokens. For example, use `http_201` for a FHIR HTTP status or `msa_aa` for an HL7 v2 MSA-1 result—not a raw HTTP body, HL7 message, or server response.
- **Idempotency:** key kind (`stable_event_id`, `fhir_identifier`, `hl7_msh10`, `facility_defined`, `none`, or `unknown`), a short normalized `key_location`, duplicate outcome, retention (`bounded`, `indefinite`, or `unknown`), optional retention seconds, and whether deduplication survives a receiver restart.
- **Failure handling:** normalized, disjoint retryable and permanent response-code tokens, plus whether the receiver's retry hint is honored, ignored, unsupported, or unknown. Use protocol response tokens such as `http_429`, `http_503`, `msa_ae`, or safe transport tokens such as `transport_timeout`; never paste raw responses or error text.
- **Limits:** a finite positive request timeout and the request-rate, batch-size, and request-byte limits. Each limit must be explicitly `specified`, `unlimited`, or `unknown`; for `specified`, give a positive integer value. `unknown` produces a blocker—it is not treated as unlimited.

FHIR success/failure codes must use `http_` tokens and HL7 success/failure codes must use `msa_` tokens. The only normalized transport failure tokens currently accepted are `transport_reset`, `transport_timeout`, and `transport_unavailable`. The validator rejects contradictory code classifications.

## Reading readiness results

A valid but incomplete example normally returns `readiness: "not_ready"` and codes such as `receiver_acknowledgement_level_unknown`, `receiver_idempotency_key_unknown`, `receiver_restart_idempotency_unverified`, `receiver_retryable_outcomes_missing`, or `receiver_request_timeout_missing`. An unresolved or duplicate-creating policy is blocked, and a generic `conflict` outcome requires explicit review before the worksheet can be considered documented. These stable codes can be used by local tooling without exposing vendor or facility values.

A bounded retention policy requires `retention_seconds`. `survives_receiver_restart = false` reports `receiver_idempotency_not_restart_durable`; `true` records what the approved contract says, not test evidence that it is true. The later contract-test lab should verify these claims in the receiver's authorized synthetic sandbox before any connector is considered.

## Data handling and Bangladesh gates

The schema contains no patient, encounter, credential, base-URL, hostname, port, certificate, or raw-message fields. Keep the local worksheet private because the receiver name and contract facts may still be facility/vendor-sensitive. The validator strips all input values, unknown-field names, paths, and Pydantic messages from its report. The 64 KiB input bound limits accidental oversized files.

This preflight does not establish Bangladesh Core FHIR conformance, national SHR access, a facility's writable interface, patient/device association authority, data-residency approval, or Bangladesh legal/regulatory readiness. Continue to use the Phase 0 [integration-discovery gates](INTEGRATION_DISCOVERY.md). Do not connect a live system based on this report; proceed only with the named facility's approvals and a separate contract-driven synthetic acceptance suite.
