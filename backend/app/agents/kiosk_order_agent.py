"""키오스크 Agent: 허용된 Tool 결과만 근거로 주문을 안내하고 변경한다."""

from __future__ import annotations

import re
from typing import Any

from app.tools.executor import execute_tool_safely


_QUANTITY_WORDS = {
    "한": 1,
    "하나": 1,
    "두": 2,
    "둘": 2,
    "세": 3,
    "셋": 3,
    "네": 4,
    "넷": 4,
}
_ORDER_WORDS = ("주문", "주세요", "줘", "담아", "넣어")
_LOOKUP_WORDS = ("추천", "메뉴", "버거", "세트", "단품", "알레르기", "품절", "감자튀김", "콜라")
_ALLERGEN_WORDS = ("우유", "새우", "밀", "대두", "계란")


def _item_value(item: dict[str, Any], snake_name: str, camel_name: str) -> Any:
    return item.get(snake_name, item.get(camel_name))


def _catalog_query(text: str) -> str:
    """자연어 주문에서 카탈로그의 짧은 검색어를 만든다."""
    burger_match = re.search(r"([가-힣A-Za-z0-9]+(?:\s+[가-힣A-Za-z0-9]+){0,2}\s*버거)", text)
    if burger_match:
        phrase = burger_match.group(1).strip()
        return re.sub(r"^(?:저기|혹시|그럼|그리고)\s+", "", phrase)
    for phrase in ("감자튀김", "제로 콜라", "콜라"):
        if phrase in text:
            return phrase
    for keyword in ("매운", "새우", "불고기", "치킨", "클래식"):
        if keyword in text:
            return keyword
    return "버거" if "버거" in text or "메뉴" in text or "추천" in text else text.strip()


def _quantity(text: str) -> int | None:
    for match in re.finditer(
        r"(?<![가-힣A-Za-z0-9])(\d+|하나|한|둘|두|셋|세|넷|네)(?=\s|개|,|\.|$)\s*(개만|개요|개를|개씩|개)?",
        text,
    ):
        head = text[max(0, match.start() - 5) : match.start()]
        tail = text[match.end() : match.end() + 5]
        if any(option_word in head for option_word in ("치즈", "패티")) or re.match(
            r"\s*(?:장|치즈|패티)", tail
        ):
            continue
        token = match.group(1)
        return int(token) if token.isdigit() else _QUANTITY_WORDS[token]
    return None


