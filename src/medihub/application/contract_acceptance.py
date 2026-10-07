"""Offline, contract-driven acceptance scenarios against a local synthetic model."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from medihub.application.receiver_contract import (
    DuplicateOutcome,
    IdempotencyRetention,
    ReceiverContract,
    ReceiverContractFileResult,
)

_SYNTHETIC_EVENT_KEY = "synthetic-contract-test-event-001"
MAX_REQUIRED_IDEMPOTENCY_HORIZON_SECONDS = 315_360_000


@dataclass(frozen=True, slots=True)
class ContractAcceptanceCheck:
    """One synthetic scenario result with no receiver or event identifiers."""

    check_id: str
    passed: bool
    result_code: str


@dataclass(frozen=True, slots=True)
class ContractAcceptanceSummary:
    """Aggregate-only results; the modeled receiver is never a real destination."""

    status: Literal["passed", "failed", "blocked"]
    checks: tuple[ContractAcceptanceCheck, ...]
    blockers: tuple[str, ...]
    errors: tuple[dict[str, str], ...]
    required_idempotency_horizon_seconds: int | None
    network_enabled: Literal[False] = False
    connectivity_enabled: Literal[False] = False
    real_receiver_tested: Literal[False] = False
    test_target: Literal["local_synthetic_contract_model"] = "local_synthetic_contract_model"

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "checks": [
                {
                    "check_id": check.check_id,
                    "passed": check.passed,
                    "result_code": check.result_code,
                }
                for check in self.checks
            ],
            "passed_checks": sum(check.passed for check in self.checks),
            "failed_checks": sum(not check.passed for check in self.checks),
            "blockers": list(self.blockers),
            "errors": list(self.errors),
            "required_idempotency_horizon_seconds": self.required_idempotency_horizon_seconds,
            "network_enabled": self.network_enabled,
            "connectivity_enabled": self.connectivity_enabled,
            "real_receiver_tested": self.real_receiver_tested,
            "test_target": self.test_target,
        }

    @property
    def exit_code(self) -> int:
        if self.status == "passed":
            return 0
        if self.status == "failed":
            return 1
        return 2


@dataclass(frozen=True, slots=True)
class _ReceiverReply:
    acknowledged: bool
    duplicate: bool
    acknowledgement_code: str | None


class _LocalSyntheticContractReceiver:
    """File-backed model of the documented policy; no transport or event payload."""

    def __init__(self, database_path: Path, contract: ReceiverContract) -> None:
        self._contract = contract
        self._connection = sqlite3.connect(database_path)
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS synthetic_contract_inbox (
                receipt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                synthetic_key TEXT NOT NULL,
                acknowledgement_code TEXT NOT NULL,
                accepted_at_seconds INTEGER NOT NULL
            )
            """
        )
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def deliver(self, synthetic_key: str, *, at_seconds: int) -> _ReceiverReply:
        """Model one request using only the contract's documented response policy."""

        idempotency = self._contract.idempotency
        if idempotency.retention is IdempotencyRetention.BOUNDED:
            retention_seconds = idempotency.retention_seconds
            if retention_seconds is None:
                return _ReceiverReply(False, False, None)
            self._connection.execute(
                """
                DELETE FROM synthetic_contract_inbox
                WHERE accepted_at_seconds + ? <= ?
                """,
                (retention_seconds, at_seconds),
            )
            self._connection.commit()

        cursor = self._connection.execute(
            """
            SELECT acknowledgement_code
            FROM synthetic_contract_inbox
            WHERE synthetic_key = ?
            ORDER BY receipt_id
            LIMIT 1
            """,
            (synthetic_key,),
        )
        existing = cursor.fetchone()
        cursor.close()
        if existing is not None:
            if idempotency.duplicate_outcome in {
                DuplicateOutcome.SAME_ACKNOWLEDGEMENT,
                DuplicateOutcome.ACKNOWLEDGED_AS_DUPLICATE,
            }:
                return _ReceiverReply(True, True, str(existing[0]))
            if idempotency.duplicate_outcome is DuplicateOutcome.CREATES_DUPLICATE:
                return self._record_receipt(synthetic_key, at_seconds, duplicate=True)
            return _ReceiverReply(False, True, None)

        return self._record_receipt(synthetic_key, at_seconds, duplicate=False)

    def receipt_count(self) -> int:
        cursor = self._connection.execute("SELECT COUNT(*) FROM synthetic_contract_inbox")
        row = cursor.fetchone()
        cursor.close()
        return int(row[0]) if row else 0

    def _record_receipt(
        self,
        synthetic_key: str,
        at_seconds: int,
        *,
        duplicate: bool,
    ) -> _ReceiverReply:
        codes = self._contract.acknowledgement.success_codes
        if not codes:
            return _ReceiverReply(False, duplicate, None)
        acknowledgement_code = codes[0]
        self._connection.execute(
            """
            INSERT INTO synthetic_contract_inbox (
                synthetic_key, acknowledgement_code, accepted_at_seconds
            ) VALUES (?, ?, ?)
            """,
            (synthetic_key, acknowledgement_code, at_seconds),
        )
        self._connection.commit()
        return _ReceiverReply(True, duplicate, acknowledgement_code)


