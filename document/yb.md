# yb 학습 도우미 AI Agent 백엔드 구현 명세서

## 1. 문서 목적

본 문서는 `master.md`와 `backend.md`를 기준으로 `yb`가 학습 도우미 AI Agent 백엔드를 독립적으로 구현하기 위한 개인 작업 명세다.

`yb`는 학습 도우미 전용 파일과 학습 기능 연결에 필요한 공통 파일까지 구현한다. 별도 병합 담당자는 두지 않는다. `yb`가 전역 Registry 확장, Agent별 Tool 격리, Router 등록과 기존 테스트 호환성을 먼저 완료하고, 이후 사용자가 `tk`의 메뉴 추천 코드를 병합한다.

## 2. 담당 범위

`yb`가 구현할 기능은 다음과 같다.

- 학습 도우미 API 요청·응답 Schema
- 학습 계획 생성 Tool
- 문제·퀴즈 생성 및 채점 Tool
- 학습 도우미 Agent 실행 흐름
- 학습 도우미 Service
- 학습 도우미 Router
- Tool 내부 Python 목 데이터
- 학습 도우미 Happy Case
- 학습 도우미 단위·API 테스트
- 학습 Router와 Tool의 공통 파일 연결
- 전역 Registry를 도메인 확장 가능한 구조로 수정
- 기존 여행 Agent의 Tool 범위 격리
- 기존 Registry 테스트를 확장 가능한 방식으로 수정

메뉴 추천 기능은 구현하거나 수정하지 않는다.

## 3. 파일 소유권과 Merge 충돌 방지

### 3.1 yb 전용 신규 파일

다음 파일은 `yb`가 생성하고 소유한다. `tk`는 이 파일들을 수정하지 않는다.

```text
backend/app/agents/learning_assistant_agent.py
backend/app/routers/learning_assistant_router.py
backend/app/schemas/learning_assistant.py
backend/app/services/learning_assistant_service.py
backend/app/tools/learning/__init__.py
backend/app/tools/learning/study_plan.py
backend/app/tools/learning/quiz.py
backend/tests/test_learning_assistant_api.py
```

### 3.2 yb가 직접 수정하는 공통 파일

별도 병합 담당자가 없으므로 다음 공통 파일도 `yb`가 직접 수정하고 테스트한다.

```text
backend/app/main.py
backend/app/agents/runtime.py
backend/app/agents/travel_agent.py
backend/app/tools/registry.py
backend/tests/test_api.py
```

각 공통 파일의 yb 작업 범위는 다음과 같다.

| 파일 | yb 작업 |
|---|---|
| `main.py` | 학습 도우미 Router 등록 |
| `runtime.py` | 필요한 경우 Tool 순차 실행을 지원하되 기존 API 유지 |
| `travel_agent.py` | 여행 Agent에 여행 Tool 네 개만 전달하도록 필터링 |
| `tools/registry.py` | 학습 Tool 두 개 등록 및 이름 기반 Definition 필터 지원 |
| `tests/test_api.py` | 기존 Tool 네 개를 부분집합으로 검사하도록 수정 |

`providers/mock.py`는 학습 Happy Case가 Python Tool 결과 조합만으로 동작하므로 수정하지 않는다. `routers`, `schemas`, `services`, `tools`의 기존 `__init__.py`도 필요하지 않으면 수정하지 않는다.

### 3.3 tk 병합 시 공통 파일 원칙

사용자가 `tk` 코드를 병합할 때 위 공통 파일은 `yb`에서 완성한 버전을 기준으로 유지한다. `tk` 쪽 변경에서 다음 메뉴 연결 부분만 추가한다.

- `main.py`: 메뉴 Router import와 `include_router` 한 줄
- `tools/registry.py`: 메뉴 Tool import와 ToolSpec 두 개
- `tests/test_api.py`: 메뉴 Tool 두 개가 Registry에 포함되는지 확인하는 테스트

`travel_agent.py`의 도메인 필터, 기존 Tool 부분집합 검사와 학습 Tool 등록을 `tk` 버전으로 덮어쓰면 안 된다.

### 3.3 기존 파일 보존 원칙

