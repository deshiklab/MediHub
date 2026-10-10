# Mindray CL-900i integration plan

**Status: discovery only.** The CL-900i is now the proposed first analyzer, but its exact LIS interface, installed software/version, host configuration, facility, and receiving-system contract have not been supplied. MediHub remains synthetic-only: there is no CL-900i adapter, live listener, patient-result model, or real EMS/EMR sender. This document does not authorize a connection.

## What is publicly confirmed

Mindray describes the CL-900i as a fully automated chemiluminescence immunoassay (CLIA) analyzer using an enhanced ALP-AMPPD method, with throughput up to 180 tests/hour, 50 sample positions, and 15 reagent positions. See the [official CL-900i product page](https://www.mindray.com/en/products/laboratory-diagnostics/chemiluminescence-immunoassay/small-test-volume/cl-900i) and [official product brochure](https://www.mindray.com/content/dam/xpace/en/resources/brochure/cl-900i-product-brochure.pdf).

Those public product materials do **not** specify the exact host/LIS protocol and message profile, result-transfer direction, acknowledgement behavior, or the interface available on a particular unit/software release. A separate [Mindray India CLIA article](https://www.mindray.com/in/media-center/blog/understanding-clia-principles-applications/) says bidirectional LIS is available across CLIA analyzers and discusses the CL-900i, but does not identify this unit's protocol or host setup. Do not infer ASTM, HL7, TCP/IP, RS-232, or query/poll support from that general statement.

### Protocol and GitHub reconnaissance

An [unofficial mirror of a CLIA 900 service manual](https://pdfcoffee.com/manual-de-servicio-clia-900-pdf-free.html) claims that the CL-900i can use HL7 or ASTM E1394 over network or serial links. Treat this only as a lead: the copy is not a vendor-controlled contract, and its exact revision/region match to the installed unit is unknown. We still need the Mindray-authorized LIS/host-interface guide and written authorization.

A public GitHub search found generic ASTM libraries but no verified CL-900i driver: [`astmio`](https://github.com/PrasoonPratham/astmio) is an MIT-licensed, pre-release Python E1381/E1394 project; [`python-astm`](https://github.com/kxepal/python-astm) is another generic implementation with no clear SPDX license in repository metadata; [`Mindray-Listener`](https://github.com/coudjo/Mindray-Listener) describes a different Mindray binary protocol and explicitly says it is not ASTM or HL7. None is evidence of CL-900i compatibility, so no third-party implementation has been adopted.

### Review of the user-supplied general integration guide

Only the guide text pasted in chat could be reviewed; the PDF attachment itself was not accessible in the workspace. That text describes a general analyzer-to-EMR architecture and names Mindray BC-6000 and BS-430 models plus the SNIBE MAGLUMI 800—not the Mindray CL-900i. Its general ASTM/HL7 statements, example port, static-IP/serial-to-TCP suggestions, and device setup steps do not verify the CL-900i's installed protocol or authorize configuration changes. The bidirectional/worklist example is outside the requested results-only scope; even result auto-send must be confirmed for the exact unit and approved host mode. The guide also lacks a controlled CL-900i document revision, installed interface version, exact message profile/framing, ACK/retry/correction semantics, and a receiver contract. Treat it as background only; do not use it to configure the analyzer or infer patient matching from a patient ID alone.

### Review of the supplied CL-900i protocol and site-prep claims

The supplied citations are mixed. An unofficial [CL-900i series service-manual mirror](https://pdfcoffee.com/manual-de-servicio-clia-900-pdf-free.html) has an LIS chapter that describes ASTM/HL7 over network or serial and distinguishes unidirectional result transmission from bidirectional communication that can receive sample-programming instructions. This is a useful lead: ask Mindray whether the exact installed software supports an approved unidirectional, results-only mode. It is not an authorized interface contract, and any required protocol ACK must be distinguished from a clinical verification or worklist command. The cited [Mindray Patient Data Share guide](https://www.mindray.com/content/dam/xpace/en_us/service-and-support/training-and-education/resource--library/technical--documents/operators-manuals-1/H-0010-20-43061-2-Mindray-Patient-Data-Share-Protocol-Programmers-Guide-v14_2-03-2020.pdf) concerns a separate patient-data-sharing interface, while the cited BS-230 and Counter-31 documents are for other analyzer models. Treat QRY^R02/QRY^A19, PMT-timing behavior, and any message-field claims as unverified for the installed CL-900i until an authorized CL-900i profile confirms them; queries/worklist exchange remain out of initial scope.

The site-preparation values are a separate installation concern. Mindray's [2022 CL-900i brochure](https://www.mindray.com/content/dam/xpace/en/resources/brochure/cl-900i-product-brochure.pdf) lists 145 kg and 1000 VA, while an [older India-region brochure](https://www.mindray.com/content/dam/xpace/en_in/resources/brochures/cl-900i-product-brochure-en_in.pdf) lists 132 kg and 500 VA. This illustrates why the exact unit/region and current authorized installation guide must control physical and electrical requirements; do not treat the supplied clearance, UPS, fluidic, or waste-routing figures as approved site specifications.

**Provisional development choice:** MediHub now has an offline, bounded ASTM E1394 record-stream parser scaffold using synthetic tests only. It does not implement E1381 framing/session control, HL7 v2, analyzer transport, CL-900i field mapping, or delivery. ASTM is a candidate—not a claim about the installed analyzer. If the authorized guide specifies HL7 instead, implement that exact profile rather than forcing ASTM.

**Review-screen prototype:** the Next.js `/lab-review` page shows fabricated pending/unverified rows in English and Bengali. It has no patient context, ingestion, persistence, order/patient association, verification/finalization/release controls, or destination delivery; its “viewed” acknowledgement is only in browser memory. It demonstrates a safety boundary, not a usable clinical review workflow. Bengali copy still needs native-speaker review.

## User-confirmed workflow and proposed safe data path

The requested topology is for MediHub to read results directly from the CL-900i and make them available to lab technicians in the facility's EMS/EMR/HMS for verification. The initial scope is results-only: MediHub must not send worklists, orders, assay controls, or analyzer configuration changes. This records the desired workflow; it does not confirm that the unit's installed LIS mode supports it.

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

The requested source is the analyzer itself. Before opening a direct connection, the facility and Mindray must confirm the approved host mode, whether the CL-900i is already connected to an LIS, and whether it permits another host. Do not interrupt an existing LIS or create a competing connection. If direct access is not permitted, the fallback is an approved read-only export/API from the existing LIS.

“Pull” needs a device-specific decision: completed results might be pushed by the analyzer, requested by an authorized host, or exposed through the LIS. Even when the analyzer initiates a result upload, MediHub can receive it without sending orders. Use the least-permissive vendor-supported **results-only** mode. Do not download worklists, send orders, change analyzer configuration, start/stop assays, or issue other control commands in the first integration.

## Data and workflow requirements

The current `ObservationEvent` accepts only a numeric scalar, and the current FHIR R4 mapper and receiver are synthetic-only. A laboratory integration needs a separately reviewed result model before a live parser is written. The exact fields must come from the authorized interface guide and facility workflow; at minimum, assess:

- analyzer identity/model/software version and source message/result identifiers;
- specimen/accession and order identifiers, sample type, assay/test code, raw result value/text, original unit, and result timestamp;
- result lifecycle (for example, preliminary, verified/final, corrected, repeated, or cancelled), analyzer flags, dilution/repeat details, and any reference/interpretation fields actually supplied;
- source code/unit and any proposed normalized code/unit, with a reviewed, versioned mapping and a traceable reason for every conversion.

Preserve the source result, code, unit, status, and timing. Do not guess an assay mapping, convert units, round values, infer a reference range, or turn an analyzer flag into a clinical interpretation. Unknown or inconsistent codes/units/statuses, duplicate/correction ambiguity, and missing association data must be quarantined for authorized review—not silently forwarded. Define separately how QC, calibration, maintenance, and non-patient records are recognized so they cannot be mistaken for patient results.

Associate a result using the facility-authoritative accession/order and patient-context workflow. Do not match by patient name, bed/location, timing, or analyzer/sample position alone. The requested technician review must remain explicit: deliver only as draft/preliminary/unverified if the receiver supports that workflow; otherwise stage the imported result for an authorized lab technician before any EMR submission. MediHub must never mark a result verified/final or auto-release it. An analyzer transmission acknowledgement is not clinical verification or EMR acceptance.

## Destination contract

The user uses EMS/EMR/HMS to mean the facility's Electronic Medical Record / Medical Record Management / Hospital Management Software. The exact vendor, product/version, and API are still unknown. Confirm whether the actual receiving endpoint is that system, an LIS, or an interface engine, and whether it accepts a pending/unverified result for lab-technician review. Obtain the approved interface contract before choosing a sender:

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
2. **Offline parser/model:** a generic ASTM E1394 record-stream parser scaffold now exists at `src/medihub/adapters/devices/astm.py`. It uses synthetic tests, preserves opaque field values, applies byte/record/field bounds, hides record contents from `repr`, and does not interpret results. It does not implement E1381 framing/session control, sockets, serial I/O, a CL-900i profile, or HL7. After the authorized guide arrives, add the exact supported transport/profile and a typed lab-result model; use only vendor-approved synthetic fixtures.
3. **Synthetic end-to-end:** run parser → reviewed mapping → pending-review policy/quarantine → durable outbox → local receiver with synthetic results only. Verify stable idempotency, lost-ACK handling, correction handling, audit, and recovery. The technician-review step must not be bypassed or converted into automatic finalization.
4. **Authorized engineering bench:** use the named CL-900i and synthetic/non-patient samples under Mindray and facility approval. Initially observe results only; verify no analyzer control/order traffic and no interference with the existing LIS.
5. **Receiver sandbox:** send only approved synthetic results to the named destination sandbox and verify application-level ACK, duplicate, correction, timeout, outage/recovery, and audit behavior.
6. **Controlled pilot decision:** proceed only after laboratory/clinical sign-off of assay mappings and result-release states, identity workflow, security/privacy and Bangladesh legal/regulatory reviews, operational support, rollback, and written site acceptance. A successful bench demo alone is not clinical validation or deployment authorization.

## Information needed to proceed

The initial business scope is now **direct analyzer result intake, results-only, followed by lab-technician verification in the facility system**. To implement it, provide or confirm through an approved channel, without patient data or credentials:

- the CL-900i's installed software/interface version and the vendor-authorized LIS guide or its non-confidential protocol summary;
- whether the CL-900i already has an LIS host connection and whether Mindray/facility permit MediHub as the direct host; if not, name the approved read-only LIS feed;
- the exact EMS/EMR/HMS product/version and supported interface contract, including whether it can accept a draft/pending/unverified lab result for technician review;
- the facility-authoritative specimen accession/order and patient association workflow, plus who can resolve mismatches;
- an approved synthetic message set and engineering test environment, with controlled references rather than real captures in Git.

Until these inputs and approvals exist, keep using synthetic data. Do not connect this preview or its current simulator to the analyzer or a live clinical receiver.
