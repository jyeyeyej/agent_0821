"""고정 Workflow로 차량 출입을 판단하는 Frontend A 화면."""

import streamlit as st

from clients.parking_workflow_client import run_parking_workflow
from core.api_client import BackendAPIError


def render_result(result: dict) -> None:
    """공통 주차 API 응답을 사용자용 결과 화면으로 표시합니다."""
    st.subheader("출입 판단 결과")
    if result.get("approved"):
        st.success("출입이 승인되었습니다.")
    else:
        st.error("출입이 승인되지 않았습니다. 차량 등록 또는 출입 권한을 확인해 주세요.")

    first, second, third = st.columns(3)
    first.metric("인식 번호판", result.get("recognized_plate_number") or "인식 실패")
    confidence = result.get("recognition_confidence")
    second.metric("OCR 신뢰도", f"{float(confidence):.2f}" if confidence is not None else "-")
    third.metric("차단기 명령", result.get("gate_command", "keep_closed"))
    st.write("판단 사유:", result.get("reason", "판단 사유가 없습니다."))

    if result.get("trace"):
        with st.expander("Workflow 처리 단계"):
            st.json(result["trace"])


st.title("🚗 주차 출입 Workflow")
st.caption("이미지 캡처 → 번호판 인식 → 차량 DB 조회 → Backend 정책 순서로 출입을 판단합니다.")
st.info("등록·활성 차량만 Backend 정책이 승인합니다. 이 화면은 실제 차단기를 제어하지 않습니다.")

image = st.camera_input("번호판 이미지를 촬영하세요")
if image is None:
    st.info("브라우저 카메라 권한을 허용한 뒤 차량 번호판을 촬영해 주세요.")
else:
    st.image(image, caption="촬영한 번호판 이미지")
    if st.button("Workflow 출입 확인", type="primary"):
        try:
            with st.spinner("번호판을 인식하고 차량 등록 정보를 확인하는 중입니다..."):
                st.session_state["parking_workflow_result"] = run_parking_workflow(
                    image.name,
                    image.getvalue(),
                    image.type or "image/jpeg",
                )
        except BackendAPIError as error:
            st.error(f"출입 확인 요청에 실패했습니다. 다시 촬영하거나 서버 상태를 확인해 주세요.\n\n{error}")

result = st.session_state.get("parking_workflow_result")
if isinstance(result, dict):
    st.divider()
    render_result(result)
