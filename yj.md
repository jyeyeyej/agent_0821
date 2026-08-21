# yj 프론트엔드 개발 계획서

## 1. 담당 목표

메뉴 추천 AI Agent를 사용자가 바로 실행할 수 있는 Streamlit 화면으로 구현하고, 최종 프론트엔드가 메뉴 추천 Agent와 학습 도우미 Agent 두 화면만 제공하도록 앱 진입 구조를 정리한다.

담당 파일과 책임은 다음과 같다.

| 구분 | 소유 파일 | 책임 |
|---|---|---|
| 신규 기능 | `frontend/app_pages/01_menu_recommendation.py` | 메뉴 조건 입력, API 호출, 결과 및 Tool 결과 표시 |
| 앱 구조 | `frontend/app.py` | 두 Agent 페이지만 등록하고 메뉴 추천을 기본 페이지로 설정 |
| 정리 작업 | `frontend/app_pages/01_home.py`~`17_agent_cycle.py` | 신규 화면 검증 후 기존 예제 페이지 제거 |

`frontend/clients/agent_client.py`는 `dy` 담당이다. 메뉴 화면에서는 그 파일이 제공하는 `run_menu_recommendation()`만 호출하며 수정하지 않는다.

## 2. 선행 조건 및 협업 방식

1. `dy`가 아래 함수를 포함한 `agent_client.py` 변경을 먼저 공유한다.

   ```python
   run_menu_recommendation(payload: dict[str, Any])
   ```

2. 백엔드 메뉴 추천 API 계약을 다음으로 확정한다.

   ```text
   POST /api/agents/menu-recommendation
   ```

3. 화면은 공통 응답의 선택 필드를 반드시 `.get()`으로 읽는다. 일부 값이 누락되어도 렌더링이 중단되지 않아야 한다.

4. `app.py`와 메뉴 추천 페이지는 yj만 수정한다. `agent_client.py`, 학습 도우미 페이지, `core/api_client.py`는 수정하지 않는다.

## 3. 메뉴 추천 화면 구현

### 3.1 임시 파일로 먼저 구현

기존 `01_home.py`와 파일명이 충돌하므로, 예제 제거 전에는 임시 파일명(예: `18_menu_recommendation.py`)으로 구현하고 동작을 확인한다. 예제 정리 단계에서 최종 파일명 `01_menu_recommendation.py`로 변경한다.

### 3.2 입력 UI

`st.form` 안에 다음 입력값을 둔다.

| 입력 항목 | 위젯 예시 | Happy Case 기본값 |
|---|---|---|
| 식사 시간 | `st.selectbox` | `저녁` |
| 인원 | `st.number_input` | `2` |
| 예산 | `st.number_input` | `30000` |
| 선호 음식 | `st.text_input` | `한식, 따뜻한 음식` |
| 제외 음식 | `st.text_input` | 빈 값 |
| 알레르기 | `st.text_input` | 빈 값 |
| 맵기 | `st.selectbox` | `보통` |

쉼표 입력값은 공백과 빈 항목을 제거해 `list[str]`로 변환한다.

```python
def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
```

제출 시 다음 payload를 만들어 `run_menu_recommendation(payload)`에 전달한다.

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

### 3.3 요청 상태와 오류 처리

- 폼 제출 후 `st.spinner("메뉴를 추천하는 중입니다...")`로 진행 상태를 표시한다.
- `BackendAPIError`는 잡아서 서버 실행 여부와 재시도 방법을 같은 화면에 안내한다.
- 예상하지 못한 응답 또는 빈 응답도 사용자용 안내를 표시하며 앱이 중단되지 않게 한다.
- 결과는 필요하면 `st.session_state`에 저장해 Streamlit 재실행 뒤에도 마지막 성공 결과를 유지한다.

### 3.4 결과 렌더링 순서

응답을 받은 뒤 다음 순서로 화면에 표시한다.

