"""학습 계획과 퀴즈 Tool을 순서대로 실행하는 학습 도우미 Agent입니다."""

from typing import Any

from app.schemas.learning_assistant import (
    LearningAssistantRequest,
    LearningAssistantResponse,
    LearningRecommendation,
    LearningToolResult,
    QuizResult,
    StudyPlanResult,
)
from app.tools.executor import execute_tool_safely
from app.tools.registry import get_tool_definitions


LEARNING_AGENT_NAME = "learning_assistant"
LEARNING_TOOL_NAMES = {"create_study_plan", "create_quiz"}


def get_learning_tools() -> list[dict[str, Any]]:
    """학습 Agent에 허용된 Tool 두 개만 반환합니다."""
    return get_tool_definitions(LEARNING_TOOL_NAMES)


def _as_learning_tool_result(result) -> LearningToolResult:
    return LearningToolResult(
        success=result.success,
        toolName=result.tool_name,
        data=result.data,
        error=result.error,
    )


def run_learning_assistant(payload: LearningAssistantRequest) -> LearningAssistantResponse:
    """계획 생성 → 퀴즈 생성 순서의 결정적 Agent Cycle을 실행합니다."""
    plan_result = execute_tool_safely(
        "create_study_plan",
        payload.model_dump(by_alias=True),
    )
    tool_results = [_as_learning_tool_result(plan_result)]
    if not plan_result.success:
        return LearningAssistantResponse(
            summary="학습 계획을 생성하지 못했습니다. 입력값을 확인해 주세요.",
            toolResults=tool_results,
        )

    plan_data = plan_result.data or {}
    if not plan_data.get("found", False):
        question = plan_data.get("followUpQuestion", "지원하는 과목과 학습 목표를 다시 입력해 주세요.")
        return LearningAssistantResponse(
            summary="요청에 맞는 학습 콘텐츠를 찾지 못했습니다.",
            followUpQuestions=[question],
            toolResults=tool_results,
        )

    plan = StudyPlanResult.model_validate(
        {key: value for key, value in plan_data.items() if key != "found"}
    )
    quiz_result = execute_tool_safely(
        "create_quiz",
        {
            "subject": plan.subject,
            "topic": plan.topic,
            "level": plan.level,
            "questionCount": 3,
            "answers": {},
        },
    )
    tool_results.append(_as_learning_tool_result(quiz_result))
    if not quiz_result.success:
        return LearningAssistantResponse(
            summary="학습 계획은 만들었지만 퀴즈를 생성하지 못했습니다.",
            followUpQuestions=["잠시 후 퀴즈 생성을 다시 시도해 주세요."],
            toolResults=tool_results,
        )

    quiz = QuizResult.model_validate(quiz_result.data)
    recommendation = LearningRecommendation(
        title=plan.title,
        totalMinutes=plan.total_minutes,
        steps=plan.steps,
        quiz=quiz.items,
        nextTopic=plan.next_topic,
    )
    return LearningAssistantResponse(
        summary=f"{plan.subject} {plan.topic}의 개념부터 문제 풀이까지 {plan.total_minutes}분 학습 계획을 만들었습니다.",
        recommendations=[recommendation],
        reasoning=[
            f"{plan.level} 수준을 적용했습니다.",
            f"전체 학습 시간을 {plan.total_minutes}분으로 구성했습니다.",
            f"{payload.learning_style} 방식으로 배치했습니다.",
        ],
        toolResults=tool_results,
    )