- 기존 여행·날씨 Agent와 Tool을 삭제하거나 이름을 바꾸지 않는다.
- 기존 `stage_01`, `stage_02`, `stage_03` API를 변경하지 않는다.
- 기존 공통 Schema와 Tool 실행 결과 형식을 임의로 변경하지 않는다.
- 메뉴 추천 관련 파일과 목 데이터를 참조하지 않는다.
- 별도의 JSON 파일, DB, `mock_data/` 폴더를 만들지 않는다.

## 4. 구현 수준과 기술 기준

현재 `mini_agent_03_tool`과 동일한 수준으로 다음 방식을 사용한다.

- FastAPI Router
- Pydantic `BaseModel`, `Field`, `ConfigDict`, `model_validator`
- Service와 Agent 함수
- 기존 Tool Registry 및 안전 실행기
- Python `list`와 `dict` 기반 목 데이터
- Mock Provider 기본 실행
- pytest와 FastAPI `TestClient`

다음은 구현하지 않는다.

- 데이터베이스
- 외부 학습 콘텐츠 API
- 벡터 검색 또는 RAG
- 사용자별 진도 영구 저장
- 인증과 권한
- 복잡한 Multi-Agent 프레임워크
- 별도 프론트엔드 코드

## 5. 학습 도우미 API 계약

### Endpoint

```http
POST /api/learning/assist
```

### Happy Case 요청

```json
{
  "subject": "Python",
  "goal": "반복문 기초 이해",
  "level": "초급",
  "studyMinutes": 30,
  "learningStyle": "예제와 문제 풀이",
  "difficultConcepts": []
}
```

JSON API는 `backend.md`에 정의된 camelCase를 사용한다. Python 내부 필드명은 snake_case로 작성하고 Pydantic alias를 설정한다.

### 성공 응답

```json
{
  "agentType": "learning_assistant",
  "summary": "Python 반복문의 개념부터 문제 풀이까지 30분 학습 계획을 만들었습니다.",
  "recommendations": [
    {
      "title": "Python 반복문 30분 학습",
      "totalMinutes": 30,
      "steps": [
        {
          "order": 1,
          "title": "for문 핵심 개념",
          "minutes": 10,
          "summary": "for문의 기본 동작을 이해합니다.",
          "example": "for number in range(3): print(number)"
        }
      ],
      "quiz": [
        {
          "questionId": "python-loop-q001",
          "question": "range(3)을 사용한 for문은 몇 번 반복됩니까?",
          "choices": ["2번", "3번", "4번", "무한 반복"],
          "answer": "3번",
          "explanation": "range(3)은 0, 1, 2를 생성합니다."
        }
      ],
      "nextTopic": "while문 기초"
    }
  ],
  "reasoning": [
    "초급 수준을 적용했습니다.",
    "전체 학습 시간을 30분으로 구성했습니다.",
    "예제와 문제 풀이 중심으로 배치했습니다."
  ],
  "followUpQuestions": [],
  "toolResults": [
    {
      "success": true,
      "toolName": "create_study_plan",
      "data": {}
    },
    {
      "success": true,
      "toolName": "create_quiz",
      "data": {}
    }
  ]
}
```

## 6. Schema 구현

파일:

```text
backend/app/schemas/learning_assistant.py
```

구현할 모델:

```text
LearningAssistantRequest
StudyPlanArgs
QuizArgs
StudyPlanStep
StudyPlanResult
QuizItem
QuizResult
LearningRecommendation
LearningToolResult
LearningAssistantResponse
```

### 요청 필드 검증

| 필드 | Python 필드 | 검증 |
|---|---|---|
| `subject` | `subject` | 필수, 1~100자 |
| `goal` | `goal` | 필수, 1~500자 |
| `level` | `level` | 초급, 중급, 고급 |
| `studyMinutes` | `study_minutes` | 10~240분 |
| `learningStyle` | `learning_style` | 필수, 1~100자 |
| `difficultConcepts` | `difficult_concepts` | 최대 10개 |

모든 입력 모델에 정의되지 않은 추가 필드는 차단한다.

```python
model_config = ConfigDict(
    extra="forbid",
    populate_by_name=True,
)
```

`studyMinutes`, `learningStyle`, `difficultConcepts`에는 각각 Pydantic alias를 지정한다.

### 응답 검증

- `agentType`은 항상 `learning_assistant`다.
- 학습 단계의 `minutes`는 1 이상이다.
- 단계별 시간 합계는 요청한 `studyMinutes`와 일치한다.
- 퀴즈에는 문제, 정답과 해설이 반드시 존재한다.
- `recommendations`, `reasoning`, `followUpQuestions`, `toolResults`는 빈 배열을 허용한다.

