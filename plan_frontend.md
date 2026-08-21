# Frontend 구현 계획

## 1. 목표

현재 `frontend/`의 01~17 페이지는 구현 방식과 코드 구조를 참고하기 위한 학습 예제다. 최종 결과물에는 기존 예제 화면을 포함하지 않고, 이번 프로젝트에서 만드는 다음 두 Agent 화면만 남긴다.

1. 메뉴 추천 AI Agent
2. 학습 도우미 AI Agent

기존 예제의 Streamlit 구성, API 호출, 로딩 및 오류 처리 방식은 참고하되 사용자에게 노출되는 화면과 최종 코드 구조는 신규 기능 중심으로 정리한다.

> 이 계획은 `master.md`의 “01~17 유지 후 18~19 추가” 방침을 “기존 예제는 참고 후 제외하고 신규 2개 화면만 유지”하는 것으로 변경한다. 이후 `master.md`의 프론트엔드 구조도 같은 내용으로 갱신해야 한다.

## 2. 참고할 기존 코드

| 참고 파일 | 참고 내용 |
|---|---|
| `frontend/app.py` | `st.Page`, `st.navigation`, 사이드바 구성 |
| `frontend/app_pages/17_agent_cycle.py` | 입력 → Tool 실행 → 최종 답변 표시 흐름 |
| `frontend/app_pages/04_travel_classifier.py` | 간단한 폼과 `BackendAPIError` 처리 |
| `frontend/clients/agent_client.py` | 화면과 백엔드 API 사이의 함수 구조 |
| `frontend/core/api_client.py` | 공통 HTTP, timeout, 연결 오류 처리 |

참고가 끝난 뒤 01~17 예제 페이지와 예제 전용 Client 함수는 최종 프론트엔드에서 제거한다.

## 3. 최종 디렉터리 구조

```text
frontend/
├─ app.py
├─ app_pages/
│  ├─ 01_menu_recommendation.py
│  └─ 02_learning_assistant.py
├─ clients/
│  ├─ __init__.py
│  └─ agent_client.py
└─ core/
   ├─ __init__.py
   └─ api_client.py
```

### 유지

- `app.py`: 신규 Agent 두 개만 등록하도록 재작성
- `clients/agent_client.py`: 신규 Agent API 함수만 유지
- `core/api_client.py`: 기존 공통 HTTP와 오류 처리 재사용
- 각 `__init__.py`: 패키지 구조 유지

### 신규

- `app_pages/01_menu_recommendation.py`
- `app_pages/02_learning_assistant.py`

### 최종 결과에서 제외

- 기존 `app_pages/01_home.py`부터 `17_agent_cycle.py`까지
- 개념 비교, 여행 분류, Provider, Prompt, Structured Output, Tool 실습, 이미지, TTS 등 예제 전용 Client 함수
- `app.py`의 기존 학습 과정 navigation과 사이드바 항목

백엔드 예제 제거는 이 문서의 범위가 아니다. 프론트엔드에서 예제 API를 호출하거나 노출하지 않는 데까지만 책임진다.

## 4. 최종 사용자 흐름

```text
Streamlit 실행
→ 사이드바에서 Agent 선택
   ├─ 메뉴 추천 Agent
   └─ 학습 도우미 Agent
→ 기본 Happy Case 또는 사용자 조건 입력
→ 요청 버튼 클릭
→ 로딩 표시
→ Tool 실행 결과와 최종 Agent 답변 표시
```

별도 HOME, 학습 예제, 결과 페이지, 요청 이력 페이지는 만들지 않는다. 앱 실행 시 메뉴 추천 Agent를 기본 페이지로 연다.

## 5. API 계약

프론트엔드 작업 전에 백엔드 담당자와 경로와 응답 키를 확정한다. 경로 변경은 페이지가 아니라 `agent_client.py`에만 반영한다.

### 메뉴 추천

```text
POST /api/agents/menu-recommendation
```

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

### 학습 도우미

```text
POST /api/agents/learning-assistant
```

```json
{
  "subject": "Python",
  "goal": "반복문 기초 이해",
  "level": "초급",
  "studyMinutes": 30,
  "learningStyle": "예제와 문제 풀이"
}
```

### 공통 응답

```json
{
  "agentType": "menu_recommendation | learning_assistant",
  "summary": "핵심 답변",
  "recommendations": [],
  "reasoning": [],
  "followUpQuestions": [],
  "toolResults": []
}
```

선택 필드는 `.get()`으로 읽어 빈 배열이나 일부 누락 필드 때문에 렌더링이 중단되지 않게 한다.

