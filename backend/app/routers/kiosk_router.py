"""햄버거 주문 키오스크 Part B API."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.schemas.kiosk_order import CartUpdateArgs, KioskTurnResponse, OrderCart, ReadyForPaymentResponse, TextTurnRequest, VoiceTurnRequest
from app.services import kiosk_order_service


kiosk_router = APIRouter(prefix="/api/kiosk", tags=["음성 햄버거 키오스크"])


def _bad_request(error: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail={"code": "KIOSK_ORDER_ERROR", "message": str(error)})


@kiosk_router.post("/voice-turn", response_model=KioskTurnResponse)
def voice_turn(payload: VoiceTurnRequest) -> KioskTurnResponse:
    try:
        return kiosk_order_service.process_voice_turn(payload)
    except Exception as error:
        raise _bad_request(error) from error


@kiosk_router.post("/text-turn", response_model=KioskTurnResponse)
def text_turn(payload: TextTurnRequest) -> KioskTurnResponse:
    try:
        return kiosk_order_service.process_text_turn(payload)
    except Exception as error:
        raise _bad_request(error) from error


@kiosk_router.get("/sessions/{session_id}/cart", response_model=OrderCart)
def read_cart(session_id: UUID) -> OrderCart:
    try:
        return OrderCart.model_validate(kiosk_order_service.get_order_cart(session_id))
    except Exception as error:
        raise _bad_request(error) from error


@kiosk_router.patch("/sessions/{session_id}/cart", response_model=OrderCart)
def change_cart(session_id: UUID, payload: CartUpdateArgs) -> OrderCart:
    if payload.session_id != session_id:
        raise HTTPException(status_code=422, detail="sessionId와 URL session_id가 일치해야 합니다.")
    try:
        return OrderCart.model_validate(kiosk_order_service.update_order_cart(payload))
    except Exception as error:
        raise _bad_request(error) from error


@kiosk_router.post("/sessions/{session_id}/ready-for-payment", response_model=ReadyForPaymentResponse)
def ready_for_payment(session_id: UUID) -> ReadyForPaymentResponse:
    try:
        return kiosk_order_service.mark_ready_for_payment(session_id)
    except Exception as error:
        raise _bad_request(error) from error