## 7. Tool 1: 학습 계획 생성

파일:

```text
backend/app/tools/learning/study_plan.py
```

Tool 이름:

```text
create_study_plan
```

### 역할

- 과목과 목표에 맞는 주제 선택
- 수준에 맞는 콘텐츠 필터링
- 개념, 예제, 연습 순서 생성
- 전체 학습 시간 단계별 배분
- 다음 학습 주제 제안

### Tool 내부 목 데이터

별도의 JSON 파일을 만들지 않는다. 다음과 같은 Python 상수를 `study_plan.py` 내부에 작성한다.

```python
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
        "recommended_minutes": 10,
        "next_topic": "while문 기초",
    }
]
```

Happy Case 외에도 다음 최소 데이터를 포함한다.

- Python 초급 반복문 개념
- Python 초급 반복문 예제
- Python 초급 반복문 연습
- 지원하지 않는 과목을 구분할 수 있는 과목 목록

### 입력

```json
{
  "subject": "Python",
  "goal": "반복문 기초 이해",
  "level": "초급",
  "studyMinutes": 30,
  "learningStyle": "예제와 문제 풀이",
  "difficultConcepts": []
}
```

### 출력

```json
{
  "title": "Python 반복문 30분 학습",
  "subject": "Python",
  "topic": "반복문",
  "level": "초급",
  "totalMinutes": 30,
  "steps": [],
  "nextTopic": "while문 기초"
}
```

### 시간 배분 규칙

- 단계 수는 기본 3단계로 한다.
- 개념, 예제, 연습 순서를 유지한다.
- 나누어떨어지지 않는 나머지 시간은 마지막 연습 단계에 더한다.
- 모든 단계 시간은 1분 이상이어야 한다.
- 단계별 시간 합계는 요청 시간과 정확히 같아야 한다.

### 결과 없음 처리

지원하지 않는 과목이나 관련 콘텐츠가 없으면 임의의 콘텐츠를 반환하지 않는다.

```json
{
  "found": false,
  "supportedSubjects": ["Python"],
  "followUpQuestion": "현재는 Python 학습 콘텐츠를 지원합니다. Python으로 학습할까요?"
}
```

## 8. Tool 2: 문제·퀴즈 생성 및 채점

파일:

```text
backend/app/tools/learning/quiz.py
```

Tool 이름:

```text
create_quiz
```

### 역할

- 첫 번째 Tool이 선택한 과목과 주제로 문제 검색
- 수준에 맞는 문제 필터링
- 요청 개수만큼 중복 없이 문제 반환
- 선택지, 정답과 해설 제공
- 사용자 답안이 있으면 채점 결과 반환

### Tool 내부 목 데이터

별도의 JSON 파일을 만들지 않는다.

```python
QUIZ_ITEMS = [
    {
        "question_id": "python-loop-q001",
        "subject": "Python",
        "topic": "반복문",
        "level": "초급",
        "question": "range(3)을 사용한 for문은 몇 번 반복됩니까?",
        "choices": ["2번", "3번", "4번", "무한 반복"],
        "answer": "3번",
        "explanation": "range(3)은 0, 1, 2를 생성합니다.",
    }
]
```

Happy Case를 위해 Python 초급 반복문 문제를 최소 3개 작성한다.

### 입력

```json
{
  "subject": "Python",
  "topic": "반복문",
  "level": "초급",
  "questionCount": 3,
  "answers": {}
}
```

### 출력

```json
{
  "items": [],
  "requestedCount": 3,
  "returnedCount": 3,
  "score": null,
  "gradingResults": []
}
```

### 문제 생성 규칙

- `questionCount`는 1~5로 제한한다.
- 같은 `questionId`를 중복 반환하지 않는다.
- 모든 문항에는 정답과 해설이 있어야 한다.
- 요청 개수보다 목 데이터가 적으면 가능한 문항만 반환하고 실제 개수를 표시한다.
- 답안이 없으면 채점하지 않고 `score`는 `null`로 반환한다.

### 채점 규칙

- 채점은 문자열을 정리한 후 정확히 일치하는 방식으로 구현한다.
- 맞은 문항 수와 전체 제출 문항 수를 반환한다.
- 제출하지 않은 문제는 오답으로 계산하지 않는다.
- 0으로 나누는 상황이 발생하지 않도록 답안이 없으면 점수를 계산하지 않는다.

