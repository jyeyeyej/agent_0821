"""메뉴 추천 Router와 Agent 사이의 유스케이스 경계입니다."""

from app.agents.menu_recommendation_agent import run_menu_recommendation_agent
from app.schemas.menu_recommendation import (
    MenuRecommendationRequest,
    MenuRecommendationResponse,
    MenuToolResult,
)


def recommend_menus(request: MenuRecommendationRequest) -> MenuRecommendationResponse:
    """예상하지 못한 내부 오류를 사용자용 응답으로 정제합니다."""

    try:
        return run_menu_recommendation_agent(request)
    except Exception:
        return MenuRecommendationResponse(
            summary="메뉴 추천 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            recommendations=[],
            reasoning=[],
            follow_up_questions=["같은 조건으로 다시 시도할까요?"],
            tool_results=[
                MenuToolResult(
                    success=False,
                    tool_name="menu_recommendation_agent",
                    error={
                        "code": "AGENT_EXECUTION_ERROR",
                        "message": "메뉴 추천을 처리하지 못했습니다.",
                    },
                )
            ],
        )
