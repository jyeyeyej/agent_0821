"""학습 도우미 Agent API를 제공합니다."""

from fastapi import APIRouter, HTTPException

from app.schemas.learning_assistant import LearningAssistantRequest, LearningAssistantResponse
from app.services.learning_assistant_service import assist_learning


learning_assistant_router = APIRouter(tags=["학습 도우미 Agent"])


@learning_assistant_router.post(
    "/api/learning/assist",
    response_model=LearningAssistantResponse,
    response_model_by_alias=True,
)
def create_learning_assistance(payload: LearningAssistantRequest) -> LearningAssistantResponse:
    try:
        return assist_learning(payload)
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail={"code": "AGENT_EXECUTION_ERROR", "message": "학습 도우미를 실행하지 못했습니다."},
        ) from error

