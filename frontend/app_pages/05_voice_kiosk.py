"""햄버거 음성 주문 키오스크 화면.

가격, 재고, 옵션 검증은 모두 Backend의 kiosk_client 응답을 단일 기준으로
표시한다. 이 페이지는 주문 화면과 Streamlit 세션 상태만 관리한다.
"""

from __future__ import annotations

from typing import Any, Callable
from uuid import uuid4

import streamlit as st

from core.api_client import BackendAPIError

try:
    from clients.kiosk_client import (
        get_order_cart,
        ready_for_payment,
        submit_text_turn,
        submit_voice_turn,
        update_order_cart,
    )
except ImportError:
    # kiosk_client.py는 API Client 담당자가 별도로 제공한다. 페이지 모듈 자체는
    # 그 작업과 병렬로 열어 볼 수 있게 하되, 주문 요청은 막는다.
    get_order_cart = ready_for_payment = submit_text_turn = submit_voice_turn = update_order_cart = None


SESSION_KEY = "kiosk_session_id"
ORDER_TYPE_KEY = "kiosk_order_type"
MESSAGES_KEY = "kiosk_messages"
CART_KEY = "kiosk_cart"
SUGGESTIONS_KEY = "kiosk_suggestions"
CONFIRMATION_KEY = "kiosk_requires_confirmation"
PROCESSING_KEY = "kiosk_processing"
STATUS_KEY = "kiosk_status"
COMPLETE_CONFIRMATION_KEY = "kiosk_complete_confirmation"
ERROR_KEY = "kiosk_error_message"
TRACE_KEY = "kiosk_trace"
RETRIEVALS_KEY = "kiosk_retrievals"


