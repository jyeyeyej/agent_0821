from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.parking import PlateRecognitionResult
from app.services import parking_workflow_service
from app.tools.vehicle_lookup import set_vehicle_repository_getter


JPEG = b"\xff\xd8\xff" + b"parking-image" + b"\xff\xd9"
client = TestClient(app)


@pytest.fixture(autouse=True)
def active_repository() -> Iterator[None]:
    set_vehicle_repository_getter(lambda plate: {
        "vehicle_id": "vehicle-1",
        "plate_number": plate,
        "owner_label": "테스트 차량 A",
        "access_status": "active",
        "access_expires_at": None,
    })
    yield
    set_vehicle_repository_getter(None)


def post_workflow(content=JPEG, content_type="image/jpeg", source="workflow"):
    return client.post(
        "/api/parking/workflow/entry",
        files={"image": ("plate.jpg", content, content_type)},
        data={"source": source},
    )


def test_workflow_happy_case_opens_gate() -> None:
    response = post_workflow()
    assert response.status_code == 200
    body = response.json()
    assert body["system_type"] == "workflow"
    assert body["approved"] is True
    assert body["gate_command"] == "open"
    assert body["recognized_plate_number"] == "12가3456"
    assert [item["stage"] for item in body["trace"]] == [
        "1_image_validation", "2_plate_recognition", "3_vehicle_lookup", "4_entry_policy",
    ]


def test_low_confidence_skips_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(parking_workflow_service, "extract_plate", lambda *_: PlateRecognitionResult(
        plate_number="12가3456", confidence=0.2, provider="mock",
    ))
    calls: list[str] = []
    monkeypatch.setattr(parking_workflow_service, "execute_tool_safely", lambda *args: calls.append(args))

    body = post_workflow().json()
    assert body["approved"] is False
    assert body["needs_recapture"] is True
    assert calls == []


@pytest.mark.parametrize(
    ("record", "reason_code"),
    [
        (None, "NOT_REGISTERED"),
        ({"vehicle_id": "v", "plate_number": "12가3456", "owner_label": "B", "access_status": "inactive", "access_expires_at": None}, "INACTIVE"),
    ],
)
def test_workflow_denies_disallowed_vehicle(record, reason_code) -> None:
    set_vehicle_repository_getter(lambda _plate: record)
    body = post_workflow().json()
    assert body["approved"] is False
    assert body["gate_command"] == "keep_closed"
    assert body["trace"][-1]["data"]["reason_code"] == reason_code


def test_database_failure_is_not_exposed() -> None:
    secret = "DATABASE_URL=postgresql://secret"

    def fail(_plate):
        raise RuntimeError(secret)

    set_vehicle_repository_getter(fail)
    response = post_workflow()
    assert response.status_code == 200
    assert response.json()["gate_command"] == "keep_closed"
    assert secret not in response.text


def test_source_must_match_endpoint() -> None:
    assert post_workflow(source="agent").status_code == 422


def test_invalid_image_requests_recapture() -> None:
    body = post_workflow(b"bad", "image/jpeg").json()
    assert body["approved"] is False
    assert body["needs_recapture"] is True
    assert body["gate_command"] == "keep_closed"
