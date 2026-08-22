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

navigation = st.navigation([menu, learning])
navigation.run()
