# AI Agent 프로젝트 마스터 설계서

## 1. 프로젝트 목표

현재 프로젝트와 별개로 다음 두 가지 독립 AI Agent를 구축한다.

1. 메뉴 추천 AI Agent
2. 학습 도우미 AI Agent

두 Agent 모두 데이터베이스를 사용하지 않으며, 초기 개발과 데모에 필요한 데이터는 코드 기반 목(Mock) 데이터로 관리한다.

## 2. 문서 구조

프로젝트 전체 설계는 본 `master.md`가 담당하며, 세부 구현 문서는 역할별로 분리한다.

```text
master.md
├─ frontend.md
│  ├─ yj.md
│  └─ dy.md
└─ backend.md
   ├─ tk.md
   └─ yb.md
```

- `master.md`: 전체 목표, 구조, 공통 정책, 역할 분담
- `frontend.md`: 화면 구성, 사용자 흐름, API 연동 방식
- `backend.md`: 서버 구조, Agent 오케스트레이션, 목 데이터 정책
- `yj.md`, `dy.md`, `tk.md`, `yb.md`: 개인별 담당 파트의 기능, 구현 범위, 작업 내역 및 완료 기준

## 3. 프로젝트 디렉터리 원칙

현재 폴더의 기존 `frontend/`와 `backend/` 구조를 그대로 사용한다. 메뉴 추천과 학습 도우미 기능은 현재 코드의 페이지, 라우터, 스키마, Agent, Service, Tool 분리 방식에 맞춰 추가한다. 이미 존재하며 공통으로 사용할 수 있는 폴더는 새로 생성하지 않는다.

```text
project-root/
├─ frontend/                              # 기존 폴더 재사용
│  ├─ app.py
│  ├─ app_pages/                          # 기존 폴더에 파일 추가
│  │  ├─ 18_menu_recommendation.py        # 신규 파일
│  │  └─ 19_learning_assistant.py         # 신규 파일
│  ├─ clients/                            # 기존 폴더 재사용
│  │  └─ agent_client.py
│  └─ core/                               # 기존 폴더 재사용
│     └─ api_client.py
├─ backend/                               # 기존 폴더 재사용
│  ├─ app/                                # 기존 폴더 재사용
│  │  ├─ main.py
│  │  ├─ agents/                          # 기존 폴더에 파일 추가
│  │  │  ├─ runtime.py
│  │  │  ├─ menu_recommendation_agent.py  # 신규 파일
│  │  │  └─ learning_assistant_agent.py   # 신규 파일
│  │  ├─ core/                            # 기존 폴더 재사용
│  │  │  └─ config.py
│  │  ├─ providers/                       # 기존 폴더 재사용
│  │  │  ├─ base.py
│  │  │  ├─ mock.py
│  │  │  └─ registry.py
│  │  ├─ routers/                         # 기존 폴더에 파일 추가
│  │  │  ├─ menu_recommendation_router.py # 신규 파일
│  │  │  └─ learning_assistant_router.py  # 신규 파일
│  │  ├─ schemas/                         # 기존 폴더에 파일 추가
│  │  │  ├─ common.py
│  │  │  ├─ menu_recommendation.py        # 신규 파일
│  │  │  └─ learning_assistant.py         # 신규 파일
│  │  ├─ services/                        # 기존 폴더에 파일 추가
│  │  │  ├─ menu_recommendation_service.py # 신규 파일
│  │  │  └─ learning_assistant_service.py  # 신규 파일
│  │  ├─ tools/                           # 기존 폴더 재사용
│  │  │  ├─ executor.py
│  │  │  ├─ registry.py
│  │  │  ├─ menu/                         # 신규 폴더
│  │  │  │  ├─ search.py                  # 신규 파일
│  │  │  │  └─ dietary_check.py           # 신규 파일
│  │  │  └─ learning/                     # 신규 폴더
│  │  │     ├─ study_plan.py              # 신규 파일
│  │  │     └─ quiz.py                    # 신규 파일
│  └─ tests/                              # 기존 폴더에 파일 추가
│     ├─ test_menu_recommendation_api.py   # 신규 파일
│     └─ test_learning_assistant_api.py    # 신규 파일
├─ master.md
├─ frontend.md
├─ backend.md
├─ yj.md
├─ dy.md
├─ tk.md
└─ yb.md
```