## 6. 역할 분담

각자 **Agent 페이지 1개 + 공용 파일 1개**를 맡고 같은 파일을 동시에 수정하지 않는다.

| 담당자 | 소유 파일 | 작업 내용 |
|---|---|---|
| `yj` | `app_pages/01_menu_recommendation.py` | 메뉴 입력, Happy Case, 추천·Tool 결과 렌더링 |
| `yj` | `app.py` | 신규 두 페이지 등록, 기본 페이지와 사이드바 구성 |
| `dy` | `app_pages/02_learning_assistant.py` | 학습 입력, Happy Case, 계획·퀴즈·Tool 결과 렌더링 |
| `dy` | `clients/agent_client.py` | 기존 예제 함수 정리, 신규 Agent API 함수 2개 구성 |

정리 작업의 소유권도 나눈다.

- `yj`: 기존 `app_pages/01_home.py`~`17_agent_cycle.py` 제거
- `dy`: `agent_client.py`의 기존 예제 전용 함수 제거
- `core/api_client.py`: 수정하지 않음

제거 작업은 신규 기능이 정상 동작한 뒤 별도 커밋으로 수행한다. 기능 구현과 정리를 분리해야 문제 발생 시 쉽게 비교하거나 되돌릴 수 있다.

## 7. `yj` 작업 명세

### 7.1 메뉴 추천 화면

`app_pages/01_menu_recommendation.py`에 다음을 구현한다.

- 제목과 사용 설명
- `st.form` 기반 입력: 식사 시간, 인원, 예산, 선호 음식, 제외 음식, 알레르기, 맵기
- `master.md`의 메뉴 추천 Happy Case 기본값
- 쉼표 구분 문자열을 공백과 빈 값을 제거한 `list[str]`로 변환
- 요청 중 `st.spinner` 표시
- 성공 시 핵심 요약, 추천 메뉴, 이유, 가격, 대체 메뉴, 후속 질문 순서로 표시
- Tool 결과는 `st.expander` 안의 `st.json`으로 표시
- `BackendAPIError` 발생 시 서버 확인과 재시도 안내
- 결과가 비었을 때 사용자용 안내 표시

```python
from clients.agent_client import run_menu_recommendation
```

### 7.2 앱 진입 구조

`app.py`에는 다음 두 페이지만 등록한다.

```python
menu = st.Page(
    "app_pages/01_menu_recommendation.py",
    title="메뉴 추천 Agent",
    default=True,
)
learning = st.Page(
    "app_pages/02_learning_assistant.py",
    title="학습 도우미 Agent",
)
```

- `st.navigation`에는 `menu`, `learning`만 포함
- 사이드바에는 두 Agent 링크만 표시
- 기존 과정명, 단계별 expander, 환경 상태 링크 제거
- 앱 제목은 두 Agent를 포괄하는 프로젝트명으로 변경

### 7.3 예제 페이지 정리

신규 페이지 등록과 검증 후 기존 01~17 파일을 제거한다. 새 파일 번호가 기존 파일과 겹치므로 다음 순서로 진행한다.

1. 신규 페이지를 충돌하지 않는 임시 이름으로 구현
2. 기존 예제 페이지 제거
3. 신규 페이지를 최종 이름 `01_menu_recommendation.py`, `02_learning_assistant.py`로 변경
4. `app.py`의 페이지 경로 확인

예제 제거와 이름 정리는 기능 구현과 별도 커밋으로 남긴다.

## 8. `dy` 작업 명세

### 8.1 학습 도우미 화면

`app_pages/02_learning_assistant.py`에 다음을 구현한다.

- 제목과 사용 설명
- `st.form` 기반 입력: 과목, 학습 목표, 수준, 학습 시간, 학습 방식
- `master.md`의 학습 Happy Case 기본값
- 학습 시간은 양의 정수로 제한
- 요청 중 `st.spinner` 표시
- 성공 시 요약, 시간별 계획, 개념, 예제, 문제, 정답·해설, 다음 학습 추천 순서로 표시
- Tool 결과는 `st.expander` 안의 `st.json`으로 표시
- `BackendAPIError`와 빈 응답 처리

```python
from clients.agent_client import run_learning_assistant
```

### 8.2 Agent Client 정리

`clients/agent_client.py`는 최종적으로 다음 두 호출 함수만 제공한다.

```python
from typing import Any

from core.api_client import request


def run_menu_recommendation(payload: dict[str, Any]):
    return request("POST", "/api/agents/menu-recommendation", json=payload)


def run_learning_assistant(payload: dict[str, Any]):
    return request("POST", "/api/agents/learning-assistant", json=payload)
```

