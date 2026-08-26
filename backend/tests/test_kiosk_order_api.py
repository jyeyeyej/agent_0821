from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents import kiosk_order_agent
from app.routers.kiosk_router import kiosk_router
from app.schemas.kiosk_order import TextTurnRequest
from app.schemas.stage_03 import ToolRunResult
from app.services import kiosk_order_service


def _cart(session_id: str, *, total: int = 0, items: list[dict] | None = None) -> dict:
    return {
        "sessionId": session_id,
        "status": "active",
        "orderType": "takeout",
        "items": items or [],
        "subtotal": total,
        "discount": 0,
        "total": total,
        "warnings": [],
        "nextAction": "continue_order",
    }


def _menu(*, available: bool = True) -> dict:
    return {
        "menu_id": "burger_spicy_chicken",
        "name": "매운 치킨 버거",
        "category": "burger",
        "price": 7000,
        "available": available,
        "allergens": ["우유"],
        "available_options": {
            "order_forms": {"single": 0, "set": 2500},
            "size_up": 700,
            "extra_patty": 2000,
            "extra_cheese": 600,
            "allowed_drinks": ["drink_cola", "drink_cola_zero"],
        },
        "alternative_menu_id": "burger_classic" if not available else None,
    }


def test_text_order_searches_catalog_and_adds_validated_cart_item(monkeypatch) -> None:
    session_id = str(uuid4())
    calls: list[tuple[str, dict]] = []

    def fake_execute(name: str, arguments: dict) -> ToolRunResult:
        calls.append((name, arguments))
        if name == "search_menu_catalog":
            return ToolRunResult(
                success=True,
                tool_name=name,
                data={"items": [_menu()], "matched_count": 1},
            )
        return ToolRunResult(
            success=True,
            tool_name=name,
            data=_cart(session_id, total=10100, items=[{"name": "매운 치킨 버거"}]),
        )

    monkeypatch.setattr(kiosk_order_agent, "execute_tool_safely", fake_execute)

    result = kiosk_order_agent.run_kiosk_order_agent(
        session_id,
        "매운 치킨 버거 세트 하나, 치즈 추가, 제로 콜라로 주세요",
        _cart(session_id),
        "dine_in",
    )

    assert [name for name, _arguments in calls] == ["search_menu_catalog", "update_order_cart"]
    assert calls[0][1]["query"] == "매운 치킨 버거"
    assert calls[1][1] == {
        "session_id": session_id,
        "operation": "add",
        "menu_id": "burger_spicy_chicken",
        "quantity": 1,
        "order_type": "dine_in",
        "selection": {
            "order_form": "set",
            "size_up": False,
            "extra_patty": 0,
            "extra_cheese": 1,
            "drink_id": "drink_cola_zero",
        },
    }
    assert result["requires_confirmation"] is False
    assert result["cart"]["total"] == 10100
    assert len(result["trace"]) == 2


def test_ambiguous_order_does_not_change_cart(monkeypatch) -> None:
    session_id = str(uuid4())
    calls: list[str] = []

    def fake_execute(name: str, _arguments: dict) -> ToolRunResult:
        calls.append(name)
        return ToolRunResult(
            success=True,
            tool_name=name,
            data={"items": [_menu(), {**_menu(), "menu_id": "burger_bulgogi", "name": "불고기 버거"}]},
        )

    monkeypatch.setattr(kiosk_order_agent, "execute_tool_safely", fake_execute)

    result = kiosk_order_agent.run_kiosk_order_agent(
        session_id, "버거 하나 주세요", _cart(session_id), "takeout"
    )

    assert calls == ["search_menu_catalog"]
    assert result["requires_confirmation"] is True
    assert result["cart"]["items"] == []


def test_sold_out_order_does_not_call_cart_tool(monkeypatch) -> None:
    session_id = str(uuid4())
    calls: list[str] = []

    def fake_execute(name: str, _arguments: dict) -> ToolRunResult:
        calls.append(name)
        return ToolRunResult(success=True, tool_name=name, data={"items": [_menu(available=False)]})

    monkeypatch.setattr(kiosk_order_agent, "execute_tool_safely", fake_execute)

    result = kiosk_order_agent.run_kiosk_order_agent(
        session_id, "매운 치킨 버거 하나 주세요", _cart(session_id), "takeout"
    )

    assert calls == ["search_menu_catalog"]
    assert result["requires_confirmation"] is True
    assert "품절" in result["assistant_message"]


def test_allergy_question_never_changes_cart(monkeypatch) -> None:
    session_id = str(uuid4())
    calls: list[str] = []

    def fake_execute(name: str, _arguments: dict) -> ToolRunResult:
        calls.append(name)
        return ToolRunResult(success=True, tool_name=name, data={"items": [_menu()]})

    monkeypatch.setattr(kiosk_order_agent, "execute_tool_safely", fake_execute)

    result = kiosk_order_agent.run_kiosk_order_agent(
        session_id, "매운 치킨 버거 알레르기 알려주세요", _cart(session_id), "takeout"
    )

    assert calls == ["search_menu_catalog"]
    assert result["requires_confirmation"] is True
    assert "매장 직원" in result["assistant_message"]