## 9. Tool 패키지 Export

파일:

```text
backend/app/tools/learning/__init__.py
```

다음 함수만 외부에 공개한다.

```python
from app.tools.learning.quiz import create_quiz
from app.tools.learning.study_plan import create_study_plan

__all__ = ["create_study_plan", "create_quiz"]
```

`ToolSpec`이나 전역 Registry를 이 파일에서 import하지 않는다. 공통 `registry.py`가 이 패키지를 import하도록 하여 순환 import를 방지한다.

## 10. 학습 도우미 Agent

파일:

```text
backend/app/agents/learning_assistant_agent.py
```

### 실행 순서

```text
LearningAssistantRequest 수신
→ create_study_plan Tool 실행
→ 지원 과목·콘텐츠 여부 확인
→ 학습 계획의 subject/topic/level 추출
→ create_quiz Tool 실행
→ 계획과 퀴즈 결과 조합
→ summary와 reasoning 생성
→ LearningAssistantResponse 반환
```

Tool 실행 순서는 다음과 같이 고정한다.

```text
1. create_study_plan
2. create_quiz
```

### Agent 규칙

- 두 번째 Tool 입력은 첫 번째 Tool 결과를 사용한다.
- Agent가 Tool 내부 목 데이터 상수를 직접 import하지 않는다.
- Tool 결과에 없는 학습 정보를 임의로 만들지 않는다.
- Tool 실패를 성공 결과로 변환하지 않는다.
- 지원하지 않는 과목이면 두 번째 Tool을 호출하지 않는다.
- 외부 Provider가 없어도 결정적 Python 조합으로 최종 응답을 만든다.
- Provider를 사용하더라도 Tool Result만 근거로 최종 답변을 작성한다.

### Trace

`toolResults`에는 실제 실행 순서대로 결과를 기록한다.

```text
create_study_plan
create_quiz
```

## 11. Service

파일:

```text
backend/app/services/learning_assistant_service.py
```

Service는 Router와 Agent 사이의 얇은 계층으로 유지한다.

담당 기능:

- 요청 모델을 Agent에 전달
- Agent 응답 반환
- 예상 가능한 도메인 오류를 사용자용 오류로 변환
- 내부 예외와 Stack Trace 비노출

Service에 목 데이터, 학습 계획 생성 규칙 또는 퀴즈 정답을 중복 작성하지 않는다.

## 12. Router

파일:

```text
backend/app/routers/learning_assistant_router.py
```

Router 객체 이름:

```python
learning_assistant_router
```

구현 Endpoint:

```python
@learning_assistant_router.post(
    "/api/learning/assist",
    response_model=LearningAssistantResponse,
)
```

Router의 역할은 요청 검증, Service 호출과 응답 모델 적용으로 제한한다. 학습 계획과 퀴즈 생성 로직을 Router에 작성하지 않는다.

## 13. 오류 처리

| 상황 | 처리 |
|---|---|
| 필수 입력 누락 | FastAPI/Pydantic 422 |
| 잘못된 수준 | FastAPI/Pydantic 422 |
| 학습 시간 범위 오류 | FastAPI/Pydantic 422 |
| 지원하지 않는 과목 | HTTP 200과 `followUpQuestions` 반환 |
| 관련 콘텐츠 없음 | 후속 질문 반환, 퀴즈 Tool 미실행 |
| 퀴즈 데이터 부족 | 가능한 문제만 반환하고 실제 개수 표시 |
| Tool 입력 검증 실패 | `TOOL_VALIDATION_ERROR` |
| Tool 실행 실패 | `TOOL_EXECUTION_ERROR` |
| 예상하지 못한 Agent 오류 | 사용자용 `AGENT_EXECUTION_ERROR` |

내부 파일 경로, Python 예외 문자열과 Stack Trace를 API 응답에 포함하지 않는다.

## 14. Happy Case

기본 요청:

```json
{
  "subject": "Python",
  "goal": "반복문 기초 이해",
  "level": "초급",
  "studyMinutes": 30,
  "learningStyle": "예제와 문제 풀이",
  "difficultConcepts": []
}
```

완료 조건:

