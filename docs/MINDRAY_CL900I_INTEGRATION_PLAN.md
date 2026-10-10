# Mindray CL-900i integration plan

**Status: discovery only.** The CL-900i is now the proposed first analyzer, but its exact LIS interface, installed software/version, host configuration, facility, and receiving-system contract have not been supplied. MediHub remains synthetic-only: there is no CL-900i adapter, live listener, patient-result model, or real EMS/EMR sender. This document does not authorize a connection.

## What is publicly confirmed

Mindray describes the CL-900i as a fully automated chemiluminescence immunoassay (CLIA) analyzer using an enhanced ALP-AMPPD method, with throughput up to 180 tests/hour, 50 sample positions, and 15 reagent positions. See the [official CL-900i product page](https://www.mindray.com/en/products/laboratory-diagnostics/chemiluminescence-immunoassay/small-test-volume/cl-900i) and [official product brochure](https://www.mindray.com/content/dam/xpace/en/resources/brochure/cl-900i-product-brochure.pdf).

Those public product materials do **not** specify the exact host/LIS protocol and message profile, result-transfer direction, acknowledgement behavior, or the interface available on a particular unit/software release. Do not infer ASTM, HL7, TCP/IP, RS-232, query/poll support, or bidirectional behavior from another Mindray product, an unofficial manual mirror, or another site's installation. Obtain the Mindray-authorized LIS/host-interface guide for the exact CL-900i configuration and written authorization before implementing or connecting anything.

## Proposed safe data path

```text
CL-900i
  └─ vendor-supported LIS interface (protocol and direction: TBD)
       └─ MediHub lab ingress adapter (initial scope: results only, read-only)
            └─ frame/message validation and protocol parser
                 └─ typed lab-result event preserving source data and status
                      └─ accession/order and patient-context verification
                           └─ reviewed assay/code/unit mapping and quarantine
                                └─ durable outbox with stable idempotency key
                                     └─ the named LIS / interface engine / EMR / EMS
                                          (only via its approved receiver contract)
```

If the facility already uses a validated LIS, prefer an approved read-only/export/API connection from that LIS rather than inserting MediHub inline between the analyzer and the LIS or creating a second analyzer host connection. The lab and Mindray must approve any direct analyzer connection and confirm that it will not disrupt the existing workflow.

“Pull” needs a device-specific decision: completed results might be pushed by the analyzer, requested by an authorized host, or exposed through the LIS. Start with the least-permissive vendor-supported **results-only** mode. Do not download worklists, send orders, change analyzer configuration, start/stop assays, or issue other control commands in the first integration.

## Data and workflow requirements

The current `ObservationEvent` accepts only a numeric scalar, and the current FHIR R4 mapper and receiver are synthetic-only. A laboratory integration needs a separately reviewed result model before a live parser is written. The exact fields must come from the authorized interface guide and facility workflow; at minimum, assess:

- analyzer identity/model/software version and source message/result identifiers;
- specimen/accession and order identifiers, sample type, assay/test code, raw result value/text, original unit, and result timestamp;
- result lifecycle (for example, preliminary, verified/final, corrected, repeated, or cancelled), analyzer flags, dilution/repeat details, and any reference/interpretation fields actually supplied;
- source code/unit and any proposed normalized code/unit, with a reviewed, versioned mapping and a traceable reason for every conversion.

Preserve the source result, code, unit, status, and timing. Do not guess an assay mapping, convert units, round values, infer a reference range, or turn an analyzer flag into a clinical interpretation. Unknown or inconsistent codes/units/statuses, duplicate/correction ambiguity, and missing association data must be quarantined for authorized review—not silently forwarded. Define separately how QC, calibration, maintenance, and non-patient records are recognized so they cannot be mistaken for patient results.

Associate a result using the facility-authoritative accession/order and patient-context workflow. Do not match by patient name, bed/location, timing, or analyzer/sample position alone. Define which result states may leave MediHub and who verifies/releases them; an analyzer transmission acknowledgement is not the same as clinical verification or EMR acceptance.

## Destination contract

First identify what “EMS” means in this deployment and whether the actual receiver is an LIS, interface engine, EMR, emergency-services system, or another product. Obtain that exact receiver's approved interface contract before choosing a sender:

- **HL7 v2:** exact version/profile, required ORU message structure (or other agreed message), transport/framing, ACK/NAK meaning, correction/replacement rules, duplicate key, retry policy, and sandbox procedure.
- **FHIR:** exact server/version, CapabilityStatement, accepted profiles/resources (often a coordinated DiagnosticReport/Observation/Specimen/ServiceRequest workflow), identifiers, authorization/scopes, response/ACK meaning, idempotency, and correction behavior.

These are alternatives to evaluate against the real receiver contract, not assumptions about what a particular Bangladesh EMS/EMR accepts. The current generic synthetic FHIR R4 Observation is not a production sender, Bangladesh Core conformance claim, or facility integration.

## Required discovery before device code

1. Exact instrument identity: CL-900i model/region, installed software and interface versions, and the Mindray-authorized support path. Do not post serial numbers or facility secrets publicly.
2. Mindray-authorized LIS/host-interface guide and written permission for the planned integration. Record its controlled document reference; do not commit proprietary manuals or real message captures to this repository.
3. Physical/transport setup (vendor-approved Ethernet or serial option), connection ownership/direction, protocol/framing, character set, port/session rules, and the supported query/push modes. Keep live hostnames, IPs, ports, certificates, and credentials out of Git/chat.
4. Authorized synthetic/test messages covering each supported result type, statuses, flags, repeats/corrections, QC/calibration, malformed/truncated frames, and ACK/retry behavior.
5. Existing LIS/worklist path, exact downstream system and its receiver contract, authoritative accession/patient association, result-release workflow, and named laboratory/clinical, biomedical, IT/interface, privacy/security, and operations owners.
6. Bangladesh facility approval, approved network flow and hosting/data-residency decision, privacy/security/legal/regulatory review, and an authorized engineering test environment.

Track these items in the [Phase 0 discovery worksheet](INTEGRATION_DISCOVERY.md), [receiver-contract worksheet](RECEIVER_CONTRACT.md), and [source-to-destination mapping worksheet](DEVICE_MAPPING_WORKSHEET.md). Validators for these worksheets are documentation checks only; they never enable connectivity.

## Implementation gates

1. **Discovery:** close the exact-device/interface and destination-contract questions above. Connectivity stays disabled.
2. **Offline parser/model:** add a typed lab-result domain model and protocol-specific parser only from the authorized guide. Use vendor-approved synthetic fixtures; add malformed-frame, duplicate, correction, status, unit, timestamp, and property-based tests. No socket or live patient data.
3. **Synthetic end-to-end:** run parser → reviewed mapping → policy/quarantine → durable outbox → local receiver with synthetic results only. Verify stable idempotency, lost-ACK handling, correction handling, audit, and recovery.
4. **Authorized engineering bench:** use the named CL-900i and synthetic/non-patient samples under Mindray and facility approval. Initially observe results only; verify no analyzer control/order traffic and no interference with the existing LIS.
5. **Receiver sandbox:** send only approved synthetic results to the named destination sandbox and verify application-level ACK, duplicate, correction, timeout, outage/recovery, and audit behavior.
6. **Controlled pilot decision:** proceed only after laboratory/clinical sign-off of assay mappings and result-release states, identity workflow, security/privacy and Bangladesh legal/regulatory reviews, operational support, rollback, and written site acceptance. A successful bench demo alone is not clinical validation or deployment authorization.

## Information needed to proceed

Please provide or confirm, using an approved channel and without patient data or credentials:

- whether an existing LIS is in the path, and whether MediHub should read from that LIS or connect directly to the analyzer;
- the CL-900i's installed software/interface version and the vendor-authorized LIS guide or its non-confidential protocol summary;
- whether the first scope is results-only (recommended) or also includes host queries/worklists;
- the actual EMS/EMR/LIS product and supported interface/contract; and what you mean by “EMS”;
- who owns the accession-to-patient association and who releases/validates results for chart delivery.

Until these inputs and approvals exist, keep using synthetic data. Do not connect this preview or its current simulator to the analyzer or a live clinical receiver.
