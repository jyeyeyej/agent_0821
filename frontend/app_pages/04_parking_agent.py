"""번호판 이미지를 분석해 주차 출입 여부를 안내하는 AI Agent 화면."""

import hashlib
from typing import Any

import streamlit as st

from clients.parking_agent_client import run_parking_agent_entry
from core.api_client import BackendAPIError


RESULT_KEY = "parking_agent_result"
IMAGE_KEY = "parking_agent_image_fingerprint"
PROCESSING_KEY = "parking_agent_processing"


def _format_confidence(value: Any) -> str:
    """0~1 또는 0~100 범위의 OCR 신뢰도를 읽기 쉽게 표시한다."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "확인할 수 없음"
    percentage = value * 100 if 0 <= value <= 1 else value
    return f"{percentage:.1f}%"


def _render_result(result: Any) -> None:
    """Backend 정책 결과와 Agent 실행 Trace를 표시한다."""
    if not isinstance(result, dict):
        st.warning("주차 출입 결과 형식을 확인할 수 없습니다. 다시 촬영해 주세요.")
        return

    approved = result.get("approved")
    if approved is True:
        st.success("출입이 승인되었습니다.")
    elif approved is False:
        st.error("출입이 승인되지 않았습니다. 차량 등록 또는 출입 권한을 확인해 주세요.")
    else:
        st.warning("승인 결과를 확인할 수 없습니다. 번호판을 다시 촬영해 주세요.")

    plate_number = result.get("recognized_plate_number") or "인식되지 않음"
    confidence = _format_confidence(result.get("recognition_confidence"))
    gate_command = result.get("gate_command")
    gate_label = {
        "open": "열림 (open)",
        "keep_closed": "닫힘 유지 (keep_closed)",
    }.get(gate_command, "명령 없음")

    plate_column, confidence_column, gate_column = st.columns(3)
    plate_column.metric("인식 번호판", plate_number)
    confidence_column.metric("OCR 신뢰도", confidence)
    gate_column.metric("차단기 명령", gate_label)

    reason = result.get("reason")
    if reason:
        st.markdown("**Backend 판단 사유**")
        st.write(reason)

    if approved is not True and gate_command != "open":
        st.info("번호판이 선명하게 보이도록 위치와 조명을 조정한 뒤 다시 촬영해 주세요.")

    trace = result.get("trace")
    tool_result = result.get("tool_result")
    with st.expander("Agent 판단 · Tool 실행 · Backend 정책 Trace", expanded=False):
        if trace or tool_result:
            st.json({"trace": trace or [], "tool_result": tool_result or {}})
        else:
            st.info("표시할 Agent 실행 Trace가 없습니다.")


st.title("🤖 주차 출입 AI Agent")
st.caption("Agent가 OCR 후보를 검토해 차량 조회 Tool 호출 또는 재촬영 요청을 선택합니다.")
st.info("Agent는 최종 승인 권한이 없습니다. 출입 승인과 차단기 명령은 Backend 정책이 결정합니다.")

captured_image = st.camera_input("번호판 이미지를 촬영하세요")

if captured_image is None:
    st.info("차량 번호판 전체가 선명하게 보이도록 촬영해 주세요.")
else:
    image_bytes = captured_image.getvalue()
    image_fingerprint = hashlib.sha256(image_bytes).hexdigest()

    if st.session_state.get(IMAGE_KEY) != image_fingerprint:
        st.session_state[IMAGE_KEY] = image_fingerprint
        st.session_state.pop(RESULT_KEY, None)

    st.image(image_bytes, caption="분석할 번호판 이미지", use_container_width=True)

    is_processing = st.session_state.get(PROCESSING_KEY, False)
    analyze = st.button(
        "AI Agent로 번호판 분석하기",
        type="primary",
        use_container_width=True,
        disabled=is_processing,
    )

    if analyze and not is_processing:
        st.session_state[PROCESSING_KEY] = True
        try:
            with st.spinner("Agent가 번호판과 차량 출입 권한을 확인하고 있습니다..."):
                st.session_state[RESULT_KEY] = run_parking_agent_entry(
                    image_bytes,
                    filename=captured_image.name or "parking-agent.jpg",
                    content_type=captured_image.type or "image/jpeg",
                )
        except BackendAPIError:
            st.session_state.pop(RESULT_KEY, None)
            st.error("주차 출입 결과를 가져오지 못했습니다.")
            st.info("Backend 서버 상태를 확인한 뒤 번호판을 다시 촬영하거나 잠시 후 재시도해 주세요.")
        except Exception:
            st.session_state.pop(RESULT_KEY, None)
            st.error("번호판 분석 중 문제가 발생했습니다.")
            st.info("이미지를 다시 촬영한 뒤 재시도해 주세요.")
        finally:
            st.session_state[PROCESSING_KEY] = False

result = st.session_state.get(RESULT_KEY)
if result is not None:
    st.divider()
    _render_result(result)
