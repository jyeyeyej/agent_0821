from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.agents import parking_entry_agent
from app.main import app
from app.schemas.parking import ParkingAgentDecision, PlateRecognitionResult
from app.tools.vehicle_lookup import set_vehicle_repository_getter


JPEG = b"\xff\xd8\xff" + b"parking-image" + b"\xff\xd9"
client = TestClient(app)


@pytest.fixture(autouse=True)
def active_repository() -> Iterator[None]:
    set_vehicle_repository_getter(lambda plate: {
        "vehicle_id": "vehicle-1", "plate_number": plate, "owner_label": "테스트 차량 A",
        "access_status": "active", "access_expires_at": None,
    })
    yield
    set_vehicle_repository_getter(None)


def post_agent(source="agent"):
    return client.post(
        "/api/parking/agent/entry",
        files={"image": ("plate.jpg", JPEG, "image/jpeg")},
        data={"source": source},
    )


def test_agent_happy_case_uses_tool_and_policy() -> None:
    body = post_agent().json()
    assert body["approved"] is True
    assert body["gate_command"] == "open"
    assert [item["stage"] for item in body["trace"]] == [
        "1_plate_recognition", "2_agent_decision", "3_tool_execution", "4_entry_policy",
    ]


def test_agent_calls_tool_at_most_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    original = parking_entry_agent.execute_tool_safely

    def track(name, arguments):
        calls.append(name)
        return original(name, arguments)

    monkeypatch.setattr(parking_entry_agent, "execute_tool_safely", track)
    assert post_agent().status_code == 200
    assert calls == ["vehicle_lookup"]


def test_agent_recapture_does_not_call_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(parking_entry_agent, "extract_plate", lambda *_: PlateRecognitionResult(
        plate_number=None, confidence=0.1, provider="mock",
    ))
    calls: list[str] = []
    monkeypatch.setattr(parking_entry_agent, "execute_tool_safely", lambda *args: calls.append(args))
    body = post_agent().json()
    assert body["needs_recapture"] is True
    assert calls == []


def test_agent_cannot_change_ocr_plate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(parking_entry_agent, "decide_parking_action", lambda _recognition: ParkingAgentDecision(
        action="lookup_vehicle", plate_number="99가9999", reason="변조 시도",
    ))
    calls: list[str] = []
    monkeypatch.setattr(parking_entry_agent, "execute_tool_safely", lambda *args: calls.append(args))
    body = post_agent().json()
    assert body["approved"] is False
    assert body["needs_recapture"] is True
    assert calls == []


def test_agent_source_must_match_endpoint() -> None:
    assert post_agent(source="workflow").status_code == 422