### 새로 추가하지 않아도 되는 공통 폴더

다음 폴더는 현재 프로젝트에 이미 존재하며 두 Agent에서 공통으로 사용할 수 있으므로 다시 만들지 않는다.

```text
frontend/
frontend/app_pages/
frontend/clients/
frontend/core/
backend/
backend/app/
backend/app/agents/
backend/app/core/
backend/app/providers/
backend/app/routers/
backend/app/schemas/
backend/app/services/
backend/app/tools/
backend/tests/
```

- `frontend/core/`: 기존 HTTP 요청, 연결 오류, 타임아웃 및 JSON 응답 처리를 그대로 사용한다.
- `frontend/clients/`: 기존 `agent_client.py`에 메뉴 추천과 학습 도우미 호출 함수만 추가한다.
- `backend/app/core/`: 기존 환경변수와 공통 설정을 사용한다.
- `backend/app/providers/`: 기존 Provider 구조를 사용하며 `mock.py`에는 Happy Case 응답만 보완한다.
- `backend/app/schemas/`: 기존 Pydantic 검증 구조와 `common.py`를 사용하고 Agent별 스키마 파일만 추가한다.
- `backend/app/tools/`: 기존 안전 실행기와 Registry 구조를 사용하고 신규 Tool을 등록한다.
- `backend/tests/`: 기존 테스트 폴더에 두 Agent의 API 및 Happy Case 테스트 파일만 추가한다.

`learning_unit/`, `starter/`, `solution/`, `.venv/`, `.pytest_cache/`는 신규 Agent의 애플리케이션 구조에 추가하거나 복제하지 않는다.

### 새로 추가해야 하는 폴더

다음 두 개 폴더만 새로 생성한다.

```text
backend/app/tools/menu/
backend/app/tools/learning/
```

- `backend/app/tools/menu/`: 메뉴 검색과 식단 조건 검증 Tool 두 개를 관리한다.
- `backend/app/tools/learning/`: 학습 계획과 퀴즈 생성·채점 Tool 두 개를 관리한다.

그 외 작업은 새로운 폴더 생성이 아니라 기존 폴더에 파일을 추가하거나 기존 공통 파일을 수정하는 방식으로 진행한다.

각 Agent는 현재 `backend/app/tools/`의 구성 방식에 맞춰 자신에게 연결된 Tool 두 개를 사용한다.

| Agent | 담당 Tool |
|---|---|
| 메뉴 추천 AI Agent | `menu/search.py`, `menu/dietary_check.py` |
| 학습 도우미 AI Agent | `learning/study_plan.py`, `learning/quiz.py` |

## 4. 메뉴 추천 AI Agent

### 목적

사용자의 상황, 선호도, 식단 조건을 바탕으로 적절한 메뉴를 추천한다.

### 주요 입력

- 식사 시간: 아침, 점심, 저녁, 야식
- 인원 수
- 예산
- 선호 음식 또는 제외 음식
- 알레르기 및 식단 제한
- 맵기, 국물 여부, 간편식 여부 등 세부 조건

### 주요 출력

- 추천 메뉴 목록
- 메뉴별 추천 사유
- 예상 가격대
- 영양 또는 식단 관련 참고 정보
- 대체 메뉴

### 연결 Tool

1. 메뉴 검색·필터 Tool
2. 메뉴 영양·조건 검증 Tool

세부 규칙과 구현 담당은 `frontend.md`, `backend.md` 및 각 개인별 담당 문서에서 정의한다.

## 5. 학습 도우미 AI Agent

### 목적

사용자의 학습 목표와 현재 수준을 기준으로 학습 계획, 개념 설명, 문제 연습을 지원한다.

### 주요 입력

- 학습 분야 및 과목
- 학습 목표
- 현재 수준
- 확보 가능한 학습 시간
- 선호 학습 방식
- 이해가 어려운 개념 또는 문제

### 주요 출력

- 맞춤형 학습 계획
- 개념 요약 및 예시
- 연습 문제와 해설
- 학습 진도 피드백
- 다음 학습 추천

### 연결 Tool

