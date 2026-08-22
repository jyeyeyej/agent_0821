"""Python 목 콘텐츠를 사용해 결정적인 학습 계획을 생성합니다."""

from app.schemas.learning_assistant import StudyPlanArgs


LEARNING_CONTENTS = [
    {
        "id": "python-loop-001",
        "subject": "Python",
        "topic": "반복문",
        "level": "초급",
        "type": "concept",
        "title": "for문 핵심 개념",
        "summary": "for문은 순회 가능한 값을 차례대로 처리합니다.",
        "example": "for number in range(3): print(number)",
        "next_topic": "while문 기초",
    },
    {
        "id": "python-loop-002",
        "subject": "Python",
        "topic": "반복문",
        "level": "초급",
        "type": "example",
        "title": "range를 사용한 반복 예제",
        "summary": "range가 만드는 숫자를 for문으로 하나씩 확인합니다.",
        "example": "for number in range(1, 4): print(number)",
        "next_topic": "while문 기초",
    },
    {
        "id": "python-loop-003",
        "subject": "Python",
        "topic": "반복문",
        "level": "초급",
        "type": "practice",
        "title": "반복문 연습",
        "summary": "목록의 값을 반복하며 출력하는 코드를 직접 작성합니다.",
        "example": "for fruit in ['사과', '배']: print(fruit)",
        "next_topic": "while문 기초",
    },
]

SUPPORTED_SUBJECTS = sorted({item["subject"] for item in LEARNING_CONTENTS})


def _topic_from_goal(goal: str) -> str:
    if "반복" in goal or "for" in goal.lower() or "loop" in goal.lower():
        return "반복문"
    return "반복문"


def _allocate_minutes(total: int, count: int) -> list[int]:
    base = total // count
    minutes = [base] * count
    minutes[-1] += total - sum(minutes)
    return minutes


def create_study_plan(args: StudyPlanArgs) -> dict:
    """과목·목표·수준에 맞는 3단계 학습 계획을 반환합니다."""
    topic = _topic_from_goal(args.goal)
    contents = [
        item
        for item in LEARNING_CONTENTS
        if item["subject"].casefold() == args.subject.casefold()
        and item["level"] == args.level
        and item["topic"] == topic
    ]
    if not contents:
        return {
            "found": False,
            "supportedSubjects": SUPPORTED_SUBJECTS,
            "followUpQuestion": "현재는 Python 초급 반복문 학습 콘텐츠를 지원합니다. Python 반복문으로 학습할까요?",
        }

    minutes = _allocate_minutes(args.study_minutes, len(contents))
    steps = [
        {
            "order": index,
            "title": item["title"],
            "minutes": allocated,
            "summary": item["summary"],
            "example": item["example"],
        }
        for index, (item, allocated) in enumerate(zip(contents, minutes), start=1)
    ]
    return {
        "found": True,
        "title": f"{args.subject} {topic} {args.study_minutes}분 학습",
        "subject": args.subject,
        "topic": topic,
        "level": args.level,
        "totalMinutes": args.study_minutes,
        "steps": steps,
        "nextTopic": contents[0]["next_topic"],
    }

