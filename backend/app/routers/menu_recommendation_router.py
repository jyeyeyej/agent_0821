"""메뉴 추천 AI Agent의 FastAPI Endpoint입니다."""

from fastapi import APIRouter

from app.schemas.menu_recommendation import (
    MenuRecommendationRequest,
    MenuRecommendationResponse,
)
from app.services.menu_recommendation_service import recommend_menus


menu_recommendation_router = APIRouter(tags=["메뉴 추천 Agent"])


@menu_recommendation_router.post(
    "/api/menu/recommend",
    response_model=MenuRecommendationResponse,
    status_code=200,
)
def recommend_menu(payload: MenuRecommendationRequest) -> MenuRecommendationResponse:
    """검증된 메뉴 조건을 Service에 전달하고 구조화 응답을 반환합니다."""

    return recommend_menus(payload)
