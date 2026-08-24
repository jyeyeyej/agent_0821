"""사용자의 식사 조건으로 메뉴 후보를 검색하는 읽기 전용 Tool입니다."""

from typing import Any

from app.schemas.menu_recommendation import MenuSearchArgs


MENUS: list[dict[str, Any]] = [
    {
        "menu_id": "menu-001",
        "name": "소고기 불고기 정식",
        "category": "한식",
        "meal_times": ["점심", "저녁"],
        "price_per_person": 14000,
        "tags": ["한식", "따뜻한 음식", "고기"],
        "ingredients": ["소고기", "양파", "마늘", "간장", "참깨"],
        "spicy_level": "보통",
        "has_soup": False,
        "quick_meal": False,
    },
    {
        "menu_id": "menu-002",
        "name": "닭고기 된장찌개 정식",
        "category": "한식",
        "meal_times": ["점심", "저녁"],
        "price_per_person": 13000,
        "tags": ["한식", "따뜻한 음식", "국물"],
        "ingredients": ["닭고기", "된장", "두부", "애호박", "대파"],
        "spicy_level": "보통",
        "has_soup": True,
        "quick_meal": False,
    },
    {
        "menu_id": "menu-003",
        "name": "나물 비빔밥",
        "category": "한식",
        "meal_times": ["아침", "점심", "저녁"],
        "price_per_person": 10000,
        "tags": ["한식", "채소", "간편식"],
        "ingredients": ["쌀", "시금치", "콩나물", "당근", "달걀", "고추장"],
        "spicy_level": "보통",
        "has_soup": False,
        "quick_meal": True,
    },
    {
        "menu_id": "menu-004",
        "name": "돼지고기 김치찌개",
        "category": "한식",
        "meal_times": ["점심", "저녁", "야식"],
        "price_per_person": 12000,
        "tags": ["한식", "따뜻한 음식", "국물", "매운 음식"],
        "ingredients": ["돼지고기", "김치", "두부", "대파", "고춧가루"],
        "spicy_level": "매움",
        "has_soup": True,
        "quick_meal": False,
    },
    {
        "menu_id": "menu-005",
        "name": "새우 달걀 볶음밥",
        "category": "중식",
        "meal_times": ["점심", "저녁"],
        "price_per_person": 11000,
        "tags": ["중식", "따뜻한 음식", "간편식"],
        "ingredients": ["쌀", "새우", "달걀", "대파", "간장"],
        "spicy_level": "안 매움",
        "has_soup": False,
        "quick_meal": True,
    },
]


SPICY_RANK = {"안 매움": 0, "보통": 1, "매움": 2}


def _contains_term(menu: dict[str, Any], term: str) -> bool:
    searchable = [
        menu["name"],
        menu["category"],
        *menu["tags"],
        *menu["ingredients"],
    ]
    needle = term.casefold()
    return any(needle in value.casefold() for value in searchable)


def _score_menu(menu: dict[str, Any], args: MenuSearchArgs, total_price: int) -> tuple[int, list[str]]:
    matched_conditions = [args.meal_time]
    score = 35

    for preference in args.preferences:
        if _contains_term(menu, preference):
            matched_conditions.append(preference)
            score += 18

    if menu["spicy_level"] == args.spicy_level:
        score += 10
        matched_conditions.append(args.spicy_level)

    remaining_budget_ratio = (args.budget - total_price) / args.budget
    score += max(0, round(15 * remaining_budget_ratio))

    if args.has_soup is not None:
        score += 10
        matched_conditions.append("국물 있음" if args.has_soup else "국물 없음")

    if menu["quick_meal"] == args.quick_meal:
        score += 5

    return min(score, 100), list(dict.fromkeys(matched_conditions))


def search_menus(args: MenuSearchArgs) -> dict:
    """조건을 임의로 완화하지 않고 적합한 메뉴를 결정적으로 정렬합니다."""

    candidates: list[dict[str, Any]] = []
    requested_spicy_rank = SPICY_RANK[args.spicy_level]

    for menu in MENUS:
        total_price = menu["price_per_person"] * args.people
        if args.meal_time not in menu["meal_times"]:
            continue
        if total_price > args.budget:
            continue
        if any(_contains_term(menu, item) for item in args.excluded_foods):
            continue
        if SPICY_RANK[menu["spicy_level"]] > requested_spicy_rank:
            continue
        if args.has_soup is not None and menu["has_soup"] != args.has_soup:
            continue
        if menu["quick_meal"] != args.quick_meal:
            continue

        score, matched_conditions = _score_menu(menu, args, total_price)
        candidates.append(
            {
                "menuId": menu["menu_id"],
                "name": menu["name"],
                "totalPrice": total_price,
                "score": score,
                "matchedConditions": matched_conditions,
            }
        )

    candidates.sort(key=lambda item: (-item["score"], item["totalPrice"], item["menuId"]))
    return {
        "matchedCount": len(candidates),
        "candidates": candidates,
        "source": "python_mock",
    }
