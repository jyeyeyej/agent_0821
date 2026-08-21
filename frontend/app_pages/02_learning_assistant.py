from typing import Any

import streamlit as st

from clients.agent_client import run_learning_assistant
from core.api_client import BackendAPIError


def _render_item(item: Any) -> None:
    """응답 항목의 형태가 달라도 사용자에게 안전하게 표시합니다."""
    if isinstance(item, dict):
        title = item.get("title") or item.get("name") or item.get("topic")
        if title:
            st.markdown(f"#### {title}")

        details = {key: value for key, value in item.items() if key not in {"title", "name", "topic"}}
        if details:
            st.json(details)
    elif isinstance(item, list):
        for nested_item in item:
            _render_item(nested_item)
    else:
        st.write(item)


def _render_list(title: str, items: Any) -> None:
    if not items:
        return

    st.subheader(title)
    values = items if isinstance(items, list) else [items]
    for index, item in enumerate(values, start=1):
        if isinstance(item, str):
            st.markdown(f"{index}. {item}")
        else:
            with st.container(border=True):
                _render_item(item)


def _render_result(result: Any) -> None:
    if not isinstance(result, dict):
        st.warning("백엔드 응답 형식을 확인할 수 없습니다. 다시 시도해 주세요.")
        return

    summary = result.get("summary")
    recommendations = result.get("recommendations", [])
    reasoning = result.get("reasoning", [])
    follow_up_questions = result.get("followUpQuestions", [])
    tool_results = result.get("toolResults", [])

    if not any((summary, recommendations, reasoning, follow_up_questions, tool_results)):
        st.warning("표시할 학습 결과가 없습니다. 입력을 확인하고 다시 시도해 주세요.")
        return

    st.subheader("맞춤 학습 안내")
    if summary:
        st.success(summary)
    else:
        st.info("응답 요약이 없습니다.")

    _render_list("학습 계획과 추천", recommendations)
    _render_list("학습 구성 이유", reasoning)
    _render_list("다음 학습을 위한 질문", follow_up_questions)

    with st.expander("Agent Tool 실행 결과", expanded=False):
        if tool_results:
            st.json(tool_results)
        else:
            st.info("표시할 Tool 실행 결과가 없습니다.")


st.title("📚 학습 도우미 Agent")
st.caption("학습 목표와 현재 수준에 맞는 계획, 핵심 개념, 예제와 연습 문제를 제공합니다.")

with st.form("learning_assistant_form"):
    subject = st.text_input("과목", value="Python")
    goal = st.text_area("학습 목표", value="반복문 기초 이해")

    level_column, time_column = st.columns(2)
    with level_column:
        level = st.selectbox("현재 수준", ["초급", "중급", "고급"], index=0)
    with time_column:
        study_minutes = st.number_input(
            "학습 시간(분)",
            min_value=10,
            max_value=480,
            value=30,
            step=10,
        )

    learning_style = st.selectbox(
        "선호 학습 방식",
        ["예제와 문제 풀이", "개념 설명 중심", "단계별 실습"],
        index=0,
    )
    submitted = st.form_submit_button("학습 계획 만들기", type="primary")

if submitted:
    cleaned_subject = subject.strip()
    cleaned_goal = goal.strip()

    if not cleaned_subject or not cleaned_goal:
        st.warning("과목과 학습 목표를 모두 입력해 주세요.")
    else:
        payload = {
            "subject": cleaned_subject,
            "goal": cleaned_goal,
            "level": level,
            "studyMinutes": int(study_minutes),
            "learningStyle": learning_style,
        }

        try:
            with st.spinner("맞춤 학습 계획을 만들고 있습니다..."):
                response = run_learning_assistant(payload)
            _render_result(response)
        except BackendAPIError as error:
            st.error(str(error))
            st.info("백엔드 서버 실행 상태를 확인한 뒤 다시 시도해 주세요.")
