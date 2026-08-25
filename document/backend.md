# AI Agent 백엔드 설계서

## 1. 문서 목적

본 문서는 `master.md`의 백엔드 구현 범위를 구체화한다. 백엔드는 다음 두 AI Agent를 구현한다.

1. 메뉴 추천 AI Agent
2. 학습 도우미 AI Agent

`tk`와 `yb`는 본 문서를 기준으로 자신의 담당 범위를 구체화한 개인 MD를 작성한다.

```text
backend.md
├─ tk.md: 메뉴 추천 AI Agent 백엔드
└─ yb.md: 학습 도우미 AI Agent 백엔드
```

| 담당자 | 담당 기능 |
|---|---|
| `tk` | 메뉴 추천 AI Agent |
| `yb` | 학습 도우미 AI Agent |

두 담당자는 현재 `mini_agent_03_tool/backend`의 구현 수준과 구조를 유지한다.

## 2. 구현 원칙

### 2.1 현재 프로젝트 수준 유지

다음 기술과 구현 방식을 그대로 사용한다.

- FastAPI 기반 API
- Pydantic 기반 요청·응답·Tool 인자 검증
- Router, Schema, Service, Agent, Tool 계층 분리
- 기존 Provider와 Mock Provider 구조
- 기존 Tool Registry와 안전 실행기
- pytest 기반 API 테스트
- Tool Python 파일 내부의 `list`/`dict` 기반 목 데이터
- 기존 `backend/app/core/config.py` 환경설정

다음 기능은 이번 구현 범위에 포함하지 않는다.

- 데이터베이스
- 사용자 인증 및 권한 관리
- 별도 벡터 데이터베이스
- 복잡한 멀티 Agent 프레임워크
- 메시지 큐 및 비동기 작업 서버
- 요청 이력 영구 저장
- 외부 메뉴·교육 콘텐츠 API

### 2.2 데이터 및 Provider 정책

현재 `mini_agent_03_tool`의 여행·날씨 Tool과 동일하게 소규모 목 데이터는 각 Tool Python 파일 내부의 `list`와 `dict` 상수로 관리한다. 별도의 JSON 파일, `mock_data/` 폴더와 데이터 서비스는 만들지 않는다. Agent는 목 데이터에 직접 접근하지 않고 Tool 실행 결과만 사용한다.

```text
Agent → Tool → Tool 내부 Python list/dict → 결과
```

외부 API 키가 없어도 동작하도록 기본 Provider는 `mock`으로 설정한다. Mock Provider에서도 Tool 실행, 최종 답변, 최초 Happy Case가 결정적으로 동작해야 한다.

## 3. 백엔드 디렉터리 구조

기존 백엔드 폴더를 다시 만들지 않고 필요한 파일만 추가한다.

```text
backend/
├─ app/
│  ├─ main.py                              # 기존 파일 수정
│  ├─ agents/
│  │  ├─ runtime.py                        # 기존 파일 확장
│  │  ├─ menu_recommendation_agent.py      # tk 신규
│  │  └─ learning_assistant_agent.py       # yb 신규
│  ├─ core/
│  │  └─ config.py                         # 기존 파일 재사용
│  ├─ providers/
│  │  ├─ base.py                           # 기존 파일 재사용
│  │  ├─ mock.py                           # Happy Case 지원 보완
│  │  └─ registry.py                       # 기존 파일 재사용
│  ├─ routers/
│  │  ├─ menu_recommendation_router.py     # tk 신규
│  │  └─ learning_assistant_router.py      # yb 신규
│  ├─ schemas/
│  │  ├─ common.py                         # 기존 파일 재사용
│  │  ├─ menu_recommendation.py            # tk 신규
│  │  └─ learning_assistant.py             # yb 신규
│  ├─ services/
│  │  ├─ menu_recommendation_service.py    # tk 신규
│  │  └─ learning_assistant_service.py     # yb 신규
│  ├─ tools/
│  │  ├─ executor.py                       # 기존 파일 재사용·필요 시 수정
│  │  ├─ registry.py                       # 신규 Tool 4개 등록
│  │  ├─ menu/                             # 신규 폴더
│  │  │  ├─ __init__.py
│  │  │  ├─ search.py                      # tk 신규
│  │  │  └─ dietary_check.py               # tk 신규
│  │  └─ learning/                         # 신규 폴더
│  │     ├─ __init__.py
│  │     ├─ study_plan.py                  # yb 신규
│  │     └─ quiz.py                        # yb 신규
└─ tests/
   ├─ test_menu_recommendation_api.py       # tk 신규
   └─ test_learning_assistant_api.py        # yb 신규
```

새로 생성하는 폴더는 다음 두 개뿐이다.

```text
backend/app/tools/menu/
backend/app/tools/learning/
```