- 외부 API 키 없이 실행된다.
- HTTP 200을 반환한다.
- `create_study_plan`이 실행된다.
- `create_quiz`가 실행된다.
- Tool 실행 순서가 올바르다.
- 학습 단계 시간의 합이 30분이다.
- Python 반복문의 개념과 예제가 포함된다.
- 퀴즈에 문제, 선택지, 정답과 해설이 포함된다.
- `agentType`이 `learning_assistant`다.
- 사용자 응답에 내부 오류 정보가 없다.

## 15. 테스트 명세

파일:

```text
backend/tests/test_learning_assistant_api.py
```

### Schema 테스트

1. Happy Case 요청을 검증한다.
2. 빈 과목과 목표를 거부한다.
3. 허용되지 않은 수준을 거부한다.
4. 10분 미만과 240분 초과를 거부한다.
5. 정의되지 않은 추가 필드를 거부한다.
6. camelCase 요청을 Python 필드로 변환한다.

### Tool 테스트

1. Python 초급 반복문 계획을 생성한다.
2. 단계 시간 합계가 요청 시간과 같다.
3. 지원하지 않는 과목은 `found=false`를 반환한다.
4. 퀴즈 문제 ID가 중복되지 않는다.
5. 문제마다 정답과 해설이 존재한다.
6. 답안이 없으면 점수를 계산하지 않는다.
7. 답안이 있으면 정답 수를 계산한다.

### Agent/API 테스트

1. Happy Case가 HTTP 200을 반환한다.
2. 두 Tool이 순서대로 실행된다.
3. 두 번째 Tool 입력이 첫 번째 Tool 결과의 주제를 사용한다.
4. 지원하지 않는 과목에는 후속 질문이 있다.
5. 지원하지 않는 과목에는 Quiz Tool을 실행하지 않는다.
6. 외부 API 키 없이 동작한다.
7. Tool 오류가 표준 형식으로 반환된다.
8. 내부 예외와 Stack Trace가 노출되지 않는다.
9. 기존 백엔드 테스트를 깨뜨리지 않는다.
10. 학습 Agent의 Tool Definition에는 `create_study_plan`, `create_quiz`만 포함된다.
11. 학습 Agent가 여행·날씨·메뉴 Tool을 선택할 수 없다.
12. 전역 Registry에 신규 Tool을 추가해도 기존 Tool 네 개가 유지된다.

Schema와 Tool 단위 테스트를 먼저 작성한 뒤 `yb`가 `main.py`와 `registry.py`를 직접 연결하고 학습 API 통합 테스트까지 완료한다. 이후 `tk` 병합 후 전체 통합 테스트를 다시 실행한다.

## 16. yb 공통 파일 통합 작업

이 절의 작업은 별도 병합 담당자에게 넘기지 않고 `yb`가 직접 공통 파일에 적용한다. 기존 기능을 유지하면서 학습 기능이 단독으로 완전히 실행되는 상태까지 구현한다.

### 16.1 Tool Registry 연결

대상:

```text
backend/app/tools/registry.py
```

필요 import:

```python
from app.schemas.learning_assistant import QuizArgs, StudyPlanArgs
from app.tools.learning import create_quiz, create_study_plan
```

필요 Tool 등록:

```python
"create_study_plan": ToolSpec(
    name="create_study_plan",
    description="과목, 목표, 수준과 학습 시간에 맞는 학습 계획을 생성합니다.",
    input_model=StudyPlanArgs,
    function=create_study_plan,
),
"create_quiz": ToolSpec(
    name="create_quiz",
    description="학습 계획의 과목과 주제에 맞는 문제, 정답과 해설을 생성합니다.",
    input_model=QuizArgs,
    function=create_quiz,
),
```

기존 날씨, 여행 및 `tk`의 메뉴 Tool 등록을 삭제하거나 덮어쓰지 않는다.

`get_tool_definitions()`는 기존 인자 없는 호출을 유지하면서 선택적으로 이름 목록을 받을 수 있도록 확장한다.

```python
def get_tool_definitions(names: set[str] | None = None) -> list[dict]:
    specs = TOOL_REGISTRY.values()
    if names is not None:
        specs = (spec for spec in specs if spec.name in names)
    return [spec.definition() for spec in specs]
```

이 방식은 기존 `/api/tools`와 테스트 호출을 깨뜨리지 않으면서 여행·메뉴·학습 Agent별 Tool 격리를 지원한다.

