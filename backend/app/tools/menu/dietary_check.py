"""메뉴 후보의 알레르기·제외 음식·영양 정보를 검증하는 Tool입니다."""

from typing import Any

from app.schemas.menu_recommendation import DietaryCheckArgs


MENU_NUTRITION: dict[str, dict[str, Any]] = {
    "menu-001": {
        "ingredients": ["소고기", "양파", "마늘", "간장", "참깨"],
        "allergens": ["대두", "참깨"],
        "calories_kcal": 720,
        "protein_g": 38,
        "nutrition_note": "단백질이 풍부하며 간장과 참깨 알레르기 여부를 확인하세요.",
    },
    "menu-002": {
        "ingredients": ["닭고기", "된장", "두부", "애호박", "대파"],
        "allergens": ["대두"],
        "calories_kcal": 650,
        "protein_g": 35,
        "nutrition_note": "닭고기와 두부로 단백질을 보충할 수 있습니다.",
    },
    "menu-003": {
        "ingredients": ["쌀", "시금치", "콩나물", "당근", "달걀", "고추장"],
        "allergens": ["달걀", "대두"],
        "calories_kcal": 560,
        "protein_g": 18,
        "nutrition_note": "여러 채소를 포함하며 달걀과 대두 알레르기 여부를 확인하세요.",
    },
    "menu-004": {
        "ingredients": ["돼지고기", "김치", "두부", "대파", "고춧가루"],
        "allergens": ["대두"],
        "calories_kcal": 680,
        "protein_g": 32,
        "nutrition_note": "국물의 나트륨 섭취량을 고려하세요.",
    },
    "menu-005": {
        "ingredients": ["쌀", "새우", "달걀", "대파", "간장"],
        "allergens": ["갑각류", "달걀", "대두"],
        "calories_kcal": 610,
        "protein_g": 24,
        "nutrition_note": "갑각류와 달걀 알레르기 여부를 반드시 확인하세요.",
    },
}


def _matching_values(requested: list[str], available: list[str]) -> list[str]:
    matches: list[str] = []
    for request_value in requested:
        needle = request_value.casefold()
        if any(needle in value.casefold() or value.casefold() in needle for value in available):
            matches.append(request_value)
    return matches


def check_dietary_conditions(args: DietaryCheckArgs) -> dict:
    """안전 후보와 제외 후보를 분리하고 제외 사유를 반환합니다."""

    safe_candidates: list[dict[str, Any]] = []
    excluded_candidates: list[dict[str, Any]] = []

    for menu_id in args.candidate_ids:
        nutrition = MENU_NUTRITION.get(menu_id)
        if nutrition is None:
            excluded_candidates.append(
                {
                    "menuId": menu_id,
                    "reasons": ["영양·알레르기 정보를 찾을 수 없습니다."],
                    "errorCode": "MOCK_DATA_NOT_FOUND",
                }
            )
            continue

        allergy_conflicts = _matching_values(args.allergies, nutrition["allergens"])
        excluded_food_conflicts = _matching_values(args.excluded_foods, nutrition["ingredients"])
        reasons: list[str] = []
        if allergy_conflicts:
            reasons.append(f"알레르기 충돌: {', '.join(allergy_conflicts)}")
        if excluded_food_conflicts:
            reasons.append(f"제외 음식 포함: {', '.join(excluded_food_conflicts)}")

        if reasons:
            excluded_candidates.append({"menuId": menu_id, "reasons": reasons})
            continue

        safe_candidates.append(
            {
                "menuId": menu_id,
                "caloriesKcal": nutrition["calories_kcal"],
                "proteinG": nutrition["protein_g"],
                "nutritionNote": nutrition["nutrition_note"],
            }
        )

    return {
        "safeCount": len(safe_candidates),
        "safeCandidates": safe_candidates,
        "excludedCandidates": excluded_candidates,
        "source": "python_mock",
    }
