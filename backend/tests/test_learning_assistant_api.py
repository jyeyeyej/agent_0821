from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.agents.learning_assistant_agent import get_learning_tools
from app.main import app
from app.schemas.learning_assistant import LearningAssistantRequest, QuizArgs, StudyPlanArgs
from app.tools.learning import create_quiz, create_study_plan


client = TestClient(app)
HAPPY_CASE = {
    "subject": "Python",
    "goal": "반복문 기초 이해",
    "level": "초급",
    "studyMinutes": 30,
    "learningStyle": "예제와 문제 풀이",
    "difficultConcepts": [],
}


def test_learning_happy_case_runs_both_tools() -> None:
    response = client.post("/api/learning/assist", json=HAPPY_CASE)
    assert response.status_code == 200
    body = response.json()
    assert body["agentType"] == "learning_assistant"
    assert [item["toolName"] for item in body["toolResults"]] == ["create_study_plan", "create_quiz"]
    recommendation = body["recommendations"][0]
    assert sum(step["minutes"] for step in recommendation["steps"]) == 30
    assert all(item["answer"] and item["explanation"] for item in recommendation["quiz"])


def test_learning_agent_only_exposes_learning_tools() -> None:
    assert {tool["name"] for tool in get_learning_tools()} == {"create_study_plan", "create_quiz"}


def test_request_rejects_invalid_minutes_level_and_extra_fields() -> None:
    for patch in (
        {"studyMinutes": 9},
        {"studyMinutes": 241},
        {"level": "전문가"},
        {"unknown": True},
    ):
        with pytest.raises(ValidationError):
            LearningAssistantRequest.model_validate(HAPPY_CASE | patch)


def test_study_plan_total_matches_requested_minutes() -> None:
    result = create_study_plan(StudyPlanArgs.model_validate(HAPPY_CASE | {"studyMinutes": 31}))
    assert result["found"] is True
    assert sum(step["minutes"] for step in result["steps"]) == 31


def test_unsupported_subject_returns_follow_up_without_quiz() -> None:
    response = client.post("/api/learning/assist", json=HAPPY_CASE | {"subject": "수학"})
    assert response.status_code == 200
    body = response.json()
    assert body["recommendations"] == []
    assert body["followUpQuestions"]
    assert [item["toolName"] for item in body["toolResults"]] == ["create_study_plan"]


def test_quiz_is_unique_and_scores_only_submitted_answers() -> None:
    args = QuizArgs.model_validate(
        {
            "subject": "Python",
            "topic": "반복문",
            "level": "초급",
            "questionCount": 3,
            "answers": {"python-loop-q001": "3번"},
        }
    )
    result = create_quiz(args)
    ids = [item["questionId"] for item in result["items"]]
    assert len(ids) == len(set(ids)) == 3
    assert result["score"] == 100
    assert len(result["gradingResults"]) == 1

