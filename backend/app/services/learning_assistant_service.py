"""학습 도우미 Router와 Agent를 연결합니다."""

from app.agents.learning_assistant_agent import run_learning_assistant
from app.schemas.learning_assistant import LearningAssistantRequest, LearningAssistantResponse


def assist_learning(payload: LearningAssistantRequest) -> LearningAssistantResponse:
    return run_learning_assistant(payload)

