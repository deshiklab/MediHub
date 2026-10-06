# Synthetic management workbench

## Scope and hard boundary

The dashboard now includes a small management workbench for **in-memory simulator devices, synthetic mapping drafts, and one in-process test receiver**. It is intended to make the configuration flow tangible without guessing any physical device protocol or facility destination contract.

It is not a production management plane. It has no sign-in, user/tenant permissions, persistent registry, physical device discovery/control, live mapping activation, external network connector, endpoint URL field, or credential field. State resets when the dashboard process restarts. Do not expose it as a production service or enter patient, facility, vendor-restricted, or secret data.

## Use the preview

Open the local dashboard and scroll to **Try device, mapping, and API workflows**:

- **Devices:** register a generated `sim-device-NNN` record, enable/disable it, and emit an arbitrary simulator sample through the local synthetic pipeline. The device model, firmware, manufacturer, and adapter are fixed to MediHub's built-in simulator.
- **Data mapping:** view the versioned demo rule, add an in-memory synthetic rule, and preview an exact metric/unit match with a bounded value. Add synthetic golden test vectors with expected normalized codes, units, and values, then run pass/fail checks against the current mapping version. Results are tagged with that version and display as stale after a mapping edit/reset until tests are rerun. The source/normalized systems are fixed to `example.invalid`; unit system is fixed to UCUM. Preview and QA runs never activate a mapping or change ingestion.
- **Destination/API setup:** run a local delivery test to the in-process synthetic FHIR R4 sink. External FHIR R4 and HL7 v2 are shown as contract-required only; there is no arbitrary endpoint configuration or external network call.

The management API is under `/api/management/`:

| Endpoint | Function |
| --- | --- |
| `GET/POST /api/management/devices` | List or register a generated simulator record |
| `PATCH /api/management/devices/{device_id}` | Enable/disable a simulator record |
| `POST /api/management/devices/{device_id}/emit` | Emit one synthetic sample for an enabled simulator |
| `GET /api/management/mappings` | Read the active-in-this-process synthetic draft set; activation remains false |
| `POST /api/management/mappings/entries` | Add a bounded synthetic mapping draft |
| `POST /api/management/mappings/preview` | Apply exact match and transform to one synthetic scalar in memory |
| `POST /api/management/mappings/reset` | Reset the in-memory mapping set to the demo rule |
| `GET /api/management/mapping-tests` | List synthetic test vectors and the latest status for the current mapping version |
| `POST /api/management/mapping-tests/vectors` | Add a bounded synthetic input/expected-output test vector |
| `POST /api/management/mapping-tests/run` | Run all vectors against the current draft version and return per-vector pass/fail codes |
| `GET /api/management/destinations` | Show the single in-process receiver and disabled external protocols |
| `POST /api/management/destinations/test` | Send a synthetic sample only to the in-process test sink |

Malformed requests return stable error codes without echoing submitted values. The workbench allows only short code-like identifiers and numeric synthetic scalars; request validation details do not include raw body fields/values.

## Before a real device or receiver can be managed

A real device registry and adapter require the named manufacturer's protocol authorization, exact model/firmware, interface documentation, test vectors, and facility approval. A real destination requires the actual facility's FHIR CapabilityStatement/profiles/auth scopes/write behavior or its HL7 v2 profile/transport/ACK contract. Patient/encounter association, hosting/privacy review, and deployment authorization are separate gates.

A real management plane also requires authenticated OIDC login, least-privilege RBAC, site scoping, audited changes, durable configuration versioning, external secret management, safe connection tests, and security review. None of those controls is implemented by this local synthetic preview. Bangladesh Core guidance does not replace a facility's writable interface contract or DGHS production authorization.