def _initialize_state() -> None:
    defaults = {
        SESSION_KEY: str(uuid4()),
        ORDER_TYPE_KEY: "dine_in",
        MESSAGES_KEY: [],
        CART_KEY: {"status": "active", "items": [], "subtotal": 0, "discount": 0, "total": 0, "warnings": []},
        SUGGESTIONS_KEY: [],
        CONFIRMATION_KEY: False,
        PROCESSING_KEY: False,
        STATUS_KEY: "active",
        COMPLETE_CONFIRMATION_KEY: False,
        ERROR_KEY: None,
        TRACE_KEY: [],
        RETRIEVALS_KEY: [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _client_ready() -> bool:
    if get_order_cart is None:
        st.warning("키오스크 API Client를 준비 중입니다. 잠시 후 다시 시도해 주세요.")
        return False
    return True


def _money(value: Any) -> str:
    try:
        return f"{int(value or 0):,}원"
    except (TypeError, ValueError):
        return "금액 확인 필요"


def _apply_response(response: dict[str, Any], customer_text: str | None = None) -> None:
    cart = response.get("cart")
    if not isinstance(cart, dict) and isinstance(response.get("items"), list) and response.get("status"):
        # PATCH 장바구니 API는 wrapper 없이 최신 OrderCart 자체를 반환한다.
        cart = response
    if isinstance(cart, dict):
        st.session_state[CART_KEY] = cart
        st.session_state[STATUS_KEY] = cart.get("status", st.session_state[STATUS_KEY])
    suggestions = response.get("suggestions")
    if isinstance(suggestions, list):
        st.session_state[SUGGESTIONS_KEY] = suggestions
    if isinstance(response.get("trace"), list):
        st.session_state[TRACE_KEY] = response["trace"]
    if isinstance(response.get("retrievals"), list):
        st.session_state[RETRIEVALS_KEY] = response["retrievals"]
    st.session_state[CONFIRMATION_KEY] = bool(response.get("requiresConfirmation", False))

    transcript = response.get("transcript") or customer_text
    if transcript:
        st.session_state[MESSAGES_KEY].append({"role": "user", "content": str(transcript)})
    message = response.get("assistantMessage")
    if message:
        st.session_state[MESSAGES_KEY].append({"role": "assistant", "content": str(message)})


def _run_request(action: Callable[[], dict[str, Any]], customer_text: str | None = None) -> None:
    if st.session_state[PROCESSING_KEY]:
        return
    st.session_state[PROCESSING_KEY] = True
    st.session_state[ERROR_KEY] = None
    st.session_state[TRACE_KEY] = []
    st.session_state[RETRIEVALS_KEY] = []
    try:
        with st.spinner("주문 내용을 확인하고 있습니다..."):
            response = action()
        if not isinstance(response, dict):
            raise BackendAPIError("백엔드가 올바른 키오스크 응답을 반환하지 않았습니다.")
        _apply_response(response, customer_text)
    except BackendAPIError as error:
        st.session_state[ERROR_KEY] = f"{error} 기존 장바구니는 유지됩니다. 잠시 후 다시 시도해 주세요."
    except Exception:
        st.session_state[ERROR_KEY] = "주문 처리 중 문제가 발생했습니다. 입력 내용을 확인한 뒤 다시 시도해 주세요."
    finally:
        st.session_state[PROCESSING_KEY] = False


def _refresh_cart() -> None:
    if not _client_ready():
        return
    try:
        cart = get_order_cart(st.session_state[SESSION_KEY])
        if isinstance(cart, dict):
            st.session_state[CART_KEY] = cart
            st.session_state[STATUS_KEY] = cart.get("status", "active")
    except BackendAPIError:
        # 최초 진입에 서버가 준비되지 않은 경우에도 입력 UI는 남겨 둔다.
        st.info("장바구니를 불러오지 못했습니다. Backend 연결 상태를 확인해 주세요.")


def _render_messages() -> None:
    if st.session_state.get(ERROR_KEY):
        st.error(st.session_state[ERROR_KEY])
    for message in st.session_state[MESSAGES_KEY]:
        with st.chat_message(message.get("role", "assistant")):
            st.write(message.get("content", ""))
    if st.session_state[CONFIRMATION_KEY]:
        st.warning("주문을 바꾸기 전에 안내된 내용을 확인해 주세요.")

    suggestions = st.session_state[SUGGESTIONS_KEY]
    if suggestions:
        st.subheader("추천 메뉴")
        for suggestion in suggestions:
            if not isinstance(suggestion, dict):
                continue
            name = suggestion.get("name") or suggestion.get("menuName") or "추천 메뉴"
            availability = "판매 가능" if suggestion.get("available", True) else "품절"
            st.markdown(f"**{name}** · {_money(suggestion.get('price'))} · {availability}")
            reason = suggestion.get("reason") or suggestion.get("recommendationReason")
            if reason:
                st.caption(str(reason))


def _render_cart() -> None:
    cart = st.session_state[CART_KEY]
    st.subheader("장바구니")
    items = cart.get("items", []) if isinstance(cart, dict) else []
    if not items:
        st.info("담긴 메뉴가 없습니다.")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("menuName") or "메뉴"
        selection = item.get("selection") if isinstance(item.get("selection"), dict) else {}
        form = selection.get("orderForm") or selection.get("order_form")
        quantity = item.get("quantity", 1)
        st.markdown(f"**{name}** {f'({form})' if form else ''}")
        st.caption(f"수량 {quantity} · 항목 합계 {_money(item.get('lineTotal') or item.get('line_total'))}")
        st.caption(
            f"단가 {_money(item.get('unitPrice') or item.get('unit_price'))} · "
            f"옵션 {_money(item.get('optionPrice') or item.get('option_price'))}"
        )
        if selection:
            st.caption(f"옵션: {selection}")
        change, remove = st.columns(2)
        disabled = st.session_state[PROCESSING_KEY] or st.session_state[STATUS_KEY] == "ready_for_payment"
        if change.button("수량 +1", key=f"kiosk_quantity_{index}", disabled=disabled) and _client_ready():
            _run_request(lambda item=item: update_order_cart(st.session_state[SESSION_KEY], {
                "operation": "update", "menuId": item.get("menuId") or item.get("menu_id"),
                "quantity": int(item.get("quantity", 1)) + 1, "orderType": st.session_state[ORDER_TYPE_KEY],
                "cartItemId": item.get("cartItemId") or item.get("cart_item_id"),
                "selection": item.get("selection"),
            }))
            st.rerun()
        if remove.button("삭제", key=f"kiosk_remove_{index}", disabled=disabled) and _client_ready():
            _run_request(lambda item=item: update_order_cart(st.session_state[SESSION_KEY], {
                "operation": "remove", "cartItemId": item.get("cartItemId") or item.get("cart_item_id"),
                "orderType": st.session_state[ORDER_TYPE_KEY],
            }))
            st.rerun()

    for warning in cart.get("warnings", []) if isinstance(cart, dict) else []:
        st.warning(str(warning))
    st.divider()
    st.write(f"소계: {_money(cart.get('subtotal') if isinstance(cart, dict) else 0)}")
    st.write(f"할인: {_money(cart.get('discount') if isinstance(cart, dict) else 0)}")
    st.markdown(f"### 총액: {_money(cart.get('total') if isinstance(cart, dict) else 0)}")


def _start_new_order() -> None:
    st.session_state[SESSION_KEY] = str(uuid4())
    st.session_state[MESSAGES_KEY] = []
    st.session_state[CART_KEY] = {"status": "active", "items": [], "subtotal": 0, "discount": 0, "total": 0, "warnings": []}
    st.session_state[SUGGESTIONS_KEY] = []
    st.session_state[CONFIRMATION_KEY] = False
    st.session_state[STATUS_KEY] = "active"
    st.session_state[COMPLETE_CONFIRMATION_KEY] = False
    st.session_state[ERROR_KEY] = None


_initialize_state()
if "kiosk_cart_loaded" not in st.session_state:
    st.session_state.kiosk_cart_loaded = True
    _refresh_cart()

st.title("🎙️ 햄버거 음성 주문 키오스크")
st.caption("음성 또는 텍스트로 주문하세요. 결제 정보는 이 화면에서 받지 않습니다.")

if st.session_state[STATUS_KEY] == "ready_for_payment":
    st.success("결제 대기 중입니다. 화면에서 결제 수단을 선택해 주세요.")
    if st.button("새 주문 시작", type="primary"):
        _start_new_order()
        st.rerun()
    st.stop()

order_type = st.radio(
    "주문 방식",
    options=["dine_in", "takeout"],
    format_func=lambda value: "매장에서 먹기" if value == "dine_in" else "포장",
    horizontal=True,
    index=0 if st.session_state[ORDER_TYPE_KEY] == "dine_in" else 1,
    disabled=st.session_state[PROCESSING_KEY],
)
st.session_state[ORDER_TYPE_KEY] = order_type

conversation_column, cart_column = st.columns([3, 2])
with conversation_column:
    _render_messages()
with cart_column:
    _render_cart()

st.divider()
audio_input = getattr(st, "audio_input", None)
audio = audio_input("음성으로 주문하기") if audio_input else st.file_uploader("음성 파일 업로드", type=["wav", "mp3", "webm", "m4a"])
text = st.text_input("텍스트로 주문하기", placeholder="예: 불고기 버거 세트 하나 주세요")

is_processing = st.session_state[PROCESSING_KEY]
voice_disabled = is_processing or audio is None or bool(text.strip())
text_disabled = is_processing or not text.strip() or audio is not None
voice_button, text_button, clear_button, complete_button = st.columns(4)

if voice_button.button("음성 전송", type="primary", disabled=voice_disabled) and _client_ready():
    audio_bytes = audio.getvalue()
    mime_type = getattr(audio, "type", None) or "audio/wav"
    _run_request(lambda: submit_voice_turn(st.session_state[SESSION_KEY], audio_bytes, mime_type, st.session_state[ORDER_TYPE_KEY]))
    st.rerun()
if text_button.button("텍스트 전송", type="primary", disabled=text_disabled) and _client_ready():
    _run_request(lambda: submit_text_turn(st.session_state[SESSION_KEY], text.strip(), st.session_state[ORDER_TYPE_KEY]), text.strip())
    st.rerun()
if clear_button.button("장바구니 비우기", disabled=is_processing or not st.session_state[CART_KEY].get("items")) and _client_ready():
    _run_request(lambda: update_order_cart(st.session_state[SESSION_KEY], {"operation": "clear", "orderType": st.session_state[ORDER_TYPE_KEY]}))
    st.rerun()
if complete_button.button("주문 완료", disabled=is_processing or not st.session_state[CART_KEY].get("items")):
    st.session_state[COMPLETE_CONFIRMATION_KEY] = True

if st.session_state[COMPLETE_CONFIRMATION_KEY]:
    st.warning("현재 장바구니의 주문과 총액을 확인하셨나요? 결제 대기 상태로 전환하면 수정할 수 없습니다.")
    confirm, cancel = st.columns(2)
    if confirm.button("확인하고 주문 완료", type="primary", disabled=is_processing) and _client_ready():
        _run_request(lambda: ready_for_payment(st.session_state[SESSION_KEY]))
        st.rerun()
    if cancel.button("계속 수정하기", disabled=is_processing):
        st.session_state[COMPLETE_CONFIRMATION_KEY] = False
        st.rerun()

with st.expander("개발자 정보", expanded=False):
    st.json({
        "sessionId": st.session_state[SESSION_KEY],
        "cart": st.session_state[CART_KEY],
        "retrievals": st.session_state[RETRIEVALS_KEY],
        "trace": st.session_state[TRACE_KEY],
    })
