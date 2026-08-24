"""주차 출입 AI Agent API 전용 클라이언트."""

from typing import Any

from core.api_client import BackendAPIError, upload


PARKING_AGENT_ENTRY_PATH = "/api/parking/agent/entry"


def run_parking_agent_entry(
    image: bytes,
    *,
    filename: str = "parking-agent.jpg",
    content_type: str = "image/jpeg",
) -> dict[str, Any]:
    """촬영한 번호판 이미지를 AI Agent 입차 API로 전송한다."""
    result = upload(
        PARKING_AGENT_ENTRY_PATH,
        files={"image": (filename, image, content_type)},
        data={"source": "agent"},
    )
    if not isinstance(result, dict):
        raise BackendAPIError("백엔드가 올바른 주차 출입 결과를 반환하지 않았습니다.")
    return result