1. `summary`: 핵심 추천 요약
2. `recommendations`: 추천 메뉴별 이름, 추천 이유, 예상 가격, 영양·식단 참고 정보
3. 대체 메뉴: 추천 항목 또는 응답의 대체 메뉴 필드가 있으면 표시
4. `reasoning`: 추천 근거
5. `followUpQuestions`: 후속 질문 또는 재추천 안내
6. `toolResults`: `st.expander("Tool 실행 결과")` 안에서 `st.json()`으로 표시

백엔드 세부 응답 구조가 달라질 수 있으므로, 메뉴 항목은 dict/list/string 어느 형태여도 최소한 안전하게 보여 주고, 선택 필드는 `.get()`과 빈 값 확인을 사용한다. 표시할 결과가 없으면 “조건에 맞는 추천 결과가 없습니다. 예산 또는 선호 조건을 바꿔 다시 시도해 주세요.”를 안내한다.

## 4. 앱 진입 구조 정리

`frontend/app.py`는 아래 두 페이지만 등록한다.

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

pg = st.navigation([menu, learning])
pg.run()
```

- 앱 제목은 두 기능을 포괄하는 이름으로 변경한다.
- 기존 학습 과정명, 단계별 expander, 환경 상태 링크, 예제 페이지 링크는 제거한다.
- 기본 진입 페이지는 메뉴 추천 Agent로 설정한다.

## 5. 예제 페이지 제거 순서

예제 제거는 신규 기능 검증 뒤 별도 커밋으로 수행한다.

1. 임시 이름의 메뉴 추천 페이지가 API 호출과 화면 렌더링을 정상 수행하는지 확인한다.
2. `dy`의 학습 도우미 페이지와 신규 Client 함수가 반영된 최신 `main`을 기준으로 작업한다.
3. 기존 `frontend/app_pages/01_home.py`~`17_agent_cycle.py`를 제거한다.
4. 임시 메뉴 추천 페이지를 `01_menu_recommendation.py`로 이름 변경한다.
5. 학습 도우미 페이지가 `02_learning_assistant.py`에 있는지 확인한다.
6. `app.py`의 두 페이지 경로와 기본 페이지 설정을 확인한다.

## 6. 개발 및 검증 순서

1. 현재 `app.py`, `17_agent_cycle.py`, `04_travel_classifier.py`를 읽어 기존 Streamlit·오류 처리 스타일을 확인한다.
2. `dy`의 `run_menu_recommendation()` 함수가 포함된 변경을 반영한다.
3. 임시 메뉴 추천 페이지에 폼, Happy Case 기본값, CSV 변환, API 호출을 구현한다.
4. 성공 응답, 빈 응답, `BackendAPIError` 각각의 렌더링을 확인한다.
5. 백엔드를 실행한 뒤 기본값으로 한 번 요청해 추천 메뉴와 두 Tool 결과가 표시되는지 확인한다.
6. `app.py`를 두 Agent 전용 navigation으로 변경하고, `dy` 페이지와 함께 앱을 실행해 전환을 확인한다.
7. 예제 페이지 제거와 파일명 정리를 별도 커밋으로 수행한다.

## 7. 완료 기준

- 메뉴 추천 페이지에서 기본값 그대로 실행 버튼 한 번으로 요청할 수 있다.
- 입력값이 API 계약의 키와 타입으로 전달된다.
- 요약, 추천 메뉴, 이유, 가격, 대체 메뉴, 후속 질문, Tool 결과를 한 페이지에서 확인할 수 있다.
- 로딩, 서버 오류, timeout, 빈 결과를 사용자가 이해할 수 있는 메시지로 처리한다.
- 앱 사이드바에는 메뉴 추천 Agent와 학습 도우미 Agent만 표시된다.
- 앱 실행 시 메뉴 추천 Agent가 기본으로 열린다.
- 기존 예제 페이지는 기능 검증 후 별도 커밋에서 제거된다.
- yj 담당 변경에 대해 Python 문법 검사와 실제 Happy Case 수동 확인을 마친다.

## 8. 권장 커밋 단위

```text
feat(frontend): add menu recommendation page
refactor(frontend): register project agent pages only
refactor(frontend): remove legacy example pages
```

각 커밋 전에는 `git diff -- frontend`로 yj 소유 범위 밖의 변경이 없는지 확인한다.
