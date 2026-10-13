# Bangladesh device inventory survey worksheet

**Purpose:** turn Bangladesh market-discovery leads into a facility-evidence-based shortlist for future MediHub work.
**Status:** blank template; no facility inventory has been supplied or verified.
**Boundary:** this worksheet does not configure a device, establish compatibility, authorize access, or permit connectivity.

## Use and handling

- Complete one row for each exact manufacturer/model **and** materially different firmware/software/interface combination at a participating facility. Keep the respondent's source record in that facility's approved system; put only its opaque reference here.
- Ask the facility's biomedical/clinical-engineering or laboratory owner to distinguish installed equipment from equipment that is planned, previously used, serviced, quoted, or merely listed by a seller.
- Use aggregate counts or count bands only when the facility authorizes recording them. Do not record device serial numbers, asset tags, patient information, raw messages, hostnames, IP addresses, ports, network maps, credentials, personal contact details, restricted manual contents, or commercial terms in this repository or chat.
- Do not probe a device or network. Interface facts must come from controlled documentation or an authorized party. A survey response is not an interface test or an approval.
- Keep completed facility/vendor responses in the facility's approved records. This checked-in file is only the blank form and method.

## One-row survey form

Copy the table into an approved local worksheet. Use `unknown` rather than guessing. Evidence references should be short opaque document/ticket IDs, not URLs, paths, or document contents.

| Field | Response guidance |
| --- | --- |
| `survey_record_ref` | Opaque reference for this survey row. |
| `site_ref` | Facility-controlled opaque site code; do not put a facility or person's name here. |
| `evidence_class` | One of the evidence classes below; retain the source record in the facility system. |
| `survey_date` | Date evidence was reviewed, not a device event time. |
| `device_family` | Hematology, clinical chemistry, immunoassay, urinalysis, electrolyte, coagulation, HbA1c, blood gas, POCT, or other. |
| `manufacturer` / `exact_model` | Transcribe from the authorized inventory/nameplate record. Do not infer from a family name or product listing. |
| `firmware_software_scope` | Exact version if verified; otherwise `unknown`. Record separate rows if interfaces differ by version. |
| `lab_section_ref` | Optional opaque section reference (for example, chemistry bench); no patient/worklist details. |
| `installed_count_or_band` | Facility-authorized aggregate count, e.g. `1`, `2-5`, `6-20`, `20+`, or `unknown`. Do not include serials. |
| `usage_band` | Aggregate workload band from a facility owner, if approved; no patient-level or result data. Otherwise `unknown`. |
| `current_receiver_product_version` | Exact LIS/HIS/EMR or interface-engine product/version if disclosed and approved; do not include a host or endpoint. |
| `current_interface_state` | `unknown`, `not_connected`, `connected_reported`, or `documented`; state whether this is self-reported or documented. |
| `device_transport_protocol_version` | Only the documented transport/protocol/version; otherwise `unconfirmed`. Do not infer from another model or product family. |
| `vendor_gateway_or_interface_ref` | Opaque document/contract reference for a manufacturer gateway or approved interface, if one exists. |
| `results_only_supported` | `yes`, `no`, or `unknown`, based on controlled documentation/authorized owner—not a seller claim. |
| `technician_review_workflow_ref` | Opaque reference to the approved pending/review workflow, if documented. No automatic finalization/release is in the initial scope. |
| `interface_document_ref_revision` | Controlled document ID and revision; do not copy the manual or message sample into the survey or Git. |
| `vendor_authorization_status_ref` | `pending`, `approved`, or `not_applicable` only when explicitly decided; pair with an opaque evidence reference. |
| `facility_authorization_status_ref` | `pending`, `approved`, or `not_applicable` only when explicitly decided; pair with an opaque evidence reference. |
| `local_service_support_ref` | Opaque reference to an authorized local service/support record, or `unknown`. |
| `synthetic_test_environment_ref` | Opaque reference only if a facility/vendor-approved synthetic environment exists. Do not test an unapproved endpoint. |
| `open_questions` | Brief non-sensitive question codes or a pointer to the controlled record; no free-text secrets or restricted information. |

## Evidence classes

Use exactly one primary class per factual claim; a row can cite several separate claims, each with its own reference.

| Class | Meaning | What it can support |
| --- | --- | --- |
| `facility_inventory_verified` | An authorized site owner has checked the row against the current controlled inventory/engineering record. | Site-specific installed-model counts, subject to the scope and date of that record. |
| `facility_self_reported` | A named role at the site provided the information, but the inventory/document was not independently inspected. | A lead for follow-up only; retain its reported status. |
| `vendor_or_distributor_claim` | A vendor/distributor supplied information or a public product listing was reviewed. | Product availability or a vendor claim only; not site installation, popularity, or compatibility. |
| `public_facility_claim` | A facility's own public material describes a device installation. | A site-specific self-reported lead only; not independent confirmation or national prevalence. |
| `unknown` | The evidence source or fact is not established. | Nothing beyond identifying an open question. |

Never upgrade an evidence class merely because the same claim appears on several reseller pages. A seller listing, public GitHub repository, or vendor capability statement does not confirm a target facility's installed software or receiver contract.

## How to prioritize after the survey

1. **Filter to the target facilities and the date range first.** Do not present a convenience sample as a Bangladesh-wide prevalence estimate.
2. **Rank confirmed installation separately from market availability.** Summarize facility-verified counts and self-reported counts in separate columns; keep seller/vendor/public-facility claims in a separate discovery-lead list.
3. **Use workload bands only as supporting evidence.** Aggregate laboratory workload can help estimate value, but it must not include patient identifiers or results.
4. **Assess interface readiness as a separate gate:** exact model/version, controlled interface document, documented transport/profile, results-only behavior, receiver product/version and contract, written vendor/facility authorization, and approved synthetic test path.
5. **Consider local service coverage and implementation effort.** A more available device is not the right first adapter if it lacks authorization, controlled documentation, or a supported results-only path.
6. **Record the decision and dissenting evidence.** A prioritization score is a discovery aid only; it cannot override a missing safety, authorization, or receiver-contract gate.

The current candidate library intentionally marks products as `discovery_only`. No score or survey count in this worksheet changes that status, adds a driver, or enables a connection. Exact interface documentation, vendor/facility authorization, controlled receiver contract, synthetic validation, and separate site approval remain required before any device-specific implementation or live use.