def test_sold_out_question_answers_availability_without_cart_update(monkeypatch) -> None:
    session_id = str(uuid4())
    calls: list[str] = []

    def fake_execute(name: str, _arguments: dict) -> ToolRunResult:
        calls.append(name)
        return ToolRunResult(success=True, tool_name=name, data={"items": [_menu(available=False)]})

    monkeypatch.setattr(kiosk_order_agent, "execute_tool_safely", fake_execute)

    result = kiosk_order_agent.run_kiosk_order_agent(
        session_id, "새우버거가 품절인지 알려줘", _cart(session_id)
    )

    assert calls == ["search_menu_catalog"]
    assert result["requires_confirmation"] is False
    assert "현재 품절" in result["assistant_message"]
    assert result["suggestions"][0]["available"] is False


def test_recommendation_uses_rag_reason_and_current_catalog_price(monkeypatch) -> None:
    session_id = str(uuid4())
    menu = _menu()

    monkeypatch.setattr(
        kiosk_order_agent,
        "execute_tool_safely",
        lambda name, _arguments: ToolRunResult(success=True, tool_name=name, data={"items": [menu]}),
    )
    result = kiosk_order_agent.run_kiosk_order_agent(
        session_id,
        "매운 메뉴 추천해줘",
        _cart(session_id),
        retrievals=[{"content": "매운맛과 든든한 구성을 원하면 추천합니다.", "metadata": {"intent": "recommendation", "menu_id": "burger_spicy_chicken"}}],
    )

    assert "7,000원" in result["assistant_message"]
    assert "매운맛과 든든한 구성" in result["assistant_message"]
    assert result["suggestions"][0]["reason"].startswith("매운맛")


def test_policy_question_uses_rag_without_catalog_call(monkeypatch) -> None:
    session_id = str(uuid4())

    monkeypatch.setattr(
        kiosk_order_agent,
        "execute_tool_safely",
        lambda *_args: (_ for _ in ()).throw(AssertionError("정책 답변은 카탈로그 변경을 호출하면 안 됩니다.")),
    )
    result = kiosk_order_agent.run_kiosk_order_agent(
        session_id,
        "포장 주문으로 가능한지 알려줘",
        _cart(session_id),
        retrievals=[{"content": "매장 식사와 포장을 선택할 수 있습니다.", "metadata": {"type": "policy"}}],
    )

    assert result["requires_confirmation"] is False
    assert result["assistant_message"] == "매장 식사와 포장을 선택할 수 있습니다."


def test_text_turn_passes_rag_results_to_order_agent(monkeypatch) -> None:
    session_id = uuid4()
    received = {}

    monkeypatch.setattr(kiosk_order_service, "get_cart", lambda _session_id: _cart(str(session_id)))
    monkeypatch.setattr(kiosk_order_service, "retrieve_knowledge", lambda *_args, **_kwargs: [])

    def fake_agent(_session_id, _text, cart, _order_type, retrievals):
        received["retrievals"] = retrievals
        return {
            "assistant_message": "정책 안내",
            "requires_confirmation": False,
            "cart": cart,
            "retrievals": retrievals,
            "suggestions": [],
            "trace": [],
        }

    monkeypatch.setattr(kiosk_order_service, "run_kiosk_order_agent", fake_agent)

    response = kiosk_order_service.process_text_turn(
        TextTurnRequest(sessionId=session_id, text="포장 가능한지 알려줘", orderType="takeout")
    )

    assert received["retrievals"] == []
    assert response.assistant_message == "정책 안내"
    assert response.trace[0]["stage"] == "retrieve_knowledge"


def test_empty_cart_is_not_marked_ready_for_payment(monkeypatch) -> None:
    session_id = str(uuid4())
    called = False

    def fake_execute(_name: str, _arguments: dict) -> ToolRunResult:
        nonlocal called
        called = True
        raise AssertionError("빈 장바구니에서는 Tool을 호출하면 안 됩니다.")

    monkeypatch.setattr(kiosk_order_agent, "execute_tool_safely", fake_execute)

    result = kiosk_order_agent.run_kiosk_order_agent(session_id, "주문 완료", _cart(session_id))

    assert called is False
    assert result["requires_confirmation"] is True


def test_patch_cart_accepts_camel_case_payload(monkeypatch) -> None:
    session_id = uuid4()
    cart_item_id = uuid4()
    captured = {}

    def fake_update(payload):
        captured.update(payload.model_dump(mode="json"))
        return _cart(str(session_id))

    monkeypatch.setattr("app.services.kiosk_order_service.update_order_cart", fake_update)
    app = FastAPI()
    app.include_router(kiosk_router)
    client = TestClient(app)

    response = client.patch(
        f"/api/kiosk/sessions/{session_id}/cart",
        json={
            "sessionId": str(session_id),
            "operation": "remove",
            "cartItemId": str(cart_item_id),
            "orderType": "takeout",
        },
    )

    assert response.status_code == 200
    assert captured["sessionId"] == str(session_id)
    assert captured["cartItemId"] == str(cart_item_id)
    assert response.json()["orderType"] == "takeout"
    assert response.json()["nextAction"] == "continue_order"
