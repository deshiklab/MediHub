# CL-900i results-only interface discovery request

Use this as a starting point for a written request to Mindray and the facility's biomedical/IT-interface owners. It is a discovery aid—not authorization to connect, configure, or change the analyzer. Share unit-specific identifiers, proprietary documents, network details, and support records only through the facility/vendor-approved channel. Do not place credentials, patient data, or live message captures in Git or chat.

## Copy/paste request to Mindray

**Subject:** CL-900i host/LIS interface confirmation for results-only integration

Hello,

We are assessing a proposed MediHub integration with a Mindray CL-900i at a Bangladesh facility. The requested initial scope is strictly to receive completed analyzer results for lab-technician review in the facility's approved EMS/EMR/HMS. It must not download test orders or worklists, send analyzer-control commands, or automatically mark results verified/final or release them.

Please confirm the following for this exact installed unit/software version. If the information is unit-specific, we can provide the serial number directly in an approved support ticket rather than in public correspondence.

1. **Controlled interface reference:** What are the exact CL-900i software and LIS/host-interface versions? Please provide the current Mindray-authorized host/LIS interface guide (document ID, revision, date, and applicable market) or an authorized non-confidential protocol summary.
2. **Supported results-only direction:** Can the analyzer send completed results to an authorized host without accepting orders/worklists or control traffic? Does it support a host query for already-completed results only? If so, document precisely what the query returns and confirm it is not a test-order/worklist download. Do not infer behavior from a generic HL7 or ASTM example.
3. **Existing host connection and topology:** Is another host permitted while the facility's current LIS connection is active? What is the vendor-approved topology if the current LIS already owns the interface? We will not create a competing connection or interrupt the existing LIS.
4. **HL7, if supported:** State the exact HL7 version and CL-900i message profile, including push/query trigger events, complete segment/field definitions, delimiters/encoding, transport/framing, ACK/NAK meaning, timeouts/retries, duplicate behavior, and correction/repeat/cancel behavior. If QRY^R02/ORF^R04 is supported, specify whether it requests stored observations or orders and provide the authorized query/response profile. Define the device's OBX-11 / OBR-25 meanings in this implementation and how those statuses relate to technician verification; identify every allowed ORC order-control code.
5. **ASTM, if supported:** State the exact record and transport/framing revisions (for example, E1394/LIS02 and E1381/LIS01 variants), whether records are framed or raw, and the full session-control, frame/checksum, sequencing, timeout/retransmission, ACK/NAK, and disconnect behavior.
6. **Result dictionary:** Provide the versioned assay/test-code, unit, result-status, abnormal-flag, dilution/repeat, correction, and QC/calibration/non-patient record dictionaries applicable to this software version. Identify which fields must be preserved verbatim and which are vendor-defined.
7. **Approved test assets:** Is there an authorized simulator, engineering bench, or test mode? Please provide synthetic/non-patient examples that cover ordinary results, flags, repeats/corrections, QC/calibration, malformed input, and transport failures, together with expected acknowledgements. No patient-identifiable data is requested.
8. **Site requirements:** Which current authorized installation/interface guide governs the approved physical and network setup for this unit and market? What facility/Mindray approval and change-control steps are required before any engineering connection?

A results-only mode is a requirement for this initial assessment. If it is unavailable, please state that explicitly; we will not enable a bidirectional order/worklist or analyzer-control mode as a workaround.

Thank you.

## Facility and receiving-system confirmations

Obtain these from the facility's laboratory owner, biomedical engineering, IT/interface team, privacy/security lead, and the receiving-system owner:

- Confirm whether the CL-900i is already connected to an LIS and whether Mindray and the facility explicitly approve MediHub as an additional direct host. If not, identify an approved read-only feed from the existing LIS.
- Name the exact receiver product/version and approved interface profile. Confirm the receiver can accept an unverified/pending result for a named lab technician to review, and describe where that result remains held until the technician's action.
- Document the meaning of transport and application acknowledgements, stable duplicate/idempotency key and retention, retries/timeouts, corrections/replacements, receiver restart behavior, request limits, downtime handling, and sandbox test procedure in `docs/RECEIVER_CONTRACT.md` and the local receiver worksheet.
- Confirm the authoritative accession/order and patient-association source, mismatch/quarantine owner, and clinical sign-off path. Do not match patients by name, bed, time, or sample position alone.
- Approve the network flow, hosting/data-residency and cross-border decision, Bangladesh privacy/legal/regulatory review path, synthetic test environment, operating owners, rollback, and change-control process before any live pilot consideration.

## Return checklist for MediHub discovery

Use the approved local profile and mapping/receiver worksheets; store only opaque controlled-document or ticket references in Git. Keep completed facility/vendor details local and private. Do not paste proprietary message captures, real endpoints, secrets, serial numbers, or patient data here.

- [ ] Exact instrument, software, and interface versions confirmed.
- [ ] Authorized Mindray interface guide/profile received and applicability verified.
- [ ] Results-only push or read-only completed-result query explicitly documented.
- [ ] Existing LIS ownership and direct-host authorization decided.
- [ ] Exact receiver and pending/unverified technician-review workflow confirmed.
- [ ] Synthetic test messages/assets and expected acknowledgements approved.
- [ ] Source-to-canonical-to-destination mappings reviewed; unknown codes remain unresolved.
- [ ] Facility hosting, privacy/security, Bangladesh legal/regulatory, and network-flow gates assigned and documented.
- [ ] Synthetic acceptance plan and accountable sign-off owners named.

A complete checklist is still discovery documentation—not production authorization. MediHub remains synthetic-only until all gates are reviewed and a separate pilot decision is approved.
