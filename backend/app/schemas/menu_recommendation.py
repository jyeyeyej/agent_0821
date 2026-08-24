"""메뉴 추천 Agent의 요청·Tool 인자·응답 계약입니다."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


MealTime = Literal["아침", "점심", "저녁", "야식"]
SpicyLevel = Literal["안 매움", "보통", "매움"]


class MenuBaseModel(BaseModel):
    """camelCase JSON과 snake_case Python 필드를 함께 지원합니다."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )


class MenuRecommendationRequest(MenuBaseModel):
    meal_time: MealTime = Field(alias="mealTime")
    people: int = Field(ge=1, le=20)
    budget: int = Field(ge=1000)
    preferences: list[str] = Field(default_factory=list, max_length=10)
    excluded_foods: list[str] = Field(default_factory=list, max_length=20, alias="excludedFoods")
    allergies: list[str] = Field(default_factory=list, max_length=20)
    spicy_level: SpicyLevel = Field(alias="spicyLevel")
    has_soup: bool | None = Field(default=None, alias="hasSoup")
    quick_meal: bool = Field(default=False, alias="quickMeal")

    @field_validator("preferences", "excluded_foods", "allergies")
    @classmethod
    def validate_text_items(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = value.strip()
            if not cleaned:
                raise ValueError("빈 문자열은 입력할 수 없습니다.")
            key = cleaned.casefold()
            if key not in seen:
                normalized.append(cleaned)
                seen.add(key)
        return normalized


class MenuSearchArgs(MenuBaseModel):
    meal_time: MealTime = Field(alias="mealTime")
    people: int = Field(ge=1, le=20)
    budget: int = Field(ge=1000)
    preferences: list[str] = Field(default_factory=list, max_length=10)
    excluded_foods: list[str] = Field(default_factory=list, max_length=20, alias="excludedFoods")
    spicy_level: SpicyLevel = Field(alias="spicyLevel")
    has_soup: bool | None = Field(default=None, alias="hasSoup")
    quick_meal: bool = Field(default=False, alias="quickMeal")


class DietaryCheckArgs(MenuBaseModel):
    candidate_ids: list[str] = Field(default_factory=list, max_length=20, alias="candidateIds")
    excluded_foods: list[str] = Field(default_factory=list, max_length=20, alias="excludedFoods")
    allergies: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("candidate_ids", "excluded_foods", "allergies")
    @classmethod
    def reject_blank_items(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("빈 문자열은 입력할 수 없습니다.")
        return values


class MenuCandidate(MenuBaseModel):
    menu_id: str = Field(min_length=1, alias="menuId")
    name: str = Field(min_length=1)
    total_price: int = Field(ge=0, alias="totalPrice")
    score: int = Field(ge=0, le=100)
    matched_conditions: list[str] = Field(default_factory=list, alias="matchedConditions")


class MenuRecommendationItem(MenuBaseModel):
    menu_id: str = Field(min_length=1, alias="menuId")
    name: str = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=500)
    total_price: int = Field(ge=0, alias="totalPrice")
    nutrition_note: str = Field(min_length=1, max_length=500, alias="nutritionNote")
    is_alternative: bool = Field(alias="isAlternative")


class MenuToolResult(MenuBaseModel):
    success: bool
    tool_name: str = Field(min_length=1, alias="toolName")
    data: Any | None = None
    error: dict[str, Any] | None = None


class MenuRecommendationResponse(MenuBaseModel):
    agent_type: Literal["menu_recommendation"] = Field(
        default="menu_recommendation",
        alias="agentType",
    )
    summary: str = Field(min_length=1, max_length=1000)
    recommendations: list[MenuRecommendationItem] = Field(default_factory=list, max_length=5)
    reasoning: list[str] = Field(default_factory=list, max_length=10)
    follow_up_questions: list[str] = Field(
        default_factory=list,
        max_length=5,
        alias="followUpQuestions",
    )
    tool_results: list[MenuToolResult] = Field(
        default_factory=list,
        max_length=2,
        alias="toolResults",
    )
