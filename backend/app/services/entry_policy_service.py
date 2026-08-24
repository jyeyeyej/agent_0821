"""LLM과 분리된 결정적 주차 출입 승인 정책입니다."""

from datetime import datetime, timezone

from app.schemas.parking import EntryPolicyResult, VehicleLookupResult


def deny_processing_failure() -> EntryPolicyResult:
    return EntryPolicyResult(
        approved=False,
        gate_command="keep_closed",
        reason="차량 정보를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.",
        reason_code="PROCESSING_FAILED",
    )


def evaluate_entry_policy(
    vehicle: VehicleLookupResult | None,
    *,
    now: datetime | None = None,
) -> EntryPolicyResult:
    if vehicle is None or not vehicle.found or vehicle.access_status == "not_registered":
        return EntryPolicyResult(
            approved=False,
            gate_command="keep_closed",
            reason="등록되지 않은 차량입니다.",
            reason_code="NOT_REGISTERED",
        )
    if vehicle.access_status != "active":
        return EntryPolicyResult(
            approved=False,
            gate_command="keep_closed",
            reason="현재 출입 권한이 비활성 상태입니다.",
            reason_code="INACTIVE",
        )
    current = now or datetime.now(timezone.utc)
    expires_at = vehicle.access_expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None or current.tzinfo is None:
            return deny_processing_failure()
        if expires_at <= current:
            return EntryPolicyResult(
                approved=False,
                gate_command="keep_closed",
                reason="차량 출입 권한이 만료되었습니다.",
                reason_code="EXPIRED",
            )
    return EntryPolicyResult(
        approved=True,
        gate_command="open",
        reason="등록된 활성 차량입니다.",
        reason_code="APPROVED",
    )
