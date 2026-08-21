# yb 담당 계획서: 학습 도우미 AI Agent 백엔드

## 1. 담당 목표

`yb`는 학습 도우미 AI Agent를 구현한다. 사용자가 입력한 과목, 목표, 수준, 학습 시간, 학습 스타일을 바탕으로 다음 결과를 제공한다.

- 요청 시간과 정확히 일치하는 단계별 학습 계획
- 요청 수준에 맞는 개념·예제·연습 콘텐츠
- 학습 계획 주제를 기반으로 한 퀴즈, 정답 및 해설
- 핵심 개념, 다음 학습 주제, 지원하지 않는 과목 등에 대한 후속 질문

모든 기능은 외부 API 키, 데이터베이스, JSON 파일 없이 Tool 파일 내부의 Python `list`/`dict` 목 데이터로 동작한다.

## 2. 담당 범위와 파일

다음 파일은 `yb`가 생성·수정한다.

```text
backend/app/agents/learning_assistant_agent.py
backend/app/routers/learning_assistant_router.py
backend/app/schemas/learning_assistant.py
backend/app/services/learning_assistant_service.py
backend/app/tools/learning/__init__.py
backend/app/tools/learning/study_plan.py
backend/app/tools/learning/quiz.py
backend/tests/test_learning_assistant_api.py
yb.md
```

`tk` 담당 파일인 메뉴 추천 도메인 파일은 수정하지 않는다.

```text
backend/app/agents/menu_recommendation_agent.py
backend/app/routers/menu_recommendation_router.py
backend/app/schemas/menu_recommendation.py
backend/app/services/menu_recommendation_service.py
backend/app/tools/menu/
backend/tests/test_menu_recommendation_api.py
```

## 3. API 계약

### 엔드포인트

```http
POST /api/learning/assist
```

### 요청 모델: `LearningAssistantRequest`

JSON은 camelCase를 사용하고, Python 모델은 필요에 따라 Pydantic alias로 snake_case를 사용한다. 모든 모델에는 `ConfigDict(extra="forbid")`를 적용해 정의되지 않은 필드를 거부한다.

| JSON 필드 | 타입 | 검증 |
|---|---|---|
| `subject` | string | 필수, 공백 제거 후 1~100자 |
| `goal` | string | 필수, 공백 제거 후 1~500자 |
| `level` | string | `초급`, `중급`, `고급` 중 하나 |
| `studyMinutes` | integer | 10~240 |
| `learningStyle` | string | 필수, 공백 제거 후 1~100자 |
| `difficultConcepts` | string 배열 | 선택, 최대 10개, 각 값은 빈 문자열 불가 |

Happy Case 요청:

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

### 응답 모델: `LearningAssistantResponse`

응답에는 아래 정보를 포함한다.

```text
agentType: "learning_assistant"
summary: 최종 학습 안내
studyPlan: 학습 계획 결과
recommendations: 핵심 개념 및 다음 학습 추천
quiz: 문제·선택지·정답·해설 목록
followUpQuestions: 콘텐츠가 없는 경우의 후속 질문
toolResults: create_study_plan, create_quiz 실행 Trace
```

내부 예외 메시지와 Stack Trace는 응답에 포함하지 않는다.

## 4. 스키마 설계

파일: `backend/app/schemas/learning_assistant.py`

다음 모델을 구현한다.

```text
LearningAssistantRequest
StudyPlanArgs
QuizArgs
StudyPlanStep
StudyPlanResult
QuizItem
LearningRecommendation
LearningAssistantResponse
```

주요 검증 기준:

- API 요청과 Tool 인자를 별도 Pydantic 모델로 검증한다.
- `StudyPlanStep.minutes`는 양의 정수여야 한다.
- `StudyPlanResult.steps`의 시간 합계는 `studyMinutes`와 같아야 한다.
- 퀴즈는 중복 없이 구성하고, 각 항목에는 문제, 선택지, 정답, 해설을 포함한다.
- 응답의 모든 문자열 필수값과 배열 최대 길이를 검증한다.

## 5. Tool 설계 및 목 데이터

### 5.1 `create_study_plan`

파일: `backend/app/tools/learning/study_plan.py`

입력은 `StudyPlanArgs`로 검증한다.

```text
subject, goal, level, study_minutes, learning_style, difficult_concepts
```

Tool 내부에 과목, 수준, 주제, 개념, 예제, 콘텐츠 ID 및 예상 시간을 가진 Python `list`/`dict` 상수를 둔다. 첫 구현은 반드시 다음 목 데이터를 포함한다.

