# Synthetic management workbench

## Scope and hard boundary

The dashboard now includes a small management workbench for **in-memory simulator devices, synthetic mapping drafts, and one in-process test receiver**. It is intended to make the configuration flow tangible without guessing any physical device protocol or facility destination contract.

It is not a production management plane. It has no sign-in, user/tenant permissions, persistent registry, physical device discovery/control, live mapping activation, external network connector, endpoint URL field, or credential field. State resets when the dashboard process restarts; only the latest 100 mapping revisions are retained in memory, with older snapshots discarded. Do not expose it as a production service or enter patient, facility, vendor-restricted, or secret data.

## Use the preview

The dashboard navigation opens four distinct page routes instead of scrolling one long page:

| Page | Route | Main content |
| --- | --- | --- |
| Operations | `/` (or `/operations`) | Health, aggregate pipeline metrics, recent events, outbox, holds, and audit activity |
| Devices | `/devices` | Simulator inventory and enable/disable/sample controls |
| Mappings | `/mappings` | Synthetic mapping drafts, previews, golden vectors, and revision history |
| API setup | `/api-setup` | In-process test receiver and delivery fault drill |

Each route selects one page view and loads only the data used by that page. Existing root fragment links to `#device-workbench`, `#mapping-workbench`, and `#destination-workbench` redirect to their matching page routes for compatibility.

- **Devices:** register a generated `sim-device-NNN` record, enable/disable it, and emit an arbitrary simulator sample through the local synthetic pipeline. The device model, firmware, manufacturer, and adapter are fixed to MediHub's built-in simulator.
- **Data mapping:** view the versioned demo rule, add an in-memory synthetic rule, and preview an exact metric/unit match with a bounded value. Inspect immutable mapping revisions, compare two snapshots, or restore an older snapshot as a new inactive revision; an old version is never overwritten. Add synthetic golden test vectors with expected normalized codes, units, and values, then run pass/fail checks against the current mapping version. Results are tagged with that version and display as stale after a mapping edit/reset/restore until tests are rerun. The source/normalized systems are fixed to `example.invalid`; unit system is fixed to UCUM. Preview and QA runs never activate a mapping or change ingestion.
- **Delivery triage:** inspect an allowlisted synthetic event/outbox/attempt timeline. An explicit replay is available only for terminal rejected/permanent-failure intents with remaining retry budget; it preserves the original event ID and attempt history and records a synthetic audit action. Transient failures stay on the normal retry schedule; acknowledged and non-synthetic records cannot be replayed here.
- **Destination/API setup:** run a local delivery test to the in-process synthetic FHIR R4 sink. A fault drill can inject one retryable failure, one terminal rejection, or an accepted event with its acknowledgement deliberately lost; the worker then retries with the stable event ID. A pending fault can be canceled. External FHIR R4 and HL7 v2 are shown as contract-required only; there is no arbitrary endpoint configuration or external network call.

The management API is under `/api/management/`:

| Endpoint | Function |
| --- | --- |
| `GET/POST /api/management/devices` | List or register a generated simulator record |
| `PATCH /api/management/devices/{device_id}` | Enable/disable a simulator record |
| `POST /api/management/devices/{device_id}/emit` | Emit one synthetic sample for an enabled simulator |
| `GET /api/management/mappings` | Read the active-in-this-process synthetic draft set; activation remains false |
| `POST /api/management/mappings/entries` | Add a bounded synthetic mapping draft |
| `POST /api/management/mappings/preview` | Apply exact match and transform to one synthetic scalar in memory |
| `POST /api/management/mappings/reset` | Create a new in-memory revision containing the demo rule |
| `GET /api/management/mappings/revisions` | List retained mapping revision summaries; history is capped at 100 |
| `GET /api/management/mappings/revisions/{version}` | Read one immutable synthetic mapping snapshot |
| `GET /api/management/mappings/revisions/{from_version}/compare/{to_version}` | Compare source signatures and transforms between snapshots |
| `POST /api/management/mappings/revisions/{version}/restore` | Create a new version from a retained snapshot; does not overwrite history or activate a mapping |
| `GET /api/management/mapping-tests` | List synthetic test vectors and the latest status for the current mapping version |
| `POST /api/management/mapping-tests/vectors` | Add a bounded synthetic input/expected-output test vector |
| `POST /api/management/mapping-tests/run` | Run all vectors against the current draft version and return per-vector pass/fail codes |
| `GET /api/management/deliveries/{event_id}` | Read safe synthetic event and delivery-attempt details; never returns raw payloads or patient context |
| `POST /api/management/deliveries/{event_id}/retry` | Replay one eligible terminal failure to the in-process test receiver with the original event ID |
| `GET /api/management/destinations` | Show the single in-process receiver and disabled external protocols |
| `GET /api/management/destinations/test-receiver/faults` | Read one-shot synthetic fault-injection status |
| `POST /api/management/destinations/test-receiver/faults` | Arm one retryable failure, terminal rejection, or lost ACK after receiver acceptance for the next synthetic send |
| `DELETE /api/management/destinations/test-receiver/faults` | Cancel a fault that has not yet been consumed |
| `POST /api/management/destinations/test` | Send a synthetic sample only to the in-process test sink |

Manual replay is limited to the fixed synthetic receiver, terminal failures, and records below the existing five-attempt worker limit; it preserves prior attempts and emits a metadata-only demo audit event. It does not provide general-purpose replay or waive facility validation, authorization, or review requirements.

Malformed requests return stable error codes without echoing submitted values. The workbench allows only short code-like identifiers and numeric synthetic scalars; request validation details do not include raw body fields/values.

## Before a real device or receiver can be managed

A real device registry and adapter require the named manufacturer's protocol authorization, exact model/firmware, interface documentation, test vectors, and facility approval. A real destination requires the actual facility's FHIR CapabilityStatement/profiles/auth scopes/write behavior or its HL7 v2 profile/transport/ACK contract. Patient/encounter association, hosting/privacy review, and deployment authorization are separate gates.

A real management plane also requires authenticated OIDC login, least-privilege RBAC, site scoping, audited changes, durable configuration versioning, external secret management, safe connection tests, and security review. None of those controls is implemented by this local synthetic preview. The ACK-loss drill demonstrates at-least-once redelivery against an in-memory receiver only; the selected destination must separately prove durable idempotency for its actual contract. Bangladesh Core guidance does not replace a facility's writable interface contract or DGHS production authorization.
