# Phase 0: integration discovery preflight

## Purpose and boundary

MediHub is continuing Phase 0 discovery because the first authorized device, receiving system, facility, and clinical association workflow have not yet been specified. This preflight provides a structured worksheet and a local validator; the companion [receiver-contract preflight](RECEIVER_CONTRACT.md) records ACK, idempotency, retry/error, and limit semantics. Neither implements, configures, or enables a device/EHR connection.

A profile reported as `discovery_complete` means only that the profile is structurally complete and every listed discovery gate has an approved or documented not-applicable decision with an evidence reference. It is **not** production authorization, regulatory approval, a safety case, a conformance claim, or permission to connect. `connectivity_enabled` is always `false` in the validator output. Connector code remains synthetic/in-process until the exact authorized interface contract and clinical workflow are supplied and separately reviewed.

## Start locally

1. Copy `config/integration-profile.example.toml` to `config/integration-profile.local.toml`.
2. Fill it in with the first facility's verified discovery details; do not commit the completed local copy.
3. Run:

   ```sh
   python -m medihub validate-profile config/integration-profile.local.toml
   ```

The command emits one JSON object containing only schema validity, a readiness label, stable blocker/error codes, and `connectivity_enabled: false`. It never prints profile values or the path. Exit codes are `0` for a structurally valid, discovery-complete profile, `1` for a valid profile with unresolved blockers, and `2` for an unreadable, oversized, malformed, or schema-invalid profile. A nonzero result does not prevent synthetic development workflows.

The validator uses a strict schema (`extra="forbid"`): misspelled and unknown fields, including attempted credential fields, are rejected. Completed TOML can still contain sensitive facility or vendor details, so keep it local and share it only through an organization-approved channel. The repository ignores `config/integration-profile.local.toml` and `*.profile.local.toml`.

## Discovery worksheet

Use the example TOML as the machine-readable checklist. Resolve the following with the facility and vendors; record opaque document/ticket identifiers in each `reference`, not the documents themselves.

### Intended use and first site

- Define the narrow initial workflow, intended users, observations/data elements, frequency, operational response, and out-of-scope actions.
- Identify the first Bangladesh facility and the accountable clinical, biomedical/engineering, IT/interface, privacy/security, and operational owners. Keep personal contact information in the facility's controlled systems; the profile should point to an approved owner roster or decision record.

### Device and authorization

- Record the exact manufacturer, model, hardware/firmware versions in scope, transport, and protocol/interface version.
- Obtain vendor authorization and the exact official technical/interface specification, including framing, units/codes, timestamps, identifiers, alarms/status, retries, and error behavior as applicable.
- Identify any existing manufacturer gateway, data dictionary, vendor license/authorization, approved simulator, and test hardware. Obtain authorized sample or synthetic messages that can be used to verify the map; record references to controlled assets rather than copying restricted captures into this repository.
- Do not infer an interface from a product family, marketing sheet, simulator, or another facility's setup. No device polling or connection is enabled by this profile.

### Destination contract

- Name the exact receiving product/system and interface/version, confirming whether an interface engine is the actual receiver. For FHIR, record the base/version, CapabilityStatement, profiles, scopes, and write behavior; for HL7 v2, record the version/profile, message examples, ACK rules, and approved MLLP route. Keep hostnames, ports, tokens, and raw endpoints out of this profile.
- Specify acknowledgment meaning, idempotency/replay behavior, error codes, mapping/versioning, rate limits, downtime handling, and support/rollback ownership. Obtain the facility-approved contract and synthetic test receiver or sandbox procedure.
- Record the ACK, duplicate, retry/error, timeout, and limit facts in the local [receiver-contract worksheet](RECEIVER_CONTRACT.md). Its validator checks documented completeness only; it never connects and cannot verify receiver behavior.
- Complete the [machine-readable protocol/field mapping worksheet](DEVICE_MAPPING_WORKSHEET.md) before coding: source field/code/unit/state → canonical field → destination field/profile. Leave unknown mappings explicitly unresolved; link the approved worksheet using an evidence reference.
- A generic FHIR R4 mapper or a public sandbox is not evidence of Bangladesh Core or facility-contract conformance, nor is it production access.

