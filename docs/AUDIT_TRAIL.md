# Synthetic lifecycle audit trail

## Scope and safety boundary

MediHub now records a privacy-minimized audit row in the same database transaction as each new event/outbox/hold decision and each outbox attempt transition. The audit schema stores only site/actor identifiers, a controlled action, a resource type and opaque resource ID, timestamps, a correlation ID, and an optional safe reason code. It never copies observation payloads, patient references, receiver response text, or exception messages.

The current actor values are system labels (`system:ingestion` and `system:outbox-worker`), not authenticated human identities. This is an engineering lifecycle ledger for the synthetic pipeline; it is **not** an authenticated operator audit system, a tamper-evident log, a regulatory-compliance claim, or a production access-control mechanism. No live connector, patient review action, or PHI-read/write workflow is enabled by this work.

## Recorded lifecycle

- `event_stored`: a new event and audit record committed together.
- `delivery_intent_created`: an eligible outbox intent committed with the event.
- `route_held`: a policy hold committed with the event; only the stable safe reason code is attached.
- `delivery_attempt_started`: the outbox claim and attempt record committed.
- `delivery_lease_expired`: an expired attempt was detected during lease recovery.
- `delivery_acknowledged`, `delivery_rejected`, `delivery_retry_scheduled`, `delivery_retry_exhausted`, or `delivery_permanent_failure`: the final attempt outcome and audit record committed together.

Duplicate event IDs with identical content remain idempotent no-ops and do not create additional ingestion audit rows. Conflicting content still fails closed. `SqlAlchemyEventStore.recent_audit_events()` offers a bounded site-filtered metadata query; its site filter is not authorization and must be placed behind an authenticated, site-scoped boundary before any production use.

## Storage and retention

Migration `0004_audit_event` creates an independent audit table without a foreign key to event payloads, so deleting an event does not silently erase its audit history. The persistent development database therefore needs an explicit retention policy before it is used for sensitive or production data. The in-memory dashboard is an exception: it deliberately prunes audit rows together with expired synthetic event history to remain bounded.

The persistent audit-store API exposes no update/delete method, but the in-memory demo intentionally prunes its bounded synthetic history and a database administrator can still modify the database. Production use would require a reviewed retention and export policy, strong access controls, encrypted storage/backups, monitoring, and tamper-evidence or off-host archival as appropriate. Do not put names, patient IDs, raw messages, credentials, endpoint details, or free-text exception content in actor/resource/correlation fields.
