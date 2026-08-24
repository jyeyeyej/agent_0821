from collections.abc import Iterator

import pytest

from app.schemas.parking import VehicleLookupArgs
from app.tools.executor import execute_tool_safely
from app.tools.vehicle_lookup import set_vehicle_repository_getter, vehicle_lookup


@pytest.fixture(autouse=True)
def reset_repository_getter() -> Iterator[None]:
    set_vehicle_repository_getter(None)
    yield
    set_vehicle_repository_getter(None)


def test_registered_vehicle_is_converted_to_tool_result() -> None:
    calls: list[str] = []

    def getter(plate_number: str):
        calls.append(plate_number)
        return {
            "vehicle_id": "vehicle-1",
            "plate_number": plate_number,
            "owner_label": "테스트 차량 A",
            "access_status": "active",
            "access_expires_at": None,
        }

    set_vehicle_repository_getter(getter)
    result = vehicle_lookup(VehicleLookupArgs(plate_number=" 12가 3456 "))

    assert calls == ["12가3456"]
    assert result["found"] is True
    assert result["access_status"] == "active"


def test_unregistered_vehicle_is_business_result() -> None:
    set_vehicle_repository_getter(lambda _plate: None)
    result = execute_tool_safely("vehicle_lookup", {"plate_number": "99가9999"})

    assert result.success is True
    assert result.data["found"] is False
    assert result.data["access_status"] == "not_registered"


def test_repository_failure_is_safely_wrapped() -> None:
    def fail(_plate: str):
        raise RuntimeError("DATABASE_URL=secret")

    set_vehicle_repository_getter(fail)
    result = execute_tool_safely("vehicle_lookup", {"plate_number": "12가3456"})

    assert result.success is False
    assert result.error["code"] == "TOOL_EXECUTION_ERROR"
    assert "secret" not in result.error["message"]


def test_invalid_plate_is_rejected_before_repository_call() -> None:
    result = execute_tool_safely("vehicle_lookup", {"plate_number": "@@"})
    assert result.success is False
    assert result.error["code"] == "TOOL_VALIDATION_ERROR"
