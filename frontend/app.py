import streamlit as st


st.set_page_config(page_title="AI Agent 도우미", page_icon="🤖", layout="wide")

menu = st.Page(
    "app_pages/01_menu_recommendation.py",
    title="메뉴 추천 Agent",
    icon="🍽️",
    default=True,
)
learning = st.Page(
    "app_pages/02_learning_assistant.py",
    title="학습 도우미 Agent",
    icon="📚",
)
parking_workflow = st.Page(
    "app_pages/03_parking_workflow.py",
    title="주차 출입 Workflow",
    icon="🚗",
    url_path="parking_workflow",
)
parking_agent = st.Page(
    "app_pages/04_parking_agent.py",
    title="주차 출입 AI Agent",
    icon="🤖",
    url_path="parking_agent",
)

navigation = st.navigation([menu, learning, parking_workflow, parking_agent])
navigation.run()
