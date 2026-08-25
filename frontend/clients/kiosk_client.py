"""햄버거 음성 주문 키오스크 Backend API 전용 클라이언트."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from core.api_client import BackendAPIError, request


KIOSK_API_PREFIX = "/api/kiosk"
VOICE_TURN_PATH = f"{KIOSK_API_PREFIX}/voice-turn"
TEXT_TURN_PATH = f"{KIOSK_API_PREFIX}/text-turn"

SUPPORTED_ORDER_TYPES = frozenset({"dine_in", "takeout"})
SUPPORTED_AUDIO_MIME_TYPES = frozenset(
    {
        "audio/aac",
        "audio/flac",
        "audio/m4a",
        "audio/mp3",
        "audio/mp4",
        "audio/mpeg",
        "audio/ogg",
        "audio/wav",
        "audio/webm",
        "audio/x-m4a",
        "audio/x-wav",
    }
)


def _validate_session_id(session_id: str) -> str:
    """세션 ID를 검증하고 Backend path에 사용할 표준 UUID 문자열을 반환한다."""
    if not isinstance(session_id, str) or not session_id.strip():
        raise BackendAPIError("주문 세션 ID가 필요합니다. 새 주문을 시작해 주세요.")

    try:
        return str(UUID(session_id.strip()))
    except ValueError as error:
        raise BackendAPIError("올바르지 않은 주문 세션 ID입니다. 새 주문을 시작해 주세요.") from error


def _validate_order_type(order_type: str) -> str:
    """주문 유형을 Backend 계약 값으로 제한한다."""
    if order_type not in SUPPORTED_ORDER_TYPES:
        raise BackendAPIError("주문 유형은 매장 식사 또는 포장 중 하나여야 합니다.")
    return order_type


def _validate_result(result: Any) -> dict[str, Any]:
    """모든 키오스크 API의 최상위 응답이 JSON 객체인지 확인한다."""
    if not isinstance(result, dict):
        raise BackendAPIError("백엔드가 올바른 키오스크 결과를 반환하지 않았습니다.")
    return result


def _session_path(session_id: str, suffix: str) -> str:
    valid_session_id = _validate_session_id(session_id)
    return f"{KIOSK_API_PREFIX}/sessions/{valid_session_id}/{suffix}"


def submit_voice_turn(
    session_id: str,
    audio_bytes: bytes,
    mime_type: str,
    order_type: str,
) -> dict[str, Any]:
    """음성을 Base64로 변환해 STT/RAG/Agent 주문 턴을 요청한다."""
    valid_session_id = _validate_session_id(session_id)
    valid_order_type = _validate_order_type(order_type)

    if not isinstance(audio_bytes, bytes) or not audio_bytes:
        raise BackendAPIError("녹음된 음성이 없습니다. 다시 녹음해 주세요.")

    normalized_mime_type = mime_type.strip().lower() if isinstance(mime_type, str) else ""
    if normalized_mime_type not in SUPPORTED_AUDIO_MIME_TYPES:
        raise BackendAPIError("지원하지 않는 음성 형식입니다. WAV 또는 WebM 형식으로 다시 녹음해 주세요.")

    payload = {
        "sessionId": valid_session_id,
        "audioBase64": base64.b64encode(audio_bytes).decode("ascii"),
        "mimeType": normalized_mime_type,
        "orderType": valid_order_type,
    }
    return _validate_result(request("POST", VOICE_TURN_PATH, json=payload))


def submit_text_turn(
    session_id: str,
    text: str,
    order_type: str,
) -> dict[str, Any]:
    """접근성 및 STT 대체용 텍스트 주문 턴을 요청한다."""
    valid_session_id = _validate_session_id(session_id)
    valid_order_type = _validate_order_type(order_type)
    normalized_text = text.strip() if isinstance(text, str) else ""
    if not normalized_text:
        raise BackendAPIError("주문할 내용을 입력해 주세요.")

    payload = {
        "sessionId": valid_session_id,
        "text": normalized_text,
        "orderType": valid_order_type,
    }
    return _validate_result(request("POST", TEXT_TURN_PATH, json=payload))


def get_order_cart(session_id: str) -> dict[str, Any]:
    """Backend를 단일 기준으로 사용해 현재 장바구니를 조회한다."""
    path = _session_path(session_id, "cart")
    return _validate_result(request("GET", path))


def update_order_cart(
    session_id: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """검증과 가격 계산은 Backend에 맡기고 장바구니 변경 요청을 전달한다."""
    if not isinstance(payload, Mapping) or not payload:
        raise BackendAPIError("장바구니 변경 내용이 필요합니다.")

    operation = payload.get("operation")
    if operation not in {"add", "update", "remove", "clear"}:
        raise BackendAPIError("지원하지 않는 장바구니 변경 작업입니다.")

    path = _session_path(session_id, "cart")
    return _validate_result(request("UPDATE", path, json=dict(payload)))


def ready_for_payment(session_id: str) -> dict[str, Any]:
    """결제를 실행하지 않고 주문을 결제 대기 상태로만 전환한다."""
    path = _session_path(session_id, "ready-for-payment")
    return _validate_result(request("POST", path, json={}))


__all__ = [
    "get_order_cart",
    "ready_for_payment",
    "submit_text_turn",
    "submit_voice_turn",
    "update_order_cart",
]
