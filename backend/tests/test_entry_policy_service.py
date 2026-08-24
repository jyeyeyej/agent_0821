from datetime import datetime, timedelta, timezone

from app.schemas.parking import VehicleLookupResult
from app.services.entry_policy_service import deny_processing_failure, evaluate_entry_policy


NOW = datetime(2026, 8, 24, tzinfo=timezone.utc)


def vehicle(status="active", expires_at=None, found=True) -> VehicleLookupResult:
    return VehicleLookupResult(
        found=found,
        plate_number="12가3456",
        vehicle_id="vehicle-1" if found else None,
        owner_label="테스트 차량" if found else None,
        access_status=status,
        access_expires_at=expires_at,
    )


def test_active_unexpired_vehicle_is_approved() -> None:
    result = evaluate_entry_policy(vehicle(expires_at=NOW + timedelta(seconds=1)), now=NOW)
    assert result.approved is True
    assert result.gate_command == "open"


def test_inactive_and_unregistered_vehicles_are_denied() -> None:
    assert evaluate_entry_policy(vehicle(status="inactive"), now=NOW).reason_code == "INACTIVE"
    assert evaluate_entry_policy(vehicle(status="not_registered", found=False), now=NOW).reason_code == "NOT_REGISTERED"


def test_expiration_boundary_is_denied() -> None:
    result = evaluate_entry_policy(vehicle(expires_at=NOW), now=NOW)
    assert result.approved is False
    assert result.reason_code == "EXPIRED"
    assert result.gate_command == "keep_closed"


def test_naive_expiration_fails_closed() -> None:
    result = evaluate_entry_policy(vehicle(expires_at=NOW.replace(tzinfo=None)), now=NOW)
    assert result.reason_code == "PROCESSING_FAILED"
    assert result.gate_command == "keep_closed"


def test_processing_failure_is_denied() -> None:
    assert deny_processing_failure().approved is False