def _option_count(text: str, option: str) -> int:
    if option not in text or not any(word in text for word in ("추가", "더", "넣어")):
        return 0
    patterns = (
        rf"{option}\s*(\d+|한|하나|두|둘|세|셋)\s*(?:장|개)?",
        rf"(\d+|한|하나|두|둘|세|셋)\s*(?:장|개)?\s*{option}",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            token = match.group(1)
            return int(token) if token.isdigit() else _QUANTITY_WORDS[token]
    return 1


def _is_add_intent(text: str) -> bool:
    if (
        "추천" in text
        or "알레르기" in text
        or "알려" in text
        or text.rstrip().endswith(("있어?", "있나요?", "뭐야?"))
    ):
        return False
    return any(word in text for word in _ORDER_WORDS)


def _question_intent(text: str) -> str:
    if "품절" in text:
        return "availability"
    if "알레르기" in text or any(word in text for word in ("안 들어", "빼고", "제외")):
        return "allergen"
    if "추천" in text:
        return "recommendation"
    if any(word in text for word in ("가격", "얼마", "몇 원")):
        return "price"
    if any(word in text for word in ("옵션", "사이즈업", "사이즈 업", "음료 변경", "세트 구성")):
        return "option"
    if any(word in text for word in ("포장", "매장에서", "매장 식사", "주문 변경", "주문 취소")):
        return "policy"
    return "menu"


def _rag_reason(retrievals: list[dict[str, Any]], intent: str, menu_id: str | None = None) -> str | None:
    for document in retrievals:
        metadata = document.get("metadata", {}) if isinstance(document, dict) else {}
        if not isinstance(metadata, dict):
            continue
        if menu_id and metadata.get("menu_id") == menu_id:
            return str(document.get("content", "")).strip() or None
        if intent == "recommendation" and metadata.get("intent") == "recommendation":
            return str(document.get("content", "")).strip() or None
        if intent == "policy" and metadata.get("type") == "policy":
            return str(document.get("content", "")).strip() or None
        if intent == "option" and metadata.get("type") == "option":
            return str(document.get("content", "")).strip() or None
    return None


def _catalog_suggestion(menu: dict[str, Any], reason: str | None = None) -> dict[str, Any]:
    suggestion = dict(menu)
    if reason:
        suggestion["reason"] = reason
    return suggestion


def _option_summary(menu: dict[str, Any]) -> str:
    options = _item_value(menu, "available_options", "availableOptions") or {}
    forms = options.get("order_forms", {})
    parts = []
    if forms:
        parts.append("단품" + ("·세트 변경 가능" if "set" in forms else "만 가능"))
    if options.get("size_up"):
        parts.append(f"사이즈업 {_money(options['size_up'])}")
    if options.get("extra_patty"):
        parts.append(f"패티 추가 {_money(options['extra_patty'])}")
    if options.get("extra_cheese"):
        parts.append(f"치즈 추가 {_money(options['extra_cheese'])}")
    if options.get("allowed_drinks"):
        parts.append("세트 음료 변경 가능")
    return ", ".join(parts) or "별도 옵션 정보가 없습니다."


def _answer_question(
    intent: str,
    items: list[dict[str, Any]],
    retrievals: list[dict[str, Any]],
    cart: dict,
    trace: list[dict[str, Any]],
) -> dict:
    if intent == "policy":
        message = _rag_reason(retrievals, "policy")
        if not message:
            message = "매장 식사와 포장을 선택할 수 있으며, 주문 완료 전에는 장바구니를 변경할 수 있습니다."
        return make_order_reply("", cart, retrievals=retrievals, trace=trace) | {
            "assistant_message": message, "suggestions": [], "requires_confirmation": False
        }
    if intent == "availability":
        sold_out = [item for item in items if not item.get("available", False)]
        if not sold_out:
            message = "현재 검색된 메뉴 중 품절 메뉴는 없습니다."
        else:
            details = []
            for item in sold_out:
                alternative = _item_value(item, "alternative_menu_id", "alternativeMenuId")
                text = f"{item.get('name', '메뉴')}는 현재 품절입니다"
                if alternative:
                    text += f". 대체 메뉴는 {alternative}입니다"
                details.append(text)
            message = " ".join(details) + "."
        return make_order_reply("", cart, retrievals=retrievals, suggestions=[_catalog_suggestion(item) for item in sold_out], trace=trace) | {
            "assistant_message": message, "requires_confirmation": False
        }
    if intent == "allergen":
        details = ", ".join(
            f"{item.get('name', '메뉴')}: {', '.join(item.get('allergens', [])) or '표시 알레르겐 없음'}"
            for item in items[:3]
        )
        message = f"카탈로그의 알레르기 정보는 {details or '검색 결과 없음'}입니다. 교차오염 가능성이 있으니 성분표와 매장 직원에게 다시 확인해 주세요."
        return make_order_reply("", cart, retrievals=retrievals, suggestions=[_catalog_suggestion(item) for item in items], trace=trace) | {
            "assistant_message": message, "requires_confirmation": True
        }
    if intent == "price":
        message = " ".join(f"{item.get('name', '메뉴')}는 현재 {_money(item.get('price'))}입니다." for item in items[:3])
        return make_order_reply("", cart, retrievals=retrievals, suggestions=[_catalog_suggestion(item) for item in items], trace=trace) | {
            "assistant_message": message or "가격 정보를 찾지 못했습니다.", "requires_confirmation": False
        }
    if intent == "option":
        message = " ".join(f"{item.get('name', '메뉴')}: {_option_summary(item)}." for item in items[:3])
        message = message or _rag_reason(retrievals, "option") or "옵션 정보를 찾지 못했습니다."
        return make_order_reply("", cart, retrievals=retrievals, suggestions=[_catalog_suggestion(item) for item in items], trace=trace) | {
            "assistant_message": message, "requires_confirmation": False
        }
    if intent == "recommendation":
        rag_menu_ids = {
            metadata.get("menu_id")
            for document in retrievals
            if isinstance(document, dict)
            for metadata in [document.get("metadata", {})]
            if isinstance(metadata, dict) and metadata.get("menu_id")
        }
        menu = next(
            (
                item for item in items
                if item.get("available", False) and _item_value(item, "menu_id", "menuId") in rag_menu_ids
            ),
            next((item for item in items if item.get("available", False)), None),
        )
        if menu is None:
            return make_order_reply("", cart, retrievals=retrievals, trace=trace) | {
                "assistant_message": "현재 추천할 수 있는 판매 중 메뉴를 찾지 못했습니다.", "requires_confirmation": True
            }
        menu_id = _item_value(menu, "menu_id", "menuId")
        reason = _rag_reason(retrievals, "recommendation", menu_id) or _rag_reason(retrievals, "recommendation")
        message = f"{menu.get('name', '메뉴')}를 추천드려요. 현재 {_money(menu.get('price'))}이며 판매 중입니다."
        if reason:
            message += f" {reason}"
        return make_order_reply("", cart, retrievals=retrievals, suggestions=[_catalog_suggestion(menu, reason)], trace=trace) | {
            "assistant_message": message, "requires_confirmation": False
        }
    message = " ".join(
        f"{item.get('name', '메뉴')}: {_money(item.get('price'))}, {'판매 중' if item.get('available') else '품절'}" for item in items[:3]
    )
    return make_order_reply("", cart, retrievals=retrievals, suggestions=[_catalog_suggestion(item) for item in items], trace=trace) | {
        "assistant_message": message or "관련 메뉴 정보를 찾지 못했습니다.", "requires_confirmation": False
    }


def _select_menu(text: str, items: list[dict[str, Any]]) -> dict[str, Any] | None:
    named_matches = [item for item in items if str(item.get("name", "")) in text]
    if named_matches:
        return max(named_matches, key=lambda item: len(str(item.get("name", ""))))
    return items[0] if len(items) == 1 else None


def _selection(text: str, menu: dict[str, Any]) -> dict[str, Any]:
    available_options = _item_value(menu, "available_options", "availableOptions") or {}
    allowed_drinks = list(available_options.get("allowed_drinks", []))
    drink_id = None
    if "제로 콜라" in text:
        drink_id = next((item for item in allowed_drinks if "zero" in item), None)
    elif "콜라" in text:
        drink_id = next((item for item in allowed_drinks if "zero" not in item), None)
    return {
        "order_form": "set" if "세트" in text else "single",
        "size_up": "사이즈업" in text or "사이즈 업" in text,
        "extra_patty": _option_count(text, "패티"),
        "extra_cheese": _option_count(text, "치즈"),
        "drink_id": drink_id,
    }


def _money(value: Any) -> str:
    try:
        return f"{int(value):,}원"
    except (TypeError, ValueError):
        return "금액 확인 필요"


def make_order_reply(
    text: str,
    cart: dict,
    retrievals: list[dict[str, Any]] | None = None,
    suggestions: list[dict[str, Any]] | None = None,
    trace: list[dict[str, Any]] | None = None,
) -> dict:
    normalized = text.strip()
    if not normalized:
        message = "말씀을 다시 들려주세요."
    elif "주문 완료" in normalized or "결제" in normalized:
        message = "장바구니에 메뉴를 먼저 담은 뒤 주문을 완료해 주세요."
    elif any(word in normalized for word in _LOOKUP_WORDS):
        message = "원하시는 메뉴와 수량을 말씀해 주세요. 예: 불고기 버거 세트 하나 주세요."
    else:
        message = "메뉴명, 단품 또는 세트, 수량을 말씀해 주세요."
    return {
        "assistant_message": message,
        "requires_confirmation": True,
        "cart": cart,
        "retrievals": retrievals or [],
        "suggestions": suggestions or [],
        "trace": trace or [{"stage": "agent_decision", "action": "ask_for_structured_order"}],
    }


def run_kiosk_order_agent(
    session_id: str,
    text: str,
    cart: dict,
    order_type: str | None = None,
    retrievals: list[dict[str, Any]] | None = None,
) -> dict:
    """카탈로그 검증 후 명확한 자연어 주문만 장바구니 Tool로 전달한다."""
    trace: list[dict[str, Any]] = []
    retrievals = retrievals or []
    normalized = text.strip()
    if not normalized:
        return make_order_reply(normalized, cart, trace=trace)

    if "주문 완료" in normalized:
        if not cart.get("items"):
            return make_order_reply(normalized, cart, trace=trace)
        completed = execute_tool_safely(
            "update_order_cart", {"session_id": session_id, "operation": "ready_for_payment"}
        )
        trace.append({"stage": "update_order_cart", "data": completed.model_dump(mode="json")})
        if completed.success:
            return {
                "assistant_message": "주문을 확인했습니다. 화면에서 결제를 진행해 주세요.",
                "requires_confirmation": False,
                "cart": completed.data,
                "retrievals": [],
                "suggestions": [],
                "trace": trace,
            }
        return make_order_reply(normalized, cart, trace=trace)

    question_intent = _question_intent(normalized)
    if question_intent == "policy" and not _is_add_intent(normalized):
        return _answer_question(question_intent, [], retrievals, cart, trace)

    should_search = (
        _is_add_intent(normalized)
        or any(word in normalized for word in _LOOKUP_WORDS)
        or question_intent in {"availability", "allergen", "recommendation", "price", "option"}
    )
    if not should_search:
        return make_order_reply(normalized, cart, trace=trace)

    catalog = execute_tool_safely(
        "search_menu_catalog", {"query": _catalog_query(normalized), "limit": 5}
    )
    trace.append({"stage": "search_menu_catalog", "data": catalog.model_dump(mode="json")})
    if not catalog.success:
        reply = make_order_reply(normalized, cart, trace=trace)
        reply["assistant_message"] = "메뉴 정보를 확인하지 못했습니다. 잠시 후 다시 말씀해 주세요."
        return reply

    items = catalog.data.get("items", [])
    suggestions = items
    if not _is_add_intent(normalized):
        return _answer_question(question_intent, items, retrievals, cart, trace)

    menu = _select_menu(normalized, items)
    quantity = _quantity(normalized)
    if menu is None or quantity is None:
        reply = make_order_reply(normalized, cart, suggestions=suggestions, trace=trace)
        reply["assistant_message"] = (
            "메뉴가 여러 개 검색되었습니다. 정확한 메뉴명과 수량을 말씀해 주세요."
            if menu is None
            else "주문할 수량을 말씀해 주세요."
        )
        return reply
    if not bool(menu.get("available", False)):
        alternative = _item_value(menu, "alternative_menu_id", "alternativeMenuId")
        message = f"{menu.get('name', '해당 메뉴')}는 현재 품절입니다."
        if alternative:
            message += f" 대체 메뉴({alternative})를 확인해 주세요."
        reply = make_order_reply(normalized, cart, suggestions=suggestions, trace=trace)
        reply["assistant_message"] = message
        return reply

    updated = execute_tool_safely(
        "update_order_cart",
        {
            "session_id": session_id,
            "operation": "add",
            "menu_id": _item_value(menu, "menu_id", "menuId"),
            "quantity": quantity,
            "order_type": order_type,
            "selection": _selection(normalized, menu),
        },
    )
    trace.append({"stage": "update_order_cart", "data": updated.model_dump(mode="json")})
    if not updated.success:
        reply = make_order_reply(normalized, cart, suggestions=suggestions, trace=trace)
        reply["assistant_message"] = "선택한 옵션으로 장바구니에 담지 못했습니다. 메뉴와 옵션을 다시 확인해 주세요."
        return reply

    order_form = "세트" if "세트" in normalized else "단품"
    return {
        "assistant_message": (
            f"{menu.get('name', '메뉴')} {order_form} {quantity}개를 담았습니다. "
            f"현재 총액은 {_money(updated.data.get('total'))}입니다."
        ),
        "requires_confirmation": False,
        "cart": updated.data,
        "retrievals": [],
        "suggestions": [],
        "trace": trace,
    }