1. 학습 계획 생성 Tool
2. 문제·퀴즈 생성 및 채점 Tool

세부 규칙과 구현 담당은 `frontend.md`, `backend.md` 및 각 개인별 담당 문서에서 정의한다.

## 6. 공통 백엔드 정책

### Agent 처리 흐름

```text
사용자 요청
→ 요청 유형 및 Agent 선택
→ 필요한 Tool 호출
→ Tool 내부 Python 목 데이터 조회 또는 가공
→ Agent 응답 생성
→ 프론트엔드 반환
```

### 공통 응답 형식

모든 Agent 응답은 다음 정보를 일관되게 포함한다.

```json
{
  "agentType": "menu_recommendation | learning_assistant",
  "summary": "사용자에게 보여 줄 핵심 답변",
  "recommendations": [],
  "reasoning": [],
  "followUpQuestions": [],
  "toolResults": []
}
```

### 오류 처리

- 필수 입력이 부족하면 추가 질문을 반환한다.
- Tool 결과가 없으면 Tool 내부 Python 목 데이터의 기본 결과를 사용한다.
- 내부 오류 상세 내용은 사용자에게 그대로 노출하지 않는다.
- 사용자에게 이해 가능한 대체 안내와 재시도 방법을 제공한다.

## 7. 목 데이터 정책

현재 `mini_agent_03_tool`의 여행·날씨 Tool과 같은 수준으로 구현하기 위해 별도의 JSON 파일이나 `mock_data/` 폴더를 만들지 않는다. 소규모 목 데이터는 각 Tool Python 파일 내부의 `list`와 `dict` 상수로 관리한다.

```text
backend/app/tools/menu/search.py
└─ 메뉴 검색용 Python list/dict 목 데이터

backend/app/tools/menu/dietary_check.py
└─ 영양·알레르기 검증용 Python list/dict 목 데이터

backend/app/tools/learning/study_plan.py
└─ 과목·학습 콘텐츠용 Python list/dict 목 데이터

backend/app/tools/learning/quiz.py
└─ 퀴즈·정답·해설용 Python list/dict 목 데이터
```

목 데이터 관리 원칙은 다음과 같다.

- 현재 프로젝트처럼 Python의 `list`와 `dict`로 작성한다.
- Agent는 목 데이터에 직접 접근하지 않고 Tool을 통해서만 결과를 받는다.
- 목 데이터는 해당 Tool 파일의 모듈 상수로 두고 실행 함수와 분리한다.
- Happy Case와 예외 테스트에 필요한 최소 데이터만 작성한다.
- 별도의 `.json` 파일, `mock_data/` 폴더, `mock_data_service.py`는 추가하지 않는다.

## 8. 프론트엔드 범위

현재 폴더에 구현된 메인 화면은 변경 없이 그대로 사용한다. 기존 사이드바에 다음 두 개의 Agent 페이지를 추가하며, 새로 만드는 프론트엔드 화면은 총 2개다.

1. 메뉴 추천 Agent 화면
2. 학습 도우미 Agent 화면

### 메뉴 추천 Agent 화면

- 사이드바 메뉴를 통해 진입한다.
- 사용자가 메뉴 추천 조건을 입력할 수 있어야 한다.
- Agent가 생성한 추천 결과를 같은 화면에 표시한다.
- 별도의 추천 결과 화면은 만들지 않는다.

### 학습 도우미 Agent 화면

- 사이드바 메뉴를 통해 진입한다.
- 사용자가 과목, 학습 목표, 현재 수준 등 학습 조건을 입력할 수 있어야 한다.
- Agent가 생성한 학습 계획, 개념 설명 또는 문제 결과를 같은 화면에 표시한다.
- 별도의 학습 결과 화면은 만들지 않는다.

### 공통 화면 정책

- 기존 메인 화면과 레이아웃 및 디자인 체계를 유지한다.
- 두 신규 화면 모두 입력 영역과 결과 영역을 하나의 페이지 안에 구성한다.
- 요청 처리 중에는 로딩 상태를 표시한다.
- 요청 실패 시 같은 화면에서 오류 안내와 재시도 방법을 제공한다.
- 별도의 대화 이력 및 요청 이력 화면은 신규 개발 범위에 포함하지 않는다.

