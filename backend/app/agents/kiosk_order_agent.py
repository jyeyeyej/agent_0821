"""키오스크 Agent: 허용된 Tool 결과만 근거로 다음 주문 행동을 안내한다."""

from typing import Any

from app.tools.executor import execute_tool_safely


def make_order_reply(
    text: str,
    cart: dict,
    retrievals: list[dict[str, Any]] | None = None,
    trace: list[dict[str, Any]] | None = None,
) -> dict:
    """LLM 교체 전에도 안전하게 동작하는 결정적 응답 경계.

    실제 Tool 선택은 통합 시 A의 STT/RAG 결과와 Registry allowlist를 통해 확장한다.
    이 함수는 메뉴/옵션이 구조화되지 않은 자연어만으로 장바구니를 수정하지 않는다.
    """
    normalized = text.strip()
    if not normalized:
        message = "말씀을 다시 들려주세요."
        return {"assistant_message": message, "requires_confirmation": True}
    if "주문 완료" in normalized or "결제" in normalized:
        message = "주문 내용을 확인하겠습니다. 화면의 주문 완료 버튼을 선택해 주세요."
    elif any(word in normalized for word in ("추천", "메뉴", "버거", "세트", "알레르기", "품절")):
        message = "메뉴와 옵션을 확인했습니다. 원하시는 메뉴와 수량을 말씀해 주세요."
    else:
        message = "메뉴명, 단품 또는 세트, 수량을 말씀해 주세요."
    return {
        "assistant_message": message,
        "requires_confirmation": True,
        "retrievals": retrievals or [],
        "trace": trace or [{"stage": "agent_decision", "action": "ask_for_structured_order"}],
    }


def run_kiosk_order_agent(session_id: str, text: str, cart: dict) -> dict:
    """메뉴 탐색은 읽기 Tool로, 주문 완료는 상태 변경 Tool로 안전 실행한다."""
    trace: list[dict[str, Any]] = []
    retrievals: list[dict[str, Any]] = []
    normalized = text.strip()
    if not normalized:
        return make_order_reply(normalized, cart, trace=trace)

    if any(word in normalized for word in ("추천", "메뉴", "버거", "세트", "알레르기", "품절")):
        catalog = execute_tool_safely("search_menu_catalog", {"query": normalized, "limit": 5})
        trace.append({"stage": "search_menu_catalog", "data": catalog.model_dump(mode="json")})
        if catalog.success:
            retrievals = catalog.data.get("items", [])

    if "주문 완료" in normalized:
        completed = execute_tool_safely(
            "update_order_cart", {"session_id": session_id, "operation": "ready_for_payment"}
        )
        trace.append({"stage": "update_order_cart", "data": completed.model_dump(mode="json")})
        if completed.success:
            cart = completed.data
            message = "주문을 확인했습니다. 화면에서 결제를 진행해 주세요."
            return {"assistant_message": message, "requires_confirmation": False, "cart": cart, "retrievals": retrievals, "trace": trace}

    reply = make_order_reply(normalized, cart, retrievals=retrievals, trace=trace)
    reply["cart"] = cart
    return reply