#### 전역 Registry 확장 시 주의사항

현재 `backend/tests/test_api.py`의 `test_tool_registry_contains_read_only_tools`는 Tool 이름을 기존 네 개와 정확히 일치하는지 검사한다.

```python
assert names == {
    "get_current_weather",
    "get_weather_forecast",
    "search_hotels",
    "search_attractions",
}
```

학습 Tool 두 개와 메뉴 Tool 두 개를 전역 Registry에 추가하면 총 Tool 수가 여덟 개가 되므로 위 테스트는 실패한다. 이는 기존 Tool이 깨진 것이 아니라 테스트가 확장 전 목록을 고정하고 있기 때문이다.

`yb`는 기존 Tool 보존 여부를 부분집합으로 검사하도록 직접 수정한다.

```python
existing_tools = {
    "get_current_weather",
    "get_weather_forecast",
    "search_hotels",
    "search_attractions",
}

assert existing_tools <= names
```

그리고 신규 Tool은 도메인별 테스트에서 별도로 확인한다.

```python
learning_tools = {"create_study_plan", "create_quiz"}
menu_tools = {"search_menus", "check_dietary_conditions"}

assert learning_tools <= names
assert menu_tools <= names
```

`test_tool_specs_are_the_single_source_for_definition_and_execution`는 Registry와 Definition 전체 집합이 같은지 확인하므로 신규 Tool을 정상 등록하면 그대로 유지할 수 있다.

### 16.2 Agent별 Tool 격리

전역 `TOOL_REGISTRY`에는 전체 Tool을 등록하되, 각 Agent에 전달하는 Tool 목록은 반드시 도메인별로 제한한다.

학습 Agent가 사용할 수 있는 Tool:

```python
LEARNING_TOOL_NAMES = {
    "create_study_plan",
    "create_quiz",
}
```

학습 Agent의 Tool Definition 생성 예시:

```python
def get_learning_tools() -> list[dict]:
    return [
        definition
        for definition in get_tool_definitions()
        if definition["name"] in LEARNING_TOOL_NAMES
    ]
```

학습 Agent는 `get_tool_definitions()` 전체 결과를 그대로 사용하면 안 된다. 전체 결과를 전달하면 날씨, 여행, 메뉴 Tool까지 선택 후보가 된다.

기존 여행 Agent도 현재 전체 Registry를 사용하므로 `yb`가 여행 Tool 네 개만 전달하도록 직접 제한한다.

```python
TRAVEL_TOOL_NAMES = {
    "get_current_weather",
    "get_weather_forecast",
    "search_hotels",
    "search_attractions",
}
```

메뉴 Agent도 메뉴 Tool 두 개만 전달한다.

```python
MENU_TOOL_NAMES = {
    "search_menus",
    "check_dietary_conditions",
}
```

Agent별 허용 범위는 다음과 같다.

| Agent | 허용 Tool 수 | 허용 Tool |
|---|---:|---|
| 여행 Agent | 4 | 날씨 2개, 여행 2개 |
| 메뉴 추천 Agent | 2 | 메뉴 검색, 식단 검증 |
| 학습 도우미 Agent | 2 | 학습 계획, 퀴즈 |

도메인별 Agent가 다른 도메인의 Tool을 선택하거나 실행하지 못하는지 테스트한다.

### 16.3 Router 연결

대상:

```text
backend/app/main.py
```

필요 import:

```python
from app.routers.learning_assistant_router import learning_assistant_router
```

필요 등록:

```python
app.include_router(learning_assistant_router)
```

기존 Router와 `tk` 메뉴 Router 등록을 유지한다.

### 16.4 Runtime 연결

공통 Runtime이 Tool Sequence를 지원하면 학습 Agent는 다음 이름 목록을 전달한다.

```python
["create_study_plan", "create_quiz"]
```

공통 Runtime 확장이 완료되지 않았으면 학습 Agent가 기존 `execute_tool_safely()`를 두 번 호출하되, 공통 Runtime 파일은 수정하지 않는다.

### 16.5 Mock Provider

학습 도우미의 Happy Case는 Python Tool 결과 조합만으로 동작해야 한다. 따라서 `providers/mock.py`는 수정하지 않는다. 학습 Agent는 외부 Provider나 Mock Provider의 추가 분기 없이도 Tool Result를 조합해 최종 응답을 생성한다.

### 16.6 기존 테스트 환경 기준선