def run_contract_acceptance(
    file_result: ReceiverContractFileResult,
    *,
    required_idempotency_horizon_seconds: int | None = None,
) -> ContractAcceptanceSummary:
    """Run deterministic local scenarios; never contact the receiver named in TOML."""

    report = file_result.report
    contract = file_result.contract
    if not report.schema_valid or report.readiness != "contract_documented" or contract is None:
        return ContractAcceptanceSummary(
            status="blocked",
            checks=(),
            blockers=report.blockers,
            errors=report.errors,
            required_idempotency_horizon_seconds=required_idempotency_horizon_seconds,
        )
    if contract.interface_version is None:
        return _blocked("receiver_interface_version_missing")
    if required_idempotency_horizon_seconds is not None and not (
        1 <= required_idempotency_horizon_seconds <= MAX_REQUIRED_IDEMPOTENCY_HORIZON_SECONDS
    ):
        return _blocked("required_idempotency_horizon_invalid")
    if (
        contract.idempotency.retention is IdempotencyRetention.BOUNDED
        and required_idempotency_horizon_seconds is None
    ):
        return _blocked("required_idempotency_horizon_missing")

    try:
        checks = _run_scenarios(contract, required_idempotency_horizon_seconds)
    except (OSError, sqlite3.Error):
        checks = (
            ContractAcceptanceCheck(
                check_id="local_inbox_storage",
                passed=False,
                result_code="local_contract_model_storage_failed",
            ),
        )

    status: Literal["passed", "failed"] = (
        "passed" if all(check.passed for check in checks) else "failed"
    )
    return ContractAcceptanceSummary(
        status=status,
        checks=checks,
        blockers=(),
        errors=(),
        required_idempotency_horizon_seconds=required_idempotency_horizon_seconds,
    )