`agents`, `core`, `providers`, `routers`, `schemas`, `services`, `tools`, `tests`는 기존 폴더를 재사용한다.

## 4. 공통 백엔드 구조

### 4.1 요청 처리 흐름

```text
Frontend 요청
→ FastAPI Router
→ Pydantic 요청 검증
→ Domain Service
→ Domain Agent
→ 첫 번째 Tool 안전 실행
→ 두 번째 Tool 안전 실행
→ Tool 결과 조합
→ Mock 또는 LLM 최종 답변 생성
→ Pydantic 응답 검증
→ Frontend 응답
```

### 4.2 공통 응답

```json
{
  "agentType": "menu_recommendation",
  "summary": "Agent의 최종 답변",
  "recommendations": [],
  "reasoning": [],
  "followUpQuestions": [],
  "toolResults": []
}
```

내부 예외 메시지나 Stack Trace는 응답에 포함하지 않는다.

### 4.3 공통 오류 코드

| 코드 | 상황 |
|---|---|
| `REQUEST_VALIDATION_ERROR` | API 요청 형식 또는 값 오류 |
| `TOOL_NOT_ALLOWED` | Registry에 등록되지 않은 Tool |
| `TOOL_VALIDATION_ERROR` | Tool arguments 검증 실패 |
| `TOOL_EXECUTION_ERROR` | Tool 함수 실행 실패 |
| `MOCK_DATA_NOT_FOUND` | Tool 내부에 필요한 목 데이터 없음 |
| `AGENT_EXECUTION_ERROR` | Agent 처리 중 복구 불가능한 오류 |

## 5. 기존 공통 코드 사용 기준

### `schemas/`

별도의 `validation/` 폴더를 만들지 않는다. API 요청·응답, Tool arguments, 숫자 범위, 필수값 및 허용 선택값 검증 모델을 기존 `backend/app/schemas/`에 추가한다. Agent별 모델은 `ConfigDict(extra="forbid")`를 적용한다.

### `tools/executor.py`

기존 안전 실행 흐름을 사용한다.

```text
Tool 이름 확인 → Registry 조회 → Pydantic 검증 → Tool 실행 → 표준 결과 반환
```

Agent가 Tool 함수를 직접 호출하여 검증 과정을 우회하면 안 된다.

### `tools/registry.py`

기존 `ToolSpec` 구조로 다음 Tool 네 개를 등록한다.

```text
search_menus
check_dietary_conditions
create_study_plan
create_quiz
```

### `agents/runtime.py`

기존 단일 Tool Cycle을 Agent별 Tool 두 개를 순서대로 실행할 수 있도록 확장한다. Runtime은 Tool 순서, 안전 실행, Trace, 실패 처리와 최종 답변 생성을 담당한다. 도메인 필터링과 추천 규칙은 Runtime에 작성하지 않는다.

# Part A. 메뉴 추천 AI Agent

## 6. 담당자 및 파일

메뉴 추천 AI Agent 백엔드는 `tk`가 담당한다.

```text
backend/app/agents/menu_recommendation_agent.py
backend/app/routers/menu_recommendation_router.py
backend/app/schemas/menu_recommendation.py
backend/app/services/menu_recommendation_service.py
backend/app/tools/menu/search.py
backend/app/tools/menu/dietary_check.py
backend/tests/test_menu_recommendation_api.py
```

## 7. 메뉴 추천 API

```http
POST /api/menu/recommend
```

요청 예시:

```json
{
  "mealTime": "저녁",
  "people": 2,
  "budget": 30000,
  "preferences": ["한식", "따뜻한 음식"],
  "excludedFoods": [],
  "allergies": [],
  "spicyLevel": "보통",
  "hasSoup": null,
  "quickMeal": false
}
```

| 필드 | 검증 |
|---|---|
| `mealTime` | 아침, 점심, 저녁, 야식 |
| `people` | 1~20 |
| `budget` | 1,000원 이상 |
| `preferences` | 최대 10개 |
| `excludedFoods` | 최대 20개 |
| `allergies` | 최대 20개 |
| `spicyLevel` | 안 매움, 보통, 매움 |
| `hasSoup` | boolean 또는 null |
| `quickMeal` | boolean, 기본값 false |

JSON API는 camelCase를 사용하고 Python 내부는 Pydantic alias를 이용해 snake_case로 구현할 수 있다.

## 8. 메뉴 추천 Schema

`backend/app/schemas/menu_recommendation.py`에 다음 모델을 구현한다.

```text
MenuRecommendationRequest
MenuSearchArgs
DietaryCheckArgs
MenuCandidate
MenuRecommendationItem
MenuRecommendationResponse
```

인원, 예산, 식사 시간, 맵기, 배열 길이, 빈 문자열, 추가 필드와 응답 추천 수를 검증한다.

