"""주차 출입 Workflow 페이지 전용 API 클라이언트."""

from typing import Any

from core.api_client import upload


def run_parking_workflow(
    filename: str,
    content: bytes,
    content_type: str,
) -> Any:
    """촬영한 번호판 이미지를 Workflow 입차 API에 전송합니다."""
    return upload(
        "/api/parking/workflow/entry",
        files={"image": (filename, content, content_type)},
        data={"source": "workflow"},
    )