def _run_scenarios(
    contract: ReceiverContract,
    required_horizon_seconds: int | None,
) -> tuple[ContractAcceptanceCheck, ...]:
    checks: list[ContractAcceptanceCheck] = []
    success_codes = contract.acknowledgement.success_codes
    retryable_codes = contract.failure_handling.retryable_codes
    permanent_codes = contract.failure_handling.permanent_codes

    with TemporaryDirectory(prefix="medihub-contract-acceptance-") as temporary_directory:
        root = Path(temporary_directory)

        receiver = _LocalSyntheticContractReceiver(root / "success.sqlite3", contract)
        try:
            success_reply = receiver.deliver(_SYNTHETIC_EVENT_KEY, at_seconds=0)
            checks.append(
                _check(
                    "application_ack",
                    success_reply.acknowledged
                    and not success_reply.duplicate
                    and success_reply.acknowledgement_code in success_codes
                    and receiver.receipt_count() == 1,
                    "application_ack_observed",
                    "application_ack_not_observed",
                )
            )
        finally:
            receiver.close()

        receiver = _LocalSyntheticContractReceiver(root / "duplicate.sqlite3", contract)
        try:
            first_reply = receiver.deliver(_SYNTHETIC_EVENT_KEY, at_seconds=0)
            duplicate_reply = receiver.deliver(_SYNTHETIC_EVENT_KEY, at_seconds=0)
            checks.append(
                _check(
                    "duplicate_delivery",
                    first_reply.acknowledged
                    and duplicate_reply.acknowledged
                    and duplicate_reply.duplicate
                    and duplicate_reply.acknowledgement_code == first_reply.acknowledgement_code
                    and receiver.receipt_count() == 1,
                    "duplicate_acknowledged_once",
                    "duplicate_delivery_created_extra_receipt",
                )
            )
        finally:
            receiver.close()

        receiver = _LocalSyntheticContractReceiver(root / "lost-ack.sqlite3", contract)
        try:
            receiver.deliver(_SYNTHETIC_EVENT_KEY, at_seconds=0)  # Deliberately drop its ACK.
            accepted_before_retry = receiver.receipt_count() == 1
            retry_reply = receiver.deliver(_SYNTHETIC_EVENT_KEY, at_seconds=0)
            checks.append(
                _check(
                    "lost_ack_retry",
                    _classify_failure("transport_timeout", retryable_codes, permanent_codes)
                    == "retryable"
                    and accepted_before_retry
                    and retry_reply.acknowledged
                    and retry_reply.duplicate
                    and receiver.receipt_count() == 1,
                    "ambiguous_ack_recovered",
                    "ambiguous_ack_not_recovered",
                )
            )
        finally:
            receiver.close()

        restart_path = root / "receiver-restart.sqlite3"
        first_receiver = _LocalSyntheticContractReceiver(restart_path, contract)
        try:
            first_reply = first_receiver.deliver(_SYNTHETIC_EVENT_KEY, at_seconds=0)
        finally:
            first_receiver.close()

        restarted_receiver = _LocalSyntheticContractReceiver(restart_path, contract)
        try:
            retry_reply = restarted_receiver.deliver(_SYNTHETIC_EVENT_KEY, at_seconds=0)
            checks.append(
                _check(
                    "receiver_restart",
                    contract.idempotency.survives_receiver_restart is True
                    and first_reply.acknowledged
                    and retry_reply.acknowledged
                    and retry_reply.duplicate
                    and restarted_receiver.receipt_count() == 1,
                    "receiver_restart_deduplicated",
                    "receiver_restart_redelivery_not_deduplicated",
                )
            )
        finally:
            restarted_receiver.close()

    permanent_code = permanent_codes[0] if permanent_codes else ""
    checks.append(
        _check(
            "permanent_rejection",
            bool(permanent_code)
            and _classify_failure(permanent_code, retryable_codes, permanent_codes) == "permanent",
            "permanent_failure_terminal",
            "permanent_failure_not_classified_terminal",
        )
    )
    checks.append(
        _check(
            "transport_timeout",
            _classify_failure("transport_timeout", retryable_codes, permanent_codes) == "retryable",
            "transport_timeout_retryable",
            "transport_timeout_not_retryable",
        )
    )

    horizon = required_horizon_seconds if required_horizon_seconds is not None else 1
    with TemporaryDirectory(prefix="medihub-contract-retention-") as retention_directory:
        receiver = _LocalSyntheticContractReceiver(
            Path(retention_directory) / "retention.sqlite3",
            contract,
        )
        try:
            first_reply = receiver.deliver(_SYNTHETIC_EVENT_KEY, at_seconds=0)
            horizon_reply = receiver.deliver(_SYNTHETIC_EVENT_KEY, at_seconds=horizon)
            checks.append(
                _check(
                    "idempotency_retention_horizon",
                    first_reply.acknowledged
                    and horizon_reply.acknowledged
                    and horizon_reply.duplicate
                    and receiver.receipt_count() == 1,
                    "idempotency_retention_covers_required_horizon",
                    "idempotency_retention_below_required_horizon",
                )
            )
        finally:
            receiver.close()

    drifted_version = f"{contract.interface_version} synthetic-test-drift"
    dispatch_allowed = _contract_version_matches(contract.interface_version, drifted_version)
    checks.append(
        _check(
            "interface_version_drift",
            not dispatch_allowed,
            "contract_version_mismatch_rejected",
            "contract_version_drift_not_rejected",
        )
    )
    return tuple(checks)


def _classify_failure(
    response_code: str,
    retryable_codes: tuple[str, ...],
    permanent_codes: tuple[str, ...],
) -> Literal["retryable", "permanent", "unknown"]:
    if response_code in retryable_codes:
        return "retryable"
    if response_code in permanent_codes:
        return "permanent"
    return "unknown"


def _contract_version_matches(expected: str, observed: str) -> bool:
    """Local fail-closed comparison; it does not query a remote capability endpoint."""

    return expected == observed


def _check(
    check_id: str,
    passed: bool,
    pass_code: str,
    fail_code: str,
) -> ContractAcceptanceCheck:
    return ContractAcceptanceCheck(
        check_id=check_id,
        passed=passed,
        result_code=pass_code if passed else fail_code,
    )


def _blocked(code: str) -> ContractAcceptanceSummary:
    return ContractAcceptanceSummary(
        status="blocked",
        checks=(),
        blockers=(code,),
        errors=(),
        required_idempotency_horizon_seconds=None,
    )


__all__ = [
    "MAX_REQUIRED_IDEMPOTENCY_HORIZON_SECONDS",
    "ContractAcceptanceCheck",
    "ContractAcceptanceSummary",
    "run_contract_acceptance",
]