- 예제 전용 API 함수와 사용하지 않는 `request_bytes`, `upload` import 제거
- 백엔드 경로 변경은 이 파일에만 반영
- 화면에서 받은 payload를 임의로 변경하지 않음

## 9. 브랜치와 머지 순서

```text
main
├─ feature/frontend-yj-menu
└─ feature/frontend-dy-learning
```

1. API 계약과 Client 함수 이름을 확정한다.
2. `dy`가 신규 API 함수 2개의 선행 커밋을 공유한다.
3. `yj`가 해당 커밋을 반영해 메뉴 페이지를 연동한다.
4. 두 사람이 각자 Agent 페이지를 병렬 구현한다.
5. `dy`의 학습 페이지와 Client 변경을 먼저 머지한다.
6. `yj`가 최신 `main`을 반영하고 `app.py`에 두 페이지만 등록한다.
7. 두 신규 페이지의 정상 동작을 확인한다.
8. `yj`가 기존 01~17 페이지를 별도 커밋으로 제거한다.
9. `dy`가 Client의 예제 함수를 별도 커밋으로 제거한다.
10. 최종 구조와 Happy Case를 함께 검증한다.

권장 커밋:

```text
feat(frontend): add agent API client functions
feat(frontend): add learning assistant page
feat(frontend): add menu recommendation page
refactor(frontend): register project agent pages only
refactor(frontend): remove legacy example pages
refactor(frontend): remove legacy example API clients
```

## 10. 충돌 방지 규칙

- `app.py`, 메뉴 추천 페이지는 `yj`만 수정한다.
- `agent_client.py`, 학습 도우미 페이지는 `dy`만 수정한다.
- `api_client.py`는 수정하지 않는다.
- 상대방 소유 파일을 포맷팅하거나 함께 정리하지 않는다.
- 전체 `frontend/` 대상 자동 포맷은 실행하지 않는다.
- 예제 제거는 신규 기능 구현과 다른 커밋으로 남긴다.
- `README.md`에는 현재 충돌 마커가 있으므로 수정하지 않는다.
- 머지 전 `git diff main...HEAD -- frontend`로 담당 외 변경을 확인한다.

## 11. 검증 체크리스트

### 최종 구조

- [ ] `app_pages/`에 신규 Agent 페이지 2개만 존재한다.
- [ ] `app.py`에 두 페이지만 등록되어 있다.
- [ ] 사이드바에 두 Agent 링크만 표시된다.
- [ ] 실행 시 메뉴 추천 페이지가 기본으로 열린다.
- [ ] 기존 학습 예제 링크와 페이지 코드가 남지 않는다.
- [ ] `agent_client.py`에 신규 Agent 호출 함수만 남는다.

### 메뉴 추천

- [ ] 기본값 그대로 버튼 한 번으로 요청된다.
- [ ] 추천 메뉴, 이유, 가격, 대체 메뉴가 표시된다.
- [ ] 메뉴 검색과 식단 검증 Tool 결과가 표시된다.
- [ ] 서버 오류와 timeout이 같은 화면에서 안내된다.

### 학습 도우미

- [ ] 기본값 그대로 버튼 한 번으로 요청된다.
- [ ] 30분 계획, 개념, 예제, 문제와 해설이 표시된다.
- [ ] 학습 계획과 퀴즈 Tool 결과가 표시된다.
- [ ] 서버 오류와 timeout이 같은 화면에서 안내된다.

### 코드

- [ ] 신규 파일이 Python 문법 검사를 통과한다.
- [ ] 페이지 import와 Client 함수 이름이 일치한다.
- [ ] 제거된 예제 페이지나 Client 함수를 참조하는 코드가 없다.
- [ ] 외부 API 키와 DB 없이 Mock Provider로 두 기능이 동작한다.
- [ ] 담당 범위 밖의 불필요한 변경이 없다.

## 12. 완료 기준

- 최종 프론트엔드에는 메뉴 추천과 학습 도우미 화면만 존재한다.
- 두 화면 모두 기본값, 사용자 입력, 로딩, 결과, Tool 결과, 오류 상태를 한 페이지에서 제공한다.
- API 호출은 정리된 `agent_client.py`, HTTP 처리는 기존 `api_client.py`를 사용한다.
- 기존 예제는 구현 참고 역할만 하고 최종 navigation과 `app_pages/`에서 제거된다.
- `yj`, `dy`가 각각 페이지 1개와 공용 파일 1개를 맡고 같은 파일을 동시에 수정하지 않는다.