### Patient/device association authority

- Identify the authoritative facility-approved source and the clinical workflow that establishes which patient/encounter/location is associated with a device and for what interval. For Bangladesh, explicitly confirm whether a facility patient-ID, UHID/Health ID, or authorized SHR path is available; do not assume national production access.
- Define who can resolve ambiguity, how reassignment/disconnection is handled, how stale associations are detected, and how mismatches are quarantined/escalated. Do not derive patient identity from a device label, room/bed, or timing alone.
- Record event timing, expected data rate, buffering duration, retention, and the clinical verification step before chart visibility. Keep real patient identifiers and examples out of the profile and synthetic tests.
- Name the accountable clinical owner and record the approval reference. Keep actual patient identifiers and examples out of the profile and synthetic tests.

### Hosting, privacy, legal, and regulatory review

- Record the facility-approved hosting/data-residency location, an explicit cross-border decision, the operating party, and approved network zones/flow. The profile stores an evidence reference for the approved network flow, not hostnames, ports, credentials, or firewall secrets.
- Obtain the facility privacy/security and Bangladesh legal review for sensitive health-data processing, retention, access, incident response, data-processing terms (and any BAA-equivalent obligations if applicable), and any cross-border transfer. Confirm whether MediHub remains limited to passive data handling. This worksheet is not legal advice; interpretations and approvals belong to qualified Bangladesh counsel and the relevant authorities.
- Obtain a device/software regulatory assessment from qualified Bangladesh regulatory counsel and the appropriate authority where applicable. Do not infer a regulatory classification or approval from this validator.
- Confirm the exact applicable Bangladesh Core FHIR profile/version and facility-specific contract separately if a FHIR destination is selected. The current generic synthetic FHIR R4 path is not a Bangladesh Core claim.

### Synthetic acceptance plan

Before any pilot decision, define reproducible tests using synthetic data only: valid and invalid frames/messages, unit/code handling, time zones and clock drift, duplicate/replay delivery, out-of-order data, device disconnect/reconnect, receiver outage/recovery, invalid association, authorization failures, auditability, and safe quarantine. Document expected results and who signs them off. Do not use real patient records in fixtures, logs, screenshots, or this repository.

The Phase 0 exit gate requires a named device and destination, written interface authorization, authorized sample/synthetic messages, an approved network flow, a mapping worksheet, a synthetic test plan, and explicit non-goals. A Bangladesh live-data pilot additionally requires named local owners, patient-identity/privacy workflows, hosting/cross-border decision, and a documented regulatory assessment. If any item is missing, continue discovery instead of guessing.

## Gate statuses and evidence references

Every gate uses one of these statuses:

- `open`: not yet assessed or assigned.
- `in_review`: evidence/decision is being reviewed.
- `blocked`: a known issue prevents completion.
- `approved`: the named accountable authority accepted the item.
- `not_applicable`: an accountable authority explicitly determined it does not apply.

`approved` and `not_applicable` require an opaque evidence reference (for example, a controlled document ID or ticket ID). Do not use URLs, filesystem paths, credentials, or secret values as references. An empty/TBD field or incomplete gate produces a stable blocker code. A documented `not_applicable` decision is not a claim that a clinical or regulatory requirement can be waived.

## Information needed to progress beyond Phase 0

Provide through an approved channel (not as secrets/PHI in the repository):

1. Exact device make/model and firmware versions, plus the authorized interface specification and written vendor permission.
2. Exact first receiver product and facility interface contract/sandbox acceptance criteria.
3. Facility-approved patient/device association authority and workflow, with clinical owner.
4. Hosting/data-residency decision, accountable site owners, and privacy/legal/regulatory review path.
5. Synthetic-only acceptance criteria and approval owners.

Until these are known and approved, MediHub remains synthetic-only and no live connector or patient association integration should be built.
