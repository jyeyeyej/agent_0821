# TK 메뉴 추천 AI Agent 백엔드 구현 명세

## 1. 문서 목적

이 문서는 `tk`가 담당하는 **메뉴 추천 AI Agent 백엔드**의 구현 범위와 API 계약을 고정한다. 수정된 `master.md`의 공통 정책과 백엔드 상세 설계서의 세부 구현 기준을 함께 적용한다.

수정된 `master.md`와 백엔드 상세 설계서는 목 데이터 정책이 일치한다. 메뉴 목 데이터는 별도의 JSON 파일이나 `backend/app/mock_data/` 폴더를 만들지 않고, 지정된 Tool Python 파일 내부의 `list`/`dict` 모듈 상수로만 관리한다. Agent는 이 데이터에 직접 접근하지 않고 반드시 Tool 실행 결과를 사용한다.

이 문서가 승인되기 전에는 `tk.md` 이외의 기존 파일, 소스 코드 및 디렉터리 구조를 변경하지 않는다.

## 2. 담당 목표

사용자의 식사 조건을 검증하고 두 개의 등록된 Tool을 순서대로 안전하게 실행하여 다음 정보를 반환한다.

- 조건에 맞는 메뉴 추천 목록
- 메뉴별 추천 이유
- 총 예상 가격
- 영양 및 식단 참고 정보
- 대체 메뉴
- 결과가 없을 때의 후속 질문

데이터베이스, JSON 목 데이터 파일과 외부 메뉴 API는 사용하지 않으며, 외부 API 키 없이 Mock Provider 환경에서 Happy Case가 항상 같은 결과를 반환해야 한다.

## 3. 역할 및 파일 소유권

### 3.1 TK 전용 신규 파일

`tk`는 아래 파일만 독점적으로 생성·수정한다.

```text
backend/app/agents/menu_recommendation_agent.py
backend/app/routers/menu_recommendation_router.py
backend/app/schemas/menu_recommendation.py
backend/app/services/menu_recommendation_service.py
backend/app/tools/menu/__init__.py
backend/app/tools/menu/search.py
backend/app/tools/menu/dietary_check.py
backend/tests/test_menu_recommendation_api.py
```

새로 생성할 수 있는 TK 담당 폴더는 아래 하나뿐이다.

```text
backend/app/tools/menu/
```

### 3.2 재사용만 하는 기존 파일

아래 파일은 TK 도메인 코드에서 import하여 사용하되 직접 수정하지 않는다.

```text
backend/app/core/config.py
backend/app/schemas/common.py
backend/app/tools/executor.py
backend/app/providers/base.py
backend/app/providers/registry.py
```

별도의 `validation/`, `mock_data/`, `data/`, `utils/`, `models/` 폴더를 만들지 않는다. `.json` 목 데이터 파일과 `mock_data_service.py`도 추가하지 않는다. `learning_unit/`, `starter/`, `solution/`, `.venv/`, `.pytest_cache/`는 신규 Agent 구현에 복제하거나 수정하지 않는다.

### 3.3 다른 담당자의 파일

다음 영역은 TK가 생성하거나 수정하지 않는다.

```text
frontend/**
backend/app/agents/learning_assistant_agent.py
backend/app/routers/learning_assistant_router.py
backend/app/schemas/learning_assistant.py
backend/app/services/learning_assistant_service.py
backend/app/tools/learning/**
backend/tests/test_learning_assistant_api.py
yb.md
yj.md
dy.md
```

## 4. 공유 파일 충돌 방지 규칙

다음 네 파일은 TK와 YB가 동시에 수정하면 충돌할 가능성이 높은 공유 통합 파일이다.

```text
backend/app/main.py
backend/app/agents/runtime.py
backend/app/providers/mock.py
backend/app/tools/registry.py
```

공유 파일에는 아래 규칙을 적용한다.

1. TK와 YB는 각자 기능 브랜치에서 공유 파일을 동시에 수정하지 않는다.
2. 구현 시작 전에 공유 파일을 수정할 **통합 담당자 한 명**을 정한다.
3. TK는 전용 파일 구현을 완료한 뒤 필요한 import, Router 등록, Tool 등록, Runtime 호출 계약을 통합 담당자에게 전달한다.
4. 통합 담당자만 최신 통합 브랜치에서 공유 파일 네 개를 한 번에 수정한다.
5. `main.py`에는 Router 등록만, `registry.py`에는 ToolSpec 등록만 추가한다.
6. `runtime.py`에는 도메인 추천 규칙이나 메뉴 목 데이터를 넣지 않는다.
7. `mock.py`에는 공통 Provider 동작만 두고 메뉴 검색·필터·알레르기 규칙을 넣지 않는다.
8. 공유 파일 통합 후 TK의 메뉴 API 테스트와 기존 회귀 테스트를 함께 실행한다.