## 9. 메뉴 추천 Tool

### `search_menus`

파일: `backend/app/tools/menu/search.py`

- `search.py` 내부 메뉴 `list/dict` 조회
- 식사 시간, 인원, 예산 필터
- 선호 음식 가중치 적용
- 제외 음식과 맵기 조건 적용
- 국물 및 간편식 조건 적용
- 적합도 기준 후보 정렬
- 후보가 없으면 필터를 임의로 무시하지 않고 빈 결과 반환

출력 예시:

```json
{
  "matchedCount": 1,
  "candidates": [
    {
      "menuId": "menu-001",
      "name": "소고기 불고기 정식",
      "totalPrice": 28000,
      "score": 95,
      "matchedConditions": ["저녁", "한식", "따뜻한 음식"]
    }
  ]
}
```

### `check_dietary_conditions`

파일: `backend/app/tools/menu/dietary_check.py`

- 첫 번째 Tool 후보의 알레르기 충돌 확인
- 제외 음식 포함 여부 확인
- 영양 참고 정보 연결
- 안전 후보와 제외 후보 구분
- 제외 사유 반환

알레르기 충돌 메뉴는 최종 추천에 포함하지 않는다.

## 10. 메뉴 목 데이터

`search.py`에는 메뉴 ID, 이름, 분류, 식사 시간, 1인 가격, 태그, 재료, 맵기, 국물 및 간편식 여부를 가진 Python `list/dict` 상수를 둔다. `dietary_check.py`에는 메뉴 ID별 알레르기, 열량, 단백질과 영양 참고 문구를 가진 Python `list/dict` 상수를 둔다.

Happy Case가 성공하도록 2인 30,000원 이하의 따뜻한 한식 메뉴와 대체 메뉴를 포함한다.

## 11. 메뉴 Agent 실행 순서

```text
요청 검증
→ search_menus
→ 후보 확인
→ check_dietary_conditions
→ 충돌 메뉴 제거
→ 최종 추천과 대체 메뉴 선정
→ 추천 이유 생성
→ MenuRecommendationResponse 반환
```

두 Tool은 Registry와 안전 실행기를 통해 위 순서로 실행한다.

## 12. 메뉴 추천 테스트

1. 기본 Happy Case가 HTTP 200을 반환한다.
2. 두 Tool이 모두 실행된다.
3. 예산 이하 메뉴만 반환한다.
4. 제외 음식 및 알레르기 충돌 메뉴를 반환하지 않는다.
5. 잘못된 식사 시간, 인원, 예산은 검증 오류가 발생한다.
6. 결과가 없으면 후속 질문을 반환한다.
7. 외부 API 키 없이 동작한다.
8. 내부 예외를 노출하지 않는다.

# Part B. 학습 도우미 AI Agent

## 13. 담당자 및 파일

학습 도우미 AI Agent 백엔드는 `yb`가 담당한다.

```text
backend/app/agents/learning_assistant_agent.py
backend/app/routers/learning_assistant_router.py
backend/app/schemas/learning_assistant.py
backend/app/services/learning_assistant_service.py
backend/app/tools/learning/study_plan.py
backend/app/tools/learning/quiz.py
backend/tests/test_learning_assistant_api.py
```

## 14. 학습 도우미 API

```http
POST /api/learning/assist
```

요청 예시:

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

| 필드 | 검증 |
|---|---|
| `subject` | 필수, 1~100자 |
| `goal` | 필수, 1~500자 |
| `level` | 초급, 중급, 고급 |
| `studyMinutes` | 10~240분 |
| `learningStyle` | 필수, 1~100자 |
| `difficultConcepts` | 최대 10개 |

## 15. 학습 도우미 Schema

`backend/app/schemas/learning_assistant.py`에 다음 모델을 구현한다.

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

과목, 목표, 수준, 학습 시간, 단계별 시간 합계, 문제 수, 정답·해설과 추가 필드를 검증한다.

## 16. 학습 도우미 Tool

### `create_study_plan`

파일: `backend/app/tools/learning/study_plan.py`

- 과목과 목표 관련 콘텐츠 검색
- 수준에 맞는 콘텐츠 필터
- 전체 시간을 단계별로 배분
- 개념, 예제, 연습 순서 생성
- 다음 학습 주제 제안

단계별 시간 합계는 요청의 `studyMinutes`와 일치해야 한다.

### `create_quiz`

파일: `backend/app/tools/learning/quiz.py`

- 학습 계획의 주제와 콘텐츠 ID 사용
- 수준에 맞는 퀴즈 템플릿 조회
- 문제, 선택지, 정답, 해설 구성
- 중복 문제 제거
- 답안이 제공되면 채점 결과 반환

1차 구현은 목 데이터 기반 문제 생성과 정답·해설 반환을 범위로 한다.

## 17. 학습 목 데이터

