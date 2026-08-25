"""Kiosk Router와 주문 Agent/Repository의 유스케이스 경계."""

from uuid import UUID

from app.agents.kiosk_order_agent import make_order_reply
from app.repositories.kiosk_order_repository import get_cart, update_cart
from app.schemas.kiosk_order import (
    CartUpdateArgs,
    KioskTurnResponse,
    ReadyForPaymentResponse,
    TextTurnRequest,
    VoiceTurnRequest,
)


def process_text_turn(request: TextTurnRequest) -> KioskTurnResponse:
    cart = get_cart(request.session_id)
    reply = make_order_reply(request.text, cart)
    return KioskTurnResponse(
        session_id=request.session_id,
        transcript=request.text,
        assistant_message=reply["assistant_message"],
        speak_text=reply["assistant_message"],
        cart=cart,
        retrievals=reply.get("retrievals", []),
        requires_confirmation=reply["requires_confirmation"],
        trace=reply.get("trace", []),
    )


def process_voice_turn(_: VoiceTurnRequest) -> KioskTurnResponse:
    """A의 transcribe_and_retrieve 통합 전에는 음성 주문을 실행하지 않는다."""
    raise ValueError("음성 인식 Tool이 아직 통합되지 않았습니다.")


def get_order_cart(session_id: UUID) -> dict:
    return get_cart(session_id)


def update_order_cart(payload: CartUpdateArgs) -> dict:
    return update_cart(payload)


def mark_ready_for_payment(session_id: UUID) -> ReadyForPaymentResponse:
    cart = update_cart(CartUpdateArgs(session_id=session_id, operation="ready_for_payment"))
    return ReadyForPaymentResponse(cart=cart, assistant_message="주문을 확인했습니다. 화면에서 결제를 진행해 주세요.")