통합 담당자에게 전달할 TK 측 변경 계약은 다음과 같다.

| 공유 파일 | 필요한 통합 내용 |
|---|---|
| `main.py` | `menu_recommendation_router` import 및 `app.include_router(...)` 한 줄 추가 |
| `tools/registry.py` | `search_menus`, `check_dietary_conditions` ToolSpec 두 개 등록 |
| `agents/runtime.py` | 지정된 Tool 두 개를 순서대로 안전 실행하고 Trace를 누적할 수 있는 공용 실행 경로 제공 |
| `providers/mock.py` | 외부 API 키 없이 결정적 최종 응답을 만들 수 있는 공용 Mock 동작 지원 |

공유 파일의 실제 수정자는 구현 승인 시 별도로 확정한다. 확정 전 TK는 위 네 파일을 수정하지 않는다.

## 5. API 계약

### 5.1 Endpoint

```http
POST /api/menu/recommend
Content-Type: application/json
```

### 5.2 요청 예시

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

JSON 필드는 camelCase를 사용하고 Python 내부 필드는 snake_case를 사용한다. Pydantic alias로 두 표현을 연결하며 응답 직렬화는 camelCase로 고정한다.

### 5.3 요청 검증

| 필드 | 형식 및 제약 |
|---|---|
| `mealTime` | `아침`, `점심`, `저녁`, `야식` 중 하나 |
| `people` | 정수 1~20 |
| `budget` | 정수, 1,000원 이상 |
| `preferences` | 문자열 배열, 최대 10개 |
| `excludedFoods` | 문자열 배열, 최대 20개 |
| `allergies` | 문자열 배열, 최대 20개 |
| `spicyLevel` | `안 매움`, `보통`, `매움` 중 하나 |
| `hasSoup` | boolean 또는 null, 기본값 null |
| `quickMeal` | boolean, 기본값 false |

문자열 배열의 빈 문자열과 공백 문자열은 허용하지 않으며, 선언되지 않은 추가 필드는 `ConfigDict(extra="forbid")`로 거부한다.

### 5.4 공통 응답 예시

```json
{
  "agentType": "menu_recommendation",
  "summary": "2인 저녁 메뉴로 소고기 불고기 정식을 추천합니다.",
  "recommendations": [
    {
      "menuId": "menu-001",
      "name": "소고기 불고기 정식",
      "reason": "예산 안에서 따뜻한 한식 조건과 잘 맞습니다.",
      "totalPrice": 28000,
      "nutritionNote": "단백질을 포함한 한 끼 식사입니다.",
      "isAlternative": false
    }
  ],
  "reasoning": [
    "식사 시간, 인원, 예산 조건으로 후보를 검색했습니다.",
    "알레르기와 제외 음식 충돌 여부를 확인했습니다."
  ],
  "followUpQuestions": [],
  "toolResults": [
    {
      "toolName": "search_menus",
      "success": true,
      "data": {}
    },
    {
      "toolName": "check_dietary_conditions",
      "success": true,
      "data": {}
    }
  ]
}
```

`recommendations`에는 안전 검증을 통과한 메뉴만 포함한다. 첫 번째 항목은 주 추천이며 이후 항목은 대체 메뉴로 표시한다. 결과가 없으면 빈 배열과 사용자가 조건을 조정할 수 있는 `followUpQuestions`를 반환한다.

## 6. Schema 범위

`backend/app/schemas/menu_recommendation.py`에 아래 모델을 둔다.

```text
MenuRecommendationRequest
MenuSearchArgs
DietaryCheckArgs
MenuCandidate
MenuRecommendationItem
MenuRecommendationResponse
```

책임은 다음과 같이 분리한다.

- `MenuRecommendationRequest`: API 요청과 사용자 입력 검증
- `MenuSearchArgs`: `search_menus` 실행 인자 검증
- `DietaryCheckArgs`: 후보 ID, 알레르기, 제외 음식 검증
- `MenuCandidate`: 첫 번째 Tool의 후보 계약
- `MenuRecommendationItem`: 프론트엔드에 표시할 추천 항목 계약
- `MenuRecommendationResponse`: 공통 Agent 응답 형식 및 추천 개수 검증

기존 `schemas/common.py`를 재사용할 수 있는 경우 import하되, 메뉴 전용 필드나 규칙을 공통 Schema에 추가하지 않는다.

## 7. Tool 설계

### 7.1 `search_menus`

파일: `backend/app/tools/menu/search.py`

역할:

