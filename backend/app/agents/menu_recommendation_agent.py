"""메뉴 검색과 식단 검증 Tool을 조합하는 메뉴 추천 Agent입니다."""

from typing import Any

from app.schemas.menu_recommendation import (
    DietaryCheckArgs,
    MenuRecommendationItem,
    MenuRecommendationRequest,
    MenuRecommendationResponse,
    MenuSearchArgs,
    MenuToolResult,
)
from app.tools.executor import execute_tool_safely


MENU_TOOL_NAMES = ("search_menus", "check_dietary_conditions")


def _safe_error(error: dict[str, Any] | None) -> dict[str, Any]:
    code = str((error or {}).get("code", "TOOL_EXECUTION_ERROR"))
    messages = {
        "TOOL_NOT_ALLOWED": "메뉴 Tool이 아직 공통 Registry에 연결되지 않았습니다.",
        "TOOL_VALIDATION_ERROR": "메뉴 Tool 입력값을 확인해 주세요.",
        "TOOL_EXECUTION_ERROR": "메뉴 정보를 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.",
        "MOCK_DATA_NOT_FOUND": "조건에 맞는 메뉴 정보를 찾지 못했습니다.",
    }
    safe_error: dict[str, Any] = {"code": code, "message": messages.get(code, messages["TOOL_EXECUTION_ERROR"])}
    if code == "TOOL_VALIDATION_ERROR" and isinstance((error or {}).get("details"), list):
        safe_error["details"] = (error or {})["details"]
    return safe_error


def _to_tool_result(result: Any) -> MenuToolResult:
    return MenuToolResult(
        success=result.success,
        tool_name=result.tool_name,
        data=result.data if result.success else None,
        error=None if result.success else _safe_error(result.error),
    )


def _failure_response(tool_results: list[MenuToolResult]) -> MenuRecommendationResponse:
    return MenuRecommendationResponse(
        summary="메뉴 추천을 완료하지 못했습니다. 입력 조건을 확인한 뒤 다시 시도해 주세요.",
        recommendations=[],
        reasoning=["등록된 안전 실행 경로에서 메뉴 Tool을 실행했습니다."],
        follow_up_questions=["같은 조건으로 다시 시도할까요?"],
        tool_results=tool_results,
    )


def _empty_response(tool_results: list[MenuToolResult]) -> MenuRecommendationResponse:
    return MenuRecommendationResponse(
        summary="모든 조건을 만족하는 안전한 메뉴를 찾지 못했습니다.",
        recommendations=[],
        reasoning=[
            "예산과 식사 조건을 임의로 완화하지 않았습니다.",
            "알레르기와 제외 음식 조건을 통과한 메뉴만 추천 대상으로 확인했습니다.",
        ],
        follow_up_questions=[
            "예산을 조금 늘려 다시 찾아볼까요?",
            "국물 또는 간편식 조건을 바꿔 볼까요?",
        ],
        tool_results=tool_results,
    )


def _recommendation_reason(candidate: dict[str, Any], is_alternative: bool) -> str:
    matched = candidate.get("matchedConditions", [])
    condition_text = ", ".join(matched[:4]) if matched else "입력한 식사 조건"
    prefix = "대체 메뉴로" if is_alternative else "가장 적합한 메뉴로"
    return f"{condition_text} 조건과 잘 맞아 {prefix} 선정했습니다."


def run_menu_recommendation_agent(
    request: MenuRecommendationRequest,
) -> MenuRecommendationResponse:
    """두 Tool을 Allowlist 안전 실행기로 호출하고 결정적인 응답을 만듭니다."""

    search_args = MenuSearchArgs(
        meal_time=request.meal_time,
        people=request.people,
        budget=request.budget,
        preferences=request.preferences,
        excluded_foods=request.excluded_foods,
        spicy_level=request.spicy_level,
        has_soup=request.has_soup,
        quick_meal=request.quick_meal,
    )
    raw_search_result = execute_tool_safely(
        MENU_TOOL_NAMES[0],
        search_args.model_dump(mode="json", by_alias=False),
    )
    search_result = _to_tool_result(raw_search_result)
    tool_results = [search_result]
    if not search_result.success:
        return _failure_response(tool_results)

    search_data = search_result.data or {}
    candidates = search_data.get("candidates", [])
    candidate_ids = [candidate["menuId"] for candidate in candidates]

    dietary_args = DietaryCheckArgs(
        candidate_ids=candidate_ids,
        excluded_foods=request.excluded_foods,
        allergies=request.allergies,
    )
    raw_dietary_result = execute_tool_safely(
        MENU_TOOL_NAMES[1],
        dietary_args.model_dump(mode="json", by_alias=False),
    )
    dietary_result = _to_tool_result(raw_dietary_result)
    tool_results.append(dietary_result)
    if not dietary_result.success:
        return _failure_response(tool_results)

    dietary_data = dietary_result.data or {}
    safe_by_id = {
        candidate["menuId"]: candidate
        for candidate in dietary_data.get("safeCandidates", [])
    }
    safe_candidates = [candidate for candidate in candidates if candidate["menuId"] in safe_by_id]
    if not safe_candidates:
        return _empty_response(tool_results)

    recommendations: list[MenuRecommendationItem] = []
    for index, candidate in enumerate(safe_candidates[:3]):
        nutrition = safe_by_id[candidate["menuId"]]
        is_alternative = index > 0
        recommendations.append(
            MenuRecommendationItem(
                menu_id=candidate["menuId"],
                name=candidate["name"],
                reason=_recommendation_reason(candidate, is_alternative),
                total_price=candidate["totalPrice"],
                nutrition_note=nutrition["nutritionNote"],
                is_alternative=is_alternative,
            )
        )

    primary = recommendations[0]
    return MenuRecommendationResponse(
        summary=f"{request.people}인 {request.meal_time} 메뉴로 {primary.name}을(를) 추천합니다.",
        recommendations=recommendations,
        reasoning=[
            "식사 시간, 인원, 예산과 세부 조건으로 후보를 검색했습니다.",
            "알레르기와 제외 음식 충돌 여부를 확인했습니다.",
            "조건 적합도와 가격 순으로 주 추천과 대체 메뉴를 구성했습니다.",
        ],
        follow_up_questions=[],
        tool_results=tool_results,
    )