- `study_plan.py`: 과목, 수준, 주제, 개념, 예제와 예상 시간을 Python `list/dict` 상수로 관리한다.
- `quiz.py`: 문제, 선택지, 정답과 해설을 Python `list/dict` 상수로 관리한다.

Happy Case가 성공하도록 Python 초급 반복문 콘텐츠와 퀴즈를 반드시 포함한다.

## 18. 학습 Agent 실행 순서

```text
요청 검증
→ create_study_plan
→ 학습 계획 확인
→ 첫 번째 Tool 결과의 주제로 create_quiz
→ 학습 계획과 퀴즈 조합
→ 핵심 개념 및 다음 학습 추천 생성
→ LearningAssistantResponse 반환
```

두 Tool은 Registry와 안전 실행기를 통해 위 순서로 실행한다.

## 19. 학습 도우미 테스트

1. 기본 Happy Case가 HTTP 200을 반환한다.
2. 두 Tool이 모두 실행된다.
3. 단계별 시간 합계가 요청 시간과 일치한다.
4. 요청 수준과 일치하는 콘텐츠만 반환한다.
5. 퀴즈에 문제, 정답, 해설이 포함된다.
6. 잘못된 수준과 학습 시간은 검증 오류가 발생한다.
7. 지원하지 않는 과목은 후속 질문을 반환한다.
8. 외부 API 키 없이 동작한다.
9. 내부 예외를 노출하지 않는다.

## 20. 공통 파일 작업과 충돌 방지

두 담당자가 함께 수정할 가능성이 있는 파일은 다음과 같다.

```text
backend/app/main.py
backend/app/agents/runtime.py
backend/app/providers/mock.py
backend/app/tools/registry.py
```

작업 원칙:

- 도메인 구현은 가능한 한 각 담당자의 신규 파일 안에서 완료한다.
- `main.py`에는 Router 등록 코드만 추가한다.
- `registry.py`에는 담당 Tool 두 개씩만 등록한다.
- 도메인 규칙을 공통 Runtime에 넣지 않는다.
- 목 데이터는 각 담당 Tool 파일 안에서 관리하며 공통 데이터 서비스는 만들지 않는다.
- 공통 파일 수정 사항은 개인 MD에 명시한다.

권장 통합 순서:

```text
1. Agent별 Schema와 Tool 내부 목 데이터
2. Agent별 Tool
3. Tool Registry 통합
4. Agent와 Service
5. Router
6. main.py Router 등록
7. Agent별 테스트
8. 전체 회귀 테스트
```

## 21. 개인 MD 작성 기준

### `tk.md`

메뉴 추천 Agent 목표, 담당 파일, 요청·응답 모델, Tool 두 개, 목 데이터, 실행 순서, 예외 처리, Happy Case, 테스트, 공통 파일 수정 내용과 완료 기준을 작성한다.

### `yb.md`

학습 도우미 Agent 목표, 담당 파일, 요청·응답 모델, Tool 두 개, 목 데이터, 실행 순서, 예외 처리, Happy Case, 테스트, 공통 파일 수정 내용과 완료 기준을 작성한다.

## 22. Backend Happy Case

### 메뉴 추천

```json
{
  "mealTime": "저녁",
  "people": 2,
  "budget": 30000,
  "preferences": ["한식", "따뜻한 음식"],
  "excludedFoods": [],
  "allergies": [],
  "spicyLevel": "보통"
}
```

HTTP 200, 두 Tool 성공, 예산 이하 추천, 추천 이유와 가격 포함, 외부 API 키 불필요를 만족해야 한다.

### 학습 도우미

```json
{
  "subject": "Python",
  "goal": "반복문 기초 이해",
  "level": "초급",
  "studyMinutes": 30,
  "learningStyle": "예제와 문제 풀이"
}
```

HTTP 200, 두 Tool 성공, 단계 합계 30분, 반복문 개념·예제·문제·해설 포함, 외부 API 키 불필요를 만족해야 한다.

## 23. 백엔드 완료 기준

- 메뉴 추천 API와 학습 도우미 API가 정상 동작한다.
- 두 Agent가 각각 자신의 Tool 두 개를 실행한다.
- 모든 Tool이 Registry와 안전 실행기를 통해 실행된다.
- 요청·응답과 Tool arguments가 Pydantic으로 검증된다.
- DB와 JSON 파일 없이 Tool 내부 Python 목 데이터로 동작한다.
- Mock Provider가 기본 Happy Case를 지원한다.
- 외부 API 키 없이 처음 실행할 수 있다.
- 내부 오류와 Stack Trace가 사용자에게 노출되지 않는다.
- Agent별 테스트와 기존 백엔드 테스트가 모두 통과한다.
- 프론트엔드에서 사용할 API 계약이 확정되어 있다.