1. 식사 시간과 인원 조건을 확인한다.
2. `1인 가격 × 인원`이 예산 이하인 메뉴만 남긴다.
3. 제외 음식, 맵기, 국물 여부, 간편식 여부를 필터링한다.
4. 선호 음식과 태그 일치에 가중치를 부여한다.
5. 적합도 점수의 내림차순, 총 가격의 오름차순, 메뉴 ID의 오름차순으로 정렬하여 결정적 결과를 만든다.
6. 후보가 없더라도 조건을 임의로 완화하지 않고 빈 결과를 반환한다.

`master.md`의 "Tool 결과가 없으면 Tool 내부 Python 목 데이터의 기본 결과를 사용한다"는 정책은 외부 API나 DB 대신 Tool 내부 기본 데이터셋을 조회한다는 의미로 적용한다. 필터 결과가 비었다는 이유로 예산, 알레르기, 제외 음식 등의 사용자 조건을 무시한 기본 메뉴를 강제로 추천하지 않는다.

Tool 내부 목 데이터 필수 항목:

```text
menu_id, name, category, meal_times, price_per_person,
tags, ingredients, spicy_level, has_soup, quick_meal
```

출력 핵심 필드:

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

### 7.2 `check_dietary_conditions`

파일: `backend/app/tools/menu/dietary_check.py`

역할:

1. `search_menus`가 반환한 후보 ID만 입력받는다.
2. 알레르기 항목과 재료 충돌을 확인한다.
3. 제외 음식 포함 여부를 다시 확인한다.
4. 메뉴 ID별 열량, 단백질 및 영양 참고 문구를 연결한다.
5. 안전 후보와 제외 후보를 분리하고 제외 사유를 반환한다.

Tool 내부 목 데이터 필수 항목:

```text
menu_id, allergens, calories_kcal, protein_g, nutrition_note
```

알레르기 또는 제외 음식과 충돌한 후보는 최종 추천에 절대 포함하지 않는다.

### 7.3 Tool 실행 원칙

- Tool 함수는 Agent에서 직접 호출하지 않는다.
- 두 Tool 모두 `tools/registry.py`의 `ToolSpec`에 등록한다.
- 두 Tool 모두 `tools/executor.py`의 `execute_tool_safely`를 통해 실행한다.
- Tool은 Pydantic 모델로 인자를 검증한다.
- Tool은 외부 상태를 변경하지 않는 순수 조회·가공 함수로 구현한다.
- Tool 데이터와 결과의 정렬은 매 실행마다 동일해야 한다.

## 8. Service와 Agent 책임

### Router

- HTTP 요청 수신 및 응답 모델 지정
- Pydantic 검증 결과를 Service에 전달
- 내부 예외나 Stack Trace를 응답에 노출하지 않음
- 메뉴 추천 규칙을 작성하지 않음

### Service

- Router와 Agent 사이의 유스케이스 경계
- 요청을 Agent 실행 인자로 전달
- 복구 불가능한 Agent 오류를 사용자용 표준 오류로 변환
- Tool 필터링 규칙을 중복 구현하지 않음

### Agent

- Tool 실행 순서와 결과 조합을 담당
- 첫 번째 Tool의 후보를 두 번째 Tool의 입력으로 전달
- 안전 후보로 추천과 대체 메뉴를 구성
- Mock 환경에서도 결정적 요약과 추천 이유를 생성
- Tool 내부 목 데이터에 직접 접근하지 않음

## 9. 실행 순서

```text
MenuRecommendationRequest 검증
→ search_menus 인자 구성
→ Registry 조회 및 안전 실행
→ 후보 유무 확인
→ check_dietary_conditions 인자 구성
→ Registry 조회 및 안전 실행
→ 충돌 후보 제거
→ 주 추천 및 대체 메뉴 구성
→ MenuRecommendationResponse 검증
→ Frontend 반환
```

첫 번째 Tool 결과가 비어 있어도 처리 흐름과 Trace는 일관되게 유지한다. 두 번째 Tool에는 빈 후보 목록을 전달하거나, 공용 Runtime 계약에서 정의한 안전한 빈 결과를 기록한다. 최종 응답은 추천 없음과 조건 조정 질문을 명확히 반환한다. Tool 내부 기본 데이터셋은 항상 조회 가능하지만, 사용자 안전 조건을 통과하지 못한 메뉴를 fallback으로 반환하지 않는다.

## 10. 오류 처리

| 코드 | 처리 기준 | 사용자 응답 원칙 |
|---|---|---|
| `REQUEST_VALIDATION_ERROR` | API 요청 형식 또는 값 오류 | 잘못된 필드와 허용 범위 안내 |
| `TOOL_NOT_ALLOWED` | Registry에 Tool 없음 | 내부 Tool 이름 노출을 최소화하고 재시도 안내 |
| `TOOL_VALIDATION_ERROR` | Tool 인자 검증 실패 | 입력 조건 확인 안내 |
| `TOOL_EXECUTION_ERROR` | Tool 실행 중 예외 | 내부 예외를 숨기고 재시도 안내 |
| `MOCK_DATA_NOT_FOUND` | 일치하거나 연결 가능한 목 데이터 없음 | 조건 완화를 위한 후속 질문 반환 |
| `AGENT_EXECUTION_ERROR` | 결과 조합 불가 | 일반 오류 메시지와 재시도 방법 반환 |