세부 화면, 컴포넌트 및 사이드바 연결 방식은 `frontend.md`에서 정의한다.

## 9. 백엔드 범위

백엔드는 다음 기능을 담당한다.

- Agent 요청 수신
- Agent 유형 구분
- Tool 호출 순서 관리
- Tool 내부 Python 목 데이터 조회 및 가공
- 응답 형식 통일
- 오류 처리 및 로그 관리

세부 API, 모듈 구조 및 개별 Agent/Tool 명세는 `backend.md`에서 정의한다.

## 10. 최초 실행 Happy Case

프로젝트를 처음 실행한 사용자가 별도의 설정이나 데이터 입력 없이 두 Agent의 정상 동작을 바로 확인할 수 있도록 기본 Happy Case를 제공한다.

### 공통 동작

- 최초 실행 시 두 신규 페이지에 예시 입력값을 기본으로 채운다.
- 사용자는 기본값을 변경하지 않고 실행 버튼만 눌러 결과를 확인할 수 있다.
- 데이터는 각 Tool Python 파일 내부의 `list`와 `dict`에서 조회한다.
- 외부 API가 설정되지 않아도 Mock Provider를 통해 항상 동일한 정상 결과를 반환한다.
- Tool 실행 결과와 최종 Agent 답변이 한 화면에서 순서대로 표시되어야 한다.

### 메뉴 추천 Happy Case

기본 입력값은 다음과 같다.

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

실행 시 `menu/search.py`가 조건에 맞는 후보를 찾고 `menu/dietary_check.py`가 식단 조건을 검증한다. 최종 화면에는 추천 메뉴, 추천 이유, 예상 가격과 대체 메뉴가 표시되어야 한다.

### 학습 도우미 Happy Case

기본 입력값은 다음과 같다.

```json
{
  "subject": "Python",
  "goal": "반복문 기초 이해",
  "level": "초급",
  "studyMinutes": 30,
  "learningStyle": "예제와 문제 풀이"
}
```

실행 시 `learning/study_plan.py`가 30분 학습 계획을 만들고 `learning/quiz.py`가 연습 문제와 해설을 생성한다. 최종 화면에는 학습 순서, 핵심 개념, 예제, 연습 문제와 해설이 표시되어야 한다.

### Happy Case 완료 기준

- 백엔드와 프론트엔드를 처음 실행한 상태에서 추가 데이터 준비 없이 동작한다.
- 각 페이지에서 실행 버튼 한 번으로 정상 결과가 표시된다.
- 각 Agent가 자신에게 지정된 Tool 두 개를 모두 호출한다.
- 외부 API 키 또는 DB가 없어도 Mock Provider와 목 데이터로 실행된다.
- 기본 Happy Case는 자동화 테스트에서도 검증한다.

## 11. 구현 우선순위

### 1단계: 기본 동작

- 두 Agent의 기본 요청 및 응답 구현
- Agent별 Tool 두 개 구현
- Tool별 Python 목 데이터 생성
- 최초 실행 Happy Case 및 기본 입력값 구현
- 기본 프론트엔드 화면 연결

### 2단계: 사용자 경험 개선

- 조건 입력 UI 개선
- 추천 사유 개인화
- 학습 진도 및 이력 표시
- 재추천 및 후속 질문 기능

### 3단계: 확장 준비

- 실제 외부 API 또는 DB로 교체 가능한 구조 유지
- Tool 추가가 쉬운 모듈 구조 적용
- Agent별 테스트 코드 작성
- Tool 내부 목 데이터 교체 방식 문서화

## 12. 완료 기준

다음 조건을 모두 만족하면 1차 프로젝트 완료로 판단한다.

- 메뉴 추천 AI Agent가 조건 기반 메뉴를 추천한다.
- 학습 도우미 AI Agent가 계획, 설명, 문제 생성 기능을 제공한다.
- 각 Agent가 각각 두 개의 Tool을 호출한다.
- 모든 결과가 목 데이터 기반으로 동작한다.
- 프론트엔드에서 두 Agent를 구분하여 사용할 수 있다.
- DB 없이 로컬 실행 및 데모가 가능하다.
- 최초 실행 시 두 Agent의 Happy Case가 추가 설정 없이 정상 동작한다.
