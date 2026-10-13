# Phase 0 public receiver discovery: Bangladesh

**Reviewed:** 2026-10-14  
**Purpose:** collect public discovery leads for a future receiving-system discussion. This is not a facility inventory, installation survey, authorization, integration specification, or conformance assessment.

## Conclusion

Public material identifies possible Bangladesh-relevant systems and an official health-information-exchange pathway, but it does **not** identify MediHub's first facility, installed receiver product/version, or authorized receiver contract. No candidate below is selected as the FHIR or HL7 target. Public marketing claims and open-source repositories are discovery leads only; they cannot replace the facility's controlled contract and approvals.

A notable version warning is that the public DGHS SHR technical material reviewed describes a FHIR STU3-based contract and says SHR is not itself a FHIR resource server. That must be reconciled with the current, authorized DGHS interface documentation before treating SHR as relevant to MediHub's generic FHIR R4 Observation path. The published page may be historical; it is not evidence of the current contract.

## Public leads and evidence limits

| Lead | What the public source says | What it does **not** establish | Phase 0 disposition |
| --- | --- | --- | --- |
| DGHS Shared Health Record (SHR) / HIE | DGHS documentation describes an API path for authorized facility/community EMR systems and an enrolment/authorization process. A technical-support page describes FHIR STU3 documents as the contract format and says SHR is not a FHIR resource server. ([DGHS documentation introduction](https://en.info.shr.dghs.gov.bd/documentation_introduction/), [SHR technical support](https://en.info.shr.dghs.gov.bd/technical-support/shared-health-record/), [clinical data exchange notes](https://en.info.shr.dghs.gov.bd/clinical-data-exchange/)) | Current interface release, approved use case, current payload/profile, Observation or result-write behavior, authorization scope, ACK/idempotency semantics, site-specific approval, and availability of an authorized synthetic test environment. The public documentation does not establish a general-purpose FHIR R4 REST receiver. | Keep as a **separate possible national HIE pathway**, not as the facility's EMR/EMS. Obtain the current controlled technical package from the authorized DGHS channel; do not infer from older public STU3 material. |
| E-Medical Software Ltd. (EMSL) | Its public site advertises HIS/EMR/LIS products and HL7/FHIR interface-development services in Bangladesh. ([EMSL public site](https://emslbd.com/)) | Which product is installed at the target site, exact version/profile, results-only behavior, controlled interface documents, ACK/retry/idempotency rules, or any facility authorization. | Vendor-discovery lead only. Request the exact installed product/version and controlled interface contract through the facility/vendor process. |
| Danphe EMR public GitHub repository | The repository describes a hospital EMR/HMIS and its README self-reports deployments across several countries including Bangladesh, along with lab-machine integrations. ([repository](https://github.com/hospital-management-system-emr/hospital-management-system-emr-opensource)) | Independent confirmation of those deployments, use at a MediHub target facility, the exact product release, analyzer/receiver protocol profile, or a writable results-only contract. | Low-confidence ecosystem lead only. Do not infer local installed base or compatibility. The public README contains demo-login material; it was not used or copied. |
| Bahmni Hub-and-Spoke / `bdshrclient` | Public source contains an OpenMRS `bdshrclient` module described as a client for central SHR; its visible history is old (latest listed commit January 2022). The repository is AGPL-3.0. ([repository](https://github.com/Bahmni/Bahmni-HnS), [`bdshrclient` module](https://github.com/Bahmni/Bahmni-HnS/tree/master/openmrs-module-bdshrclient)) | Whether this implementation is current, supported, deployed at the target site, or compatible with the current DGHS contract. It is not a present-day receiver specification. | Historical interoperability reference only. Do not adopt or port code without current security, maintenance, and license review. |
| OpenMRS FHIR2 module | Public GitHub source describes an OpenMRS FHIR module initially using R4 and has R3/R4 provider packages; its repository was active in October 2026. ([repository](https://github.com/openmrs/openmrs-module-fhir2)) | That OpenMRS is installed at the target facility, how a local deployment is configured, or which profiles and workflow it exposes. | Technical comparison/reference only, not a Bangladesh installation or receiver contract. No dependency or code has been adopted. |

## Questions for the facility and authorized receiver owner

Before creating a receiver-specific fixture, obtain through an approved channel:

1. The facility name and **exact installed receiving product, release, and interface-engine role** (if an interface engine is the actual receiver).
2. The controlled contract/profile document ID and revision, plus the exact FHIR release and supported resources/profiles, or HL7 version, message profile, transport/framing, and ACK profile.
3. The receiver's patient/accession-association policy and a documented **pending, technician-reviewed results-only** workflow. No order/worklist download, analyzer control, automatic finalization, or release is in the initial scope.
4. Duplicate/idempotency retention, retry and timeout semantics, correction/replacement behavior, request limits, and receiver-restart behavior.
5. Written vendor/facility authorization and an approved synthetic test environment/fixture, with its owner and approval reference.
6. The responsible clinical, biomedical, interface/IT, privacy/security, and operational owners, plus Bangladesh hosting/data-residency and legal/regulatory review paths.

Record only opaque, non-secret evidence references in the worksheet. Do not provide credentials, access tokens, patient data, or live endpoint/host details in this repository or chat.

## MediHub decision until evidence arrives

- The FHIR runner remains a **local generic FHIR R4 fixture check only**; it does not validate DGHS SHR, EMSL, Danphe, OpenMRS, or any other receiver.
- Do not label any public lead as the installed site system or claim Bangladesh Core/facility-contract conformance.
- HL7 stays `contract_required`; no HL7 runner or network path is enabled.
- Once an exact controlled contract and authorized synthetic fixture are supplied, add a separate versioned offline target-profile test. A pass must remain a local fixture result; site approval and any live integration are separate gates.

Continue the existing [Phase 0 integration-discovery worksheet](INTEGRATION_DISCOVERY.md) and [receiver-contract preflight](RECEIVER_CONTRACT.md) for evidence collection.