Stack Trace, 파일 시스템 경로, 환경변수, API 키, 원본 내부 예외 메시지는 클라이언트 응답에 포함하지 않는다.

## 11. Happy Case

기본 입력:

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

성공 조건:

- HTTP 200을 반환한다.
- `search_menus`와 `check_dietary_conditions`가 순서대로 한 번씩 실행된다.
- 총 가격 30,000원 이하의 안전한 메뉴를 반환한다.
- 따뜻한 한식 주 추천과 최소 한 개의 대체 메뉴를 준비한다.
- 추천 이유, 총 가격, 영양 참고 정보가 포함된다.
- `agentType`은 `menu_recommendation`이다.
- `toolResults`에 두 Tool의 실행 순서와 성공 여부가 남는다.
- DB, JSON 목 데이터 파일, 외부 메뉴 API 및 외부 API 키 없이 같은 결과가 반복된다.

## 12. 테스트 범위

`backend/tests/test_menu_recommendation_api.py`에 다음을 검증한다.

1. 기본 Happy Case가 HTTP 200을 반환한다.
2. 두 Tool이 정해진 순서로 모두 실행된다.
3. 반환 메뉴의 총 가격이 요청 예산 이하이다.
4. 제외 음식이 포함된 메뉴를 반환하지 않는다.
5. 알레르기 충돌 메뉴를 반환하지 않는다.
6. 식사 시간, 인원, 예산, 맵기와 추가 필드가 검증된다.
7. 후보가 없으면 빈 추천과 후속 질문을 반환한다.
8. 외부 API 키 없이 Mock 환경에서 동작한다.
9. 내부 예외와 Stack Trace를 응답에 노출하지 않는다.
10. 같은 입력은 같은 추천 순서와 결과를 반환한다.
11. 기존 `backend/tests/` 회귀 테스트가 계속 통과한다.

테스트 파일은 기존 공용 테스트 파일을 수정하지 않고 메뉴 기능 전용 파일로 분리한다.

## 13. 구현 및 통합 순서

```text
1. menu_recommendation.py Schema 작성
2. menu/search.py 목 데이터 및 search_menus 구현
3. menu/dietary_check.py 목 데이터 및 check_dietary_conditions 구현
4. menu_recommendation_agent.py 구현
5. menu_recommendation_service.py 구현
6. menu_recommendation_router.py 구현
7. test_menu_recommendation_api.py 작성
8. 통합 담당자에게 공유 파일 변경 계약 전달
9. 통합 담당자가 Registry, Runtime, Mock, main.py 반영
10. 메뉴 테스트 및 전체 회귀 테스트 실행
```

각 단계는 가능한 한 TK 전용 파일만 변경하는 독립 커밋으로 유지한다. 공유 파일 통합 커밋에는 TK와 YB의 등록 변경을 함께 반영하여 동일 구간을 반복 수정하지 않는다.

## 14. 완료 기준

- 지정된 파일과 `backend/app/tools/menu/` 이외에 신규 파일·폴더를 만들지 않았다.
- TK 전용 파일과 YB·프론트엔드 담당 파일의 소유권이 섞이지 않았다.
- 공유 파일은 지정된 통합 담당자 한 명만 수정했다.
- 메뉴 요청·응답과 Tool 인자가 Pydantic으로 검증된다.
- 두 Tool이 Registry와 안전 실행기를 통해 정해진 순서로 실행된다.
- 목 데이터는 `search.py`와 `dietary_check.py` 내부의 Python `list`/`dict` 모듈 상수로만 관리된다.
- `.json` 목 데이터 파일, `backend/app/mock_data/` 및 `mock_data_service.py`가 생성되지 않았다.
- 알레르기 및 제외 음식 충돌 메뉴가 최종 결과에서 제거된다.
- 공통 응답 형식과 camelCase API 계약을 지킨다.
- 최초 Happy Case가 외부 API 키와 DB 없이 성공한다.
- 메뉴 기능 테스트와 기존 백엔드 회귀 테스트가 모두 통과한다.
- 내부 오류 상세와 Stack Trace가 사용자에게 노출되지 않는다.

## 15. 구현 승인 전 체크포인트

코드 작업을 시작하기 전에 아래 두 항목을 확정한다.

1. 공유 파일 네 개의 단일 통합 담당자
2. TK 전용 파일 목록과 본 API 계약에 대한 승인

승인 전에는 이 문서 외의 프로젝트 파일을 변경하지 않는다.
