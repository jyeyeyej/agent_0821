"""학습 도우미 Agent의 요청, Tool arguments와 응답 계약입니다."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LearningModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class LearningAssistantRequest(LearningModel):
    subject: str = Field(min_length=1, max_length=100)
    goal: str = Field(min_length=1, max_length=500)
    level: Literal["초급", "중급", "고급"]
    study_minutes: int = Field(alias="studyMinutes", ge=10, le=240)
    learning_style: str = Field(alias="learningStyle", min_length=1, max_length=100)
    difficult_concepts: list[str] = Field(alias="difficultConcepts", default_factory=list, max_length=10)


class StudyPlanArgs(LearningAssistantRequest):
    pass


class QuizArgs(LearningModel):
    subject: str = Field(min_length=1, max_length=100)
    topic: str = Field(min_length=1, max_length=100)
    level: Literal["초급", "중급", "고급"]
    question_count: int = Field(alias="questionCount", default=3, ge=1, le=5)
    answers: dict[str, str] = Field(default_factory=dict)


class StudyPlanStep(LearningModel):
    order: int = Field(ge=1)
    title: str = Field(min_length=1)
    minutes: int = Field(ge=1)
    summary: str = Field(min_length=1)
    example: str = ""


class StudyPlanResult(LearningModel):
    title: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    level: Literal["초급", "중급", "고급"]
    total_minutes: int = Field(alias="totalMinutes", ge=1)
    steps: list[StudyPlanStep] = Field(min_length=1)
    next_topic: str = Field(alias="nextTopic", min_length=1)

    @model_validator(mode="after")
    def validate_total_minutes(self) -> "StudyPlanResult":
        if sum(step.minutes for step in self.steps) != self.total_minutes:
            raise ValueError("학습 단계 시간의 합은 전체 학습 시간과 같아야 합니다.")
        return self


class QuizItem(LearningModel):
    question_id: str = Field(alias="questionId", min_length=1)
    question: str = Field(min_length=1)
    choices: list[str] = Field(min_length=2)
    answer: str = Field(min_length=1)
    explanation: str = Field(min_length=1)


class GradingResult(LearningModel):
    question_id: str = Field(alias="questionId", min_length=1)
    submitted_answer: str = Field(alias="submittedAnswer")
    correct: bool


class QuizResult(LearningModel):
    items: list[QuizItem]
    requested_count: int = Field(alias="requestedCount", ge=1)
    returned_count: int = Field(alias="returnedCount", ge=0)
    score: int | None = Field(default=None, ge=0, le=100)
    grading_results: list[GradingResult] = Field(alias="gradingResults", default_factory=list)


class LearningRecommendation(LearningModel):
    title: str
    total_minutes: int = Field(alias="totalMinutes", ge=1)
    steps: list[StudyPlanStep]
    quiz: list[QuizItem]
    next_topic: str = Field(alias="nextTopic")


class LearningToolResult(LearningModel):
    success: bool
    tool_name: str = Field(alias="toolName")
    data: Any | None = None
    error: dict[str, Any] | None = None


class LearningAssistantResponse(LearningModel):
    agent_type: Literal["learning_assistant"] = Field(alias="agentType", default="learning_assistant")
    summary: str
    recommendations: list[LearningRecommendation] = Field(default_factory=list)
    reasoning: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(alias="followUpQuestions", default_factory=list)
    tool_results: list[LearningToolResult] = Field(alias="toolResults", default_factory=list)

