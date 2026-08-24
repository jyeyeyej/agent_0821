from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents import menu_recommendation_agent
from app.routers.menu_recommendation_router import menu_recommendation_router
from app.schemas.menu_recommendation import DietaryCheckArgs, MenuSearchArgs
from app.services import menu_recommendation_service
from app.tools.menu import check_dietary_conditions, search_menus
from app.tools.registry import TOOL_REGISTRY, ToolSpec


HAPPY_CASE = {
    "mealTime": "저녁",
    "people": 2,
    "budget": 30000,
    "preferences": ["한식", "따뜻한 음식"],
    "excludedFoods": [],
    "allergies": [],
    "spicyLevel": "보통",
    "hasSoup": None,
    "quickMeal": False,
}


test_app = FastAPI()
test_app.include_router(menu_recommendation_router)
client = TestClient(test_app)


@pytest.fixture(autouse=True)
def register_menu_tools_for_domain_test() -> Iterator[None]:
    """공유 Registry 파일을 수정하지 않고 TK의 통합 계약을 검증합니다."""

    previous = {
        name: TOOL_REGISTRY.get(name)
        for name in ("search_menus", "check_dietary_conditions")
    }
    TOOL_REGISTRY["search_menus"] = ToolSpec(
        name="search_menus",
        description="식사 조건에 맞는 메뉴 후보를 검색합니다.",
        input_model=MenuSearchArgs,
        function=search_menus,
    )
    TOOL_REGISTRY["check_dietary_conditions"] = ToolSpec(
        name="check_dietary_conditions",
        description="메뉴 후보의 알레르기와 제외 음식 충돌을 확인합니다.",
        input_model=DietaryCheckArgs,
        function=check_dietary_conditions,
    )
    yield
    for name, spec in previous.items():
        if spec is None:
            TOOL_REGISTRY.pop(name, None)
        else:
            TOOL_REGISTRY[name] = spec


def test_happy_case_returns_recommendations_and_two_tool_results() -> None:
    response = client.post("/api/menu/recommend", json=HAPPY_CASE)

    assert response.status_code == 200
    body = response.json()
    assert body["agentType"] == "menu_recommendation"
    assert body["recommendations"]
    assert body["recommendations"][0]["isAlternative"] is False
    assert any(item["isAlternative"] for item in body["recommendations"][1:])
    assert [item["toolName"] for item in body["toolResults"]] == [
        "search_menus",
        "check_dietary_conditions",
    ]
    assert all(item["success"] for item in body["toolResults"])


def test_tools_execute_in_the_required_order(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    original = menu_recommendation_agent.execute_tool_safely

    def track(name: str, arguments: dict):
        calls.append(name)
        return original(name, arguments)

    monkeypatch.setattr(menu_recommendation_agent, "execute_tool_safely", track)

    response = client.post("/api/menu/recommend", json=HAPPY_CASE)

    assert response.status_code == 200
    assert calls == ["search_menus", "check_dietary_conditions"]


def test_recommendations_never_exceed_budget() -> None:
    response = client.post("/api/menu/recommend", json=HAPPY_CASE)

    assert response.status_code == 200
    assert all(item["totalPrice"] <= HAPPY_CASE["budget"] for item in response.json()["recommendations"])


def test_excluded_food_is_not_recommended() -> None:
    payload = {**HAPPY_CASE, "excludedFoods": ["닭고기"]}
    response = client.post("/api/menu/recommend", json=payload)

    assert response.status_code == 200
    names = {item["name"] for item in response.json()["recommendations"]}
    assert "닭고기 된장찌개 정식" not in names
    assert "소고기 불고기 정식" in names


def test_allergy_conflict_is_removed_after_dietary_check() -> None:
    payload = {**HAPPY_CASE, "allergies": ["참깨"]}
    response = client.post("/api/menu/recommend", json=payload)

    assert response.status_code == 200
    names = {item["name"] for item in response.json()["recommendations"]}
    assert "소고기 불고기 정식" not in names
    assert "닭고기 된장찌개 정식" in names


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("mealTime", "브런치"),
        ("people", 0),
        ("people", 21),
        ("budget", 999),
        ("spicyLevel", "아주 매움"),
        ("preferences", [""]),
    ],
)
def test_invalid_requests_return_422(field: str, value: object) -> None:
    response = client.post("/api/menu/recommend", json={**HAPPY_CASE, field: value})

    assert response.status_code == 422


def test_unknown_request_field_is_rejected() -> None:
    response = client.post(
        "/api/menu/recommend",
        json={**HAPPY_CASE, "unknown": True},
    )

    assert response.status_code == 422


def test_no_candidates_returns_follow_up_and_keeps_two_tool_trace() -> None:
    payload = {**HAPPY_CASE, "budget": 1000}
    response = client.post("/api/menu/recommend", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["recommendations"] == []
    assert body["followUpQuestions"]
    assert [item["toolName"] for item in body["toolResults"]] == [
        "search_menus",
        "check_dietary_conditions",
    ]


def test_same_input_returns_same_result() -> None:
    first = client.post("/api/menu/recommend", json=HAPPY_CASE)
    second = client.post("/api/menu/recommend", json=HAPPY_CASE)

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()


def test_internal_exception_is_not_exposed(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "C:\\private\\token.txt API_KEY=secret"

    def fail(_request):
        raise RuntimeError(secret)

    monkeypatch.setattr(menu_recommendation_service, "run_menu_recommendation_agent", fail)
    response = client.post("/api/menu/recommend", json=HAPPY_CASE)

    assert response.status_code == 200
    serialized = response.text
    assert secret not in serialized
    assert "AGENT_EXECUTION_ERROR" in serialized