```text
과목: Python
수준: 초급
주제: 반복문
콘텐츠: 반복문 개념, for문 예제, 반복 연습 문제
```

실행 규칙:

1. 과목과 수준에 맞는 콘텐츠만 조회한다.
2. 목표와 어려운 개념을 반영해 관련 콘텐츠를 우선 선택한다.
3. 개념 → 예제 → 연습 순서로 계획을 구성한다.
4. 각 단계에 콘텐츠 ID, 주제, 설명, 학습 시간을 포함한다.
5. 단계 시간 합계가 요청 `study_minutes`와 정확히 일치하도록 배분한다.
6. 콘텐츠가 없으면 빈 계획과 후속 질문에 필요한 상태를 반환한다.

### 5.2 `create_quiz`

파일: `backend/app/tools/learning/quiz.py`

입력은 `QuizArgs`로 검증한다.

```text
subject, level, topic, content_ids, answers(optional)
```

Tool 내부에 과목, 수준, 주제, 문제 ID, 문제, 선택지, 정답, 해설을 가진 Python `list`/`dict` 상수를 둔다. Python 초급 반복문 퀴즈를 반드시 포함한다.

실행 규칙:

1. 첫 번째 Tool이 반환한 주제와 콘텐츠 ID를 입력으로 사용한다.
2. 과목과 수준이 일치하는 템플릿만 조회한다.
3. 중복 문제 ID를 제거한다.
4. 각 퀴즈에 문제, 선택지, 정답, 해설을 포함한다.
5. 답안이 전달되면 선택적으로 채점 결과를 추가한다.
6. 템플릿이 없으면 빈 퀴즈 결과를 반환하고 Agent가 후속 질문을 만든다.

## 6. Agent·Service·Router 처리 흐름

```text
POST /api/learning/assist
→ LearningAssistantRouter
→ LearningAssistantRequest 검증
→ LearningAssistantService
→ LearningAssistantAgent
→ 안전 실행기: create_study_plan
→ 학습 계획 및 콘텐츠 ID 확인
→ 안전 실행기: create_quiz
→ 학습 계획, 퀴즈, 추천 문구 조합
→ LearningAssistantResponse 검증
→ HTTP 응답
```

### Agent 책임

파일: `backend/app/agents/learning_assistant_agent.py`

- Tool 호출 순서와 Tool 결과 조합을 정의한다.
- Tool 함수는 직접 호출하지 않고 Runtime 또는 `tools/executor.py`의 안전 실행 경로만 사용한다.
- 첫 Tool에서 콘텐츠가 없으면 두 번째 Tool을 무의미하게 실행하지 않고, 지원 가능한 과목이나 목표를 묻는 후속 질문을 응답한다.
- Tool 오류는 공통 오류 형식으로 처리하고 내부 정보를 외부에 노출하지 않는다.

### Service 책임

파일: `backend/app/services/learning_assistant_service.py`

- Router와 Agent 사이의 도메인 진입점 역할을 한다.
- 요청을 Agent에 전달하고 검증된 응답 모델을 반환한다.
- HTTP 세부 처리나 Tool 내부 필터링 규칙은 포함하지 않는다.

### Router 책임

파일: `backend/app/routers/learning_assistant_router.py`

- `/api/learning/assist` POST 라우트를 선언한다.
- 요청·응답 Pydantic 모델과 명시적 상태 코드를 사용한다.
- 도메인 로직을 포함하지 않는다.

## 7. 공통 코드 통합 및 충돌 방지

`yb`는 자기 도메인 파일에서 구현을 완료하는 것을 우선한다. 아래 공통 파일은 `tk`와 충돌할 수 있으므로 필요한 최소 변경만 별도 커밋으로 관리한다.

| 공통 파일 | yb 변경 범위 | 충돌 방지 원칙 |
|---|---|---|
| `backend/app/main.py` | 학습 Router import 및 `include_router` 한 항목 | 기존 코드와 tk Router 등록을 수정·정렬하지 않고 인접 줄만 추가 |
| `backend/app/tools/registry.py` | `create_study_plan`, `create_quiz` ToolSpec 두 항목 | tk의 메뉴 Tool 등록을 변경하지 않고 독립 항목만 추가 |
| `backend/app/agents/runtime.py` | 두 Tool 순차 실행에 필요한 범용 확장만 수행 | 메뉴·학습 전용 분기, 필터 및 응답 문구를 추가하지 않음 |
| `backend/app/providers/mock.py` | 학습 Happy Case에 필요한 범용 최종 답변 지원 | 메뉴 도메인 응답 규칙을 변경하지 않음 |

