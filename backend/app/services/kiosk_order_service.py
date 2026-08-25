"""Kiosk Router와 주문 Agent/Repository의 유스케이스 경계."""

from uuid import UUID

from app.agents.kiosk_order_agent import run_kiosk_order_agent
from app.repositories.kiosk_order_repository import get_cart, update_cart
from app.schemas.kiosk_order import (
    CartUpdateArgs,
    KioskTurnResponse,
    ReadyForPaymentResponse,
    TextTurnRequest,
    VoiceTurnRequest,
)
from app.tools.executor import execute_tool_safely


def process_text_turn(request: TextTurnRequest) -> KioskTurnResponse:
    cart = get_cart(request.session_id)
    reply = run_kiosk_order_agent(str(request.session_id), request.text, cart)
    return KioskTurnResponse(
        session_id=request.session_id,
        transcript=request.text,
        assistant_message=reply["assistant_message"],
        speak_text=reply["assistant_message"],
        cart=reply.get("cart", cart),
        retrievals=reply.get("retrievals", []),
        requires_confirmation=reply["requires_confirmation"],
        trace=reply.get("trace", []),
    )


def process_voice_turn(request: VoiceTurnRequest) -> KioskTurnResponse:
    stt = execute_tool_safely(
        "transcribe_and_retrieve",
        {
            "session_id": str(request.session_id),
            "audio_base64": request.audio_base64,
            "mime_type": request.mime_type,
        },
    )
    if not stt.success:
        raise ValueError("음성 인식을 처리하지 못했습니다.")
    transcript = stt.data["transcript"]
    cart = get_cart(request.session_id)
    if stt.data.get("needs_confirmation"):
        message = "잘 듣지 못했습니다. 메뉴명과 수량을 다시 말씀해 주세요."
        return KioskTurnResponse(
            session_id=request.session_id, transcript=transcript, assistant_message=message, speak_text=message,
            cart=cart, retrievals=stt.data.get("retrieved_documents", []), requires_confirmation=True,
            trace=[{"stage": "transcribe_and_retrieve", "data": stt.model_dump(mode="json")}],
        )
    reply = run_kiosk_order_agent(str(request.session_id), transcript, cart)
    trace = [{"stage": "transcribe_and_retrieve", "data": stt.model_dump(mode="json")}, *reply.get("trace", [])]
    return KioskTurnResponse(
        session_id=request.session_id, transcript=transcript, assistant_message=reply["assistant_message"],
        speak_text=reply["assistant_message"], cart=reply.get("cart", cart),
        retrievals=stt.data.get("retrieved_documents", []) + reply.get("retrievals", []),
        requires_confirmation=reply["requires_confirmation"], trace=trace,
    )


def get_order_cart(session_id: UUID) -> dict:
    return get_cart(session_id)


def update_order_cart(payload: CartUpdateArgs) -> dict:
    return update_cart(payload)


def mark_ready_for_payment(session_id: UUID) -> ReadyForPaymentResponse:
    cart = update_cart(CartUpdateArgs(session_id=session_id, operation="ready_for_payment"))
    return ReadyForPaymentResponse(cart=cart, assistant_message="주문을 확인했습니다. 화면에서 결제를 진행해 주세요.")
