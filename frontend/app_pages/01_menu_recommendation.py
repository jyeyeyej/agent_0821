"""사용자 조건에 맞는 메뉴를 추천하는 Agent 화면."""

from typing import Any

import streamlit as st

from clients.agent_client import run_menu_recommendation
from core.api_client import BackendAPIError


def parse_csv(value: str) -> list[str]:
    """쉼표로 입력된 조건을 API용 문자열 목록으로 바꾼다."""
    return [item.strip() for item in value.split(",") if item.strip()]


def show_value(label: str, value: Any) -> None:
    """응답의 문자열, 목록, 객체 값을 안전하게 화면에 표시한다."""
    if value in (None, "", [], {}):
        return
    st.markdown(f"**{label}**")
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                st.write(" · ".join(f"{key}: {item_value}" for key, item_value in item.items()))
            else:
                st.write(f"- {item}")
    elif isinstance(value, dict):
        st.json(value)
    else:
        st.write(value)


def show_recommendations(recommendations: Any) -> None:
    """추천 결과가 다양한 형태여도 읽을 수 있게 렌더링한다."""
    if not recommendations:
        st.info("조건에 맞는 추천 결과가 없습니다. 예산 또는 선호 조건을 바꿔 다시 시도해 주세요.")
        return

    st.subheader("추천 메뉴")
    items = recommendations if isinstance(recommendations, list) else [recommendations]
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            st.write(f"{index}. {item}")
            continue

        name = item.get("name") or item.get("menu") or item.get("title") or f"추천 메뉴 {index}"
        st.markdown(f"#### {index}. {name}")
        show_value("추천 이유", item.get("reason") or item.get("reasons"))
        show_value("예상 가격", item.get("price") or item.get("priceRange"))
        show_value("영양·식단 참고", item.get("nutrition") or item.get("dietaryInfo"))
        show_value("대체 메뉴", item.get("alternatives") or item.get("alternativeMenus"))


def show_result(result: Any) -> None:
    """공통 Agent 응답을 메뉴 추천 화면에 표시한다."""
    if not isinstance(result, dict):
        st.warning("추천 결과 형식을 읽을 수 없습니다. 잠시 후 다시 시도해 주세요.")
        return

    summary = result.get("summary")
    if summary:
        st.subheader("추천 요약")
        st.write(summary)

    show_recommendations(result.get("recommendations"))
    show_value("대체 메뉴", result.get("alternatives") or result.get("alternativeMenus"))
    show_value("추천 근거", result.get("reasoning"))
    show_value("다음 질문", result.get("followUpQuestions"))

    tool_results = result.get("toolResults")
    if tool_results:
        with st.expander("Tool 실행 결과"):
            st.json(tool_results)


st.title("🍽️ 메뉴 추천 Agent")
st.caption("식사 상황과 선호 조건을 입력하면 맞춤 메뉴를 추천해 드립니다.")

with st.form("menu_recommendation_form"):
    left, right = st.columns(2)
    with left:
        meal_time = st.selectbox("식사 시간", ["아침", "점심", "저녁", "야식"], index=2)
        people = st.number_input("인원", min_value=1, value=2, step=1)
        budget = st.number_input("총 예산 (원)", min_value=0, value=30000, step=1000)
        spicy_level = st.selectbox("맵기", ["안 매운", "보통", "매운"], index=1)
    with right:
        preferences = st.text_input("선호 음식 (쉼표로 구분)", value="한식, 따뜻한 음식")
        excluded_foods = st.text_input("제외 음식 (쉼표로 구분)")
        allergies = st.text_input("알레르기·식단 제한 (쉼표로 구분)")

    submitted = st.form_submit_button("메뉴 추천받기", type="primary", use_container_width=True)

if submitted:
    payload = {
        "mealTime": meal_time,
        "people": int(people),
        "budget": int(budget),
        "preferences": parse_csv(preferences),
        "excludedFoods": parse_csv(excluded_foods),
        "allergies": parse_csv(allergies),
        "spicyLevel": spicy_level,
    }
    try:
        with st.spinner("메뉴를 추천하는 중입니다..."):
            st.session_state["menu_recommendation_result"] = run_menu_recommendation(payload)
    except BackendAPIError as error:
        st.error(f"메뉴 추천을 가져오지 못했습니다. 서버 실행 상태를 확인한 뒤 다시 시도해 주세요.\n\n{error}")
    except Exception:
        st.error("메뉴 추천 처리 중 문제가 발생했습니다. 입력 조건을 확인한 뒤 다시 시도해 주세요.")

result = st.session_state.get("menu_recommendation_result")
if result is not None:
    st.divider()
    show_result(result)