통합 순서:

1. yb 전용 Schema와 Tool 목 데이터를 먼저 완성한다.
2. yb 전용 Tool, Agent, Service, Router와 테스트를 완성한다.
3. 공통 Runtime 확장이 필요하면 범용 인터페이스만 별도 커밋으로 반영한다.
4. Registry에는 학습 Tool 두 개만 추가한다.
5. `main.py`에는 학습 Router 등록 한 건만 추가한다.
6. tk 병합 뒤 전체 테스트를 실행하고 import 순서·등록 누락만 조정한다.

공통 파일을 수정할 때는 다음을 지킨다.

- 관련 없는 코드 포맷팅, 이름 변경, import 재정렬을 하지 않는다.
- tk와 같은 줄을 수정해야 하면 선행 변경을 병합한 뒤 최소 diff로 수정한다.
- 공통 파일 변경은 전용 도메인 파일 변경과 분리된 커밋으로 남긴다.
- 목 데이터, 검증 모델, 추천 규칙은 `learning_*` 파일 또는 `tools/learning/` 안에만 둔다.

## 8. 오류 처리

공통 오류 코드를 사용한다.

| 코드 | yb 처리 기준 |
|---|---|
| `REQUEST_VALIDATION_ERROR` | 과목, 목표, 수준, 학습 시간, 학습 스타일 요청값 오류 |
| `TOOL_NOT_ALLOWED` | 학습 Tool이 Registry에 등록되지 않은 경우 |
| `TOOL_VALIDATION_ERROR` | `StudyPlanArgs`, `QuizArgs` 검증 실패 |
| `TOOL_EXECUTION_ERROR` | Tool 실행 중 복구 불가능한 오류 |
| `MOCK_DATA_NOT_FOUND` | 과목·수준·주제에 맞는 목 콘텐츠 또는 퀴즈가 없음 |
| `AGENT_EXECUTION_ERROR` | Agent 결과 조합 중 복구 불가능한 오류 |

지원하지 않는 과목이나 결과가 없는 경우는 내부 오류가 아니라 정상 HTTP 응답으로 처리하며, 빈 학습 계획·퀴즈와 구체적인 `followUpQuestions`를 반환한다.

## 9. 테스트 계획

파일: `backend/tests/test_learning_assistant_api.py`

다음 API 테스트를 구현한다.

1. Python 초급 반복문 Happy Case가 HTTP 200을 반환한다.
2. 응답 Trace에서 `create_study_plan`과 `create_quiz`가 모두 성공한 것을 확인한다.
3. 학습 계획 단계 시간 합계가 요청한 `studyMinutes`와 동일한지 확인한다.
4. 반환 콘텐츠와 퀴즈가 요청 수준과 일치하는지 확인한다.
5. 퀴즈에 문제, 선택지, 정답, 해설이 포함되는지 확인한다.
6. 허용되지 않은 수준과 범위를 벗어난 학습 시간에 검증 오류가 발생하는지 확인한다.
7. 지원하지 않는 과목은 HTTP 200과 후속 질문을 반환하는지 확인한다.
8. 외부 API 키 없이 Mock Provider로 실행되는지 확인한다.
9. Tool 실패 시 내부 예외 및 Stack Trace가 응답에 포함되지 않는지 확인한다.
10. 메뉴 추천 API 테스트와 독립적으로 실행되는지 확인한다.

## 10. 완료 기준

- `/api/learning/assist`가 요청·응답 계약에 맞게 동작한다.
- `create_study_plan`과 `create_quiz`가 Registry 및 안전 실행기를 통해 순서대로 실행된다.
- Python 초급 반복문 30분 Happy Case가 외부 API 키 없이 성공한다.
- 학습 단계 시간 합계가 요청 시간과 정확히 일치한다.
- 결과에 반복문 개념, 예제, 문제, 정답 및 해설이 포함된다.
- 지원하지 않는 과목은 후속 질문을 반환한다.
- Tool 목 데이터는 `tools/learning/` 내부 Python 상수로만 관리한다.
- yb 도메인 구현이 tk 메뉴 도메인 파일을 수정하지 않는다.
- 공통 파일 변경이 최소화되고 독립 커밋으로 분리되어 병합 충돌을 줄인다.
- yb API 테스트와 기존 백엔드 회귀 테스트가 통과한다.