병합 전 기존 테스트를 먼저 실행하고 결과를 기록한다.

```powershell
cd C:\mini_agent\mini_agent_03_tool\backend
..\.venv\Scripts\python.exe -m pytest tests -q
```

현재 로컬 `.env`에서 `LLM_PROVIDER=ollama` 또는 날씨 실호출 모드를 사용하면 다음 기존 테스트가 실패할 수 있다.

- 기본 Provider가 `mock`이라고 기대하는 테스트
- 현재 날씨 Tool의 결과가 `source=mock`이라고 기대하는 테스트

이 두 실패는 Registry 병합 실패와 구분한다. Registry 관련 회귀 여부를 확인할 때는 테스트 환경에서 다음 값을 명시한다.

```text
LLM_PROVIDER=mock
WEATHER_MODE=mock
```

비밀 키나 개인 `.env` 파일을 수정·커밋하지 않는다. 테스트 실행 프로세스에만 환경값을 적용한다.

## 17. tk 파트와의 인터페이스 분리

| 구분 | yb 학습 도우미 | tk 메뉴 추천 |
|---|---|---|
| API | `/api/learning/assist` | `/api/menu/recommend` |
| Agent 파일 | `learning_assistant_agent.py` | `menu_recommendation_agent.py` |
| Schema 파일 | `learning_assistant.py` | `menu_recommendation.py` |
| Service 파일 | `learning_assistant_service.py` | `menu_recommendation_service.py` |
| Tool 폴더 | `tools/learning/` | `tools/menu/` |
| Tool 이름 | `create_study_plan`, `create_quiz` | `search_menus`, `check_dietary_conditions` |
| 테스트 파일 | `test_learning_assistant_api.py` | `test_menu_recommendation_api.py` |

두 파트가 공유하는 것은 기존 실행 기반과 최종 Registry/Router 연결뿐이며, 도메인 파일은 서로 import하지 않는다.

## 18. 구현 순서

```text
1. learning_assistant.py Schema 작성
2. study_plan.py와 Python 목 데이터 작성
3. quiz.py와 Python 목 데이터 작성
4. tools/learning/__init__.py 작성
5. Tool 단위 테스트 작성
6. learning_assistant_agent.py 작성
7. learning_assistant_service.py 작성
8. learning_assistant_router.py 작성
9. Agent 단위 테스트 작성
10. main.py, registry.py, travel_agent.py 공통 연결 적용
11. 기존 test_api.py Registry 검사 수정
12. 학습 Registry와 Router 통합 테스트
13. 전체 기존 테스트 실행
14. tk 병합 후 전체 통합 테스트 재실행
```

## 19. yb 완료 기준

- yb 전용 파일과 본 문서에 지정된 공통 파일만 생성하거나 수정했다.
- `tk`의 메뉴 추천 파일을 수정하지 않았다.
- 학습 연결에 필요한 공통 파일을 yb가 직접 수정하고 검증했다.
- 여행 Agent에 여행 Tool만 전달되도록 격리했다.
- 기존 Registry 테스트를 신규 Tool 추가가 가능한 방식으로 수정했다.
- 학습 계획 및 퀴즈 Tool 두 개가 구현됐다.
- 목 데이터는 Tool Python 파일 내부의 `list/dict`로 작성됐다.
- JSON, DB와 별도 `mock_data/` 폴더를 사용하지 않는다.
- 요청·응답과 Tool arguments가 Pydantic으로 검증된다.
- 두 Tool의 순서와 의존 관계가 보장된다.
- 학습 Agent에는 학습 Tool 두 개만 전달된다.
- 전역 Registry 확장 후 기존 Tool 네 개가 유지된다.
- 기존 Registry 테스트의 고정 목록 검사를 확장 가능한 방식으로 변경하는 내용이 병합 계약에 반영됐다.
- 최초 Happy Case가 외부 API 키 없이 동작한다.
- 학습 단계 시간 합계가 요청 시간과 일치한다.
- 퀴즈에 문제, 정답과 해설이 포함된다.
- 지원하지 않는 과목에는 후속 질문을 반환한다.
- 내부 오류와 Stack Trace를 사용자에게 노출하지 않는다.
- yb 단위 테스트와 병합 후 API 테스트가 통과한다.
- 기존 `mini_agent_03_tool` 테스트가 계속 통과한다.
