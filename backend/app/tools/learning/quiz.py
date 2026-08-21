"""Python 목 문제를 사용해 퀴즈를 생성하고 제출 답안을 채점합니다."""

from app.schemas.learning_assistant import QuizArgs


QUIZ_ITEMS = [
    {
        "questionId": "python-loop-q001",
        "subject": "Python",
        "topic": "반복문",
        "level": "초급",
        "question": "range(3)을 사용한 for문은 몇 번 반복됩니까?",
        "choices": ["2번", "3번", "4번", "무한 반복"],
        "answer": "3번",
        "explanation": "range(3)은 0, 1, 2를 생성합니다.",
    },
    {
        "questionId": "python-loop-q002",
        "subject": "Python",
        "topic": "반복문",
        "level": "초급",
        "question": "목록의 모든 값을 차례로 처리할 때 가장 알맞은 문장은 무엇입니까?",
        "choices": ["if문", "for문", "import문", "class문"],
        "answer": "for문",
        "explanation": "for문은 목록처럼 순회 가능한 값들을 차례대로 처리합니다.",
    },
    {
        "questionId": "python-loop-q003",
        "subject": "Python",
        "topic": "반복문",
        "level": "초급",
        "question": "for number in range(1, 4)에서 마지막 number 값은 무엇입니까?",
        "choices": ["1", "2", "3", "4"],
        "answer": "3",
        "explanation": "range의 종료값 4는 포함되지 않아 1, 2, 3을 생성합니다.",
    },
]


def create_quiz(args: QuizArgs) -> dict:
    """조건에 맞는 문제를 중복 없이 반환하고 제출된 답안만 채점합니다."""
    matched = [
        item
        for item in QUIZ_ITEMS
        if item["subject"].casefold() == args.subject.casefold()
        and item["topic"] == args.topic
        and item["level"] == args.level
    ][: args.question_count]

    public_items = [
        {key: value for key, value in item.items() if key not in {"subject", "topic", "level"}}
        for item in matched
    ]
    grading_results = []
    for item in matched:
        question_id = item["questionId"]
        if question_id not in args.answers:
            continue
        submitted = args.answers[question_id].strip()
        grading_results.append(
            {
                "questionId": question_id,
                "submittedAnswer": submitted,
                "correct": submitted.casefold() == item["answer"].strip().casefold(),
            }
        )

    score = None
    if grading_results:
        correct_count = sum(1 for result in grading_results if result["correct"])
        score = round(correct_count / len(grading_results) * 100)

    return {
        "items": public_items,
        "requestedCount": args.question_count,
        "returnedCount": len(public_items),
        "score": score,
        "gradingResults": grading_results,
    }

