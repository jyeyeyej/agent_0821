# DY Frontend 작업 명세

## 1. 담당 목표

`dy`는 학습 도우미 Agent 화면과 프론트엔드 API Client를 담당한다.

최종 담당 파일은 다음 두 개다.

```text
frontend/
├─ app_pages/
│  └─ 02_learning_assistant.py
└─ clients/
   └─ agent_client.py
```

작업 목표:

1. 기본값만으로 바로 실행 가능한 학습 도우미 화면 구현
2. 메뉴 추천과 학습 도우미 API 호출 함수 제공
3. 자신의 기능 구현이 끝나면 기존 예제용 Client 함수를 브랜치에서 정리
4. `yj`의 파일과 겹치지 않는 커밋 구성

## 2. 작업하지 않는 파일

다음 파일은 `yj` 담당이므로 수정하지 않는다.

```text
frontend/app.py
frontend/app_pages/01_menu_recommendation.py
```

다음 파일은 기존 기능을 그대로 사용하므로 수정하지 않는다.

```text
frontend/core/api_client.py
```

기존 `frontend/app_pages/01_home.py`~`17_agent_cycle.py` 제거도 `yj`가 담당한다. 전체 `frontend/`에 자동 포맷터를 실행하지 않는다.

## 3. 작업 전 확인 사항

백엔드 담당자와 아래 내용을 먼저 확정한다.

- 학습 도우미 API 경로
- 메뉴 추천 API 경로
- 요청 필드의 camelCase 사용 여부
- 공통 응답 필드
- `recommendations`와 `toolResults` 내부 객체 구조
- 오류 응답 형식

현재 프론트엔드 기준 계약은 다음과 같다.

```text
POST /api/agents/menu-recommendation
POST /api/agents/learning-assistant
```

백엔드 경로가 달라지면 페이지가 아니라 `frontend/clients/agent_client.py`에서만 수정한다.

## 4. 1차 작업: Agent API 함수 추가

### 대상 파일

```text
frontend/clients/agent_client.py
```

기존 예제 함수는 이 단계에서 제거하지 않는다. 다음 함수 두 개만 추가한다.

```python
def run_menu_recommendation(payload: dict[str, Any]):
    return request("POST", "/api/agents/menu-recommendation", json=payload)


def run_learning_assistant(payload: dict[str, Any]):
    return request("POST", "/api/agents/learning-assistant", json=payload)
```

구현 규칙:

- 기존 `request()`를 그대로 사용한다.
- 페이지가 전달한 payload를 Client에서 임의로 변경하지 않는다.
- timeout이나 연결 오류를 따로 다시 처리하지 않는다. 기존 `api_client.py`의 `BackendAPIError`를 사용한다.
- 기존 함수의 이름과 동작은 이 단계에서 변경하지 않는다.
- 두 함수가 추가된 커밋을 먼저 만들고 `yj`에게 커밋 해시와 함수 이름을 공유한다.

권장 커밋:

```text
feat(frontend): add menu and learning agent API clients
```

## 5. 2차 작업: 학습 도우미 화면 구현

### 대상 파일

```text
frontend/app_pages/02_learning_assistant.py
```

기존 `02_environment.py`와 파일명이 다르므로 함께 존재할 수 있다. 기존 예제는 `yj`가 최종 정리한다.

### Import

```python
import streamlit as st

from clients.agent_client import run_learning_assistant
from core.api_client import BackendAPIError
```

### Happy Case 기본값

```json
{
  "subject": "Python",
  "goal": "반복문 기초 이해",
  "level": "초급",
  "studyMinutes": 30,
  "learningStyle": "예제와 문제 풀이"
}
```

사용자가 값을 바꾸지 않고 실행 버튼만 눌러도 결과를 확인할 수 있어야 한다.

### 입력 UI

하나의 `st.form` 안에 다음 입력을 배치한다.

| 입력 | 권장 Streamlit 요소 | 기본값/규칙 |
|---|---|---|
| 과목 | `st.text_input` | `Python`, 빈 문자열 금지 |
| 학습 목표 | `st.text_area` | `반복문 기초 이해`, 빈 문자열 금지 |
| 현재 수준 | `st.selectbox` | `초급`, 선택지: 초급·중급·고급 |
| 학습 시간 | `st.number_input` | 30분, 최소 10분, 10분 단위 |
| 학습 방식 | `st.selectbox` | `예제와 문제 풀이` |

학습 방식 선택지는 최소한 다음 항목을 제공한다.

- 예제와 문제 풀이
- 개념 설명 중심
- 단계별 실습

폼 제출 버튼 문구는 `학습 계획 만들기`로 한다. 폼 제출 전에는 API를 호출하지 않는다.

### 요청 payload

```python
payload = {
    "subject": subject.strip(),
    "goal": goal.strip(),
    "level": level,
    "studyMinutes": int(study_minutes),
    "learningStyle": learning_style,
}
```

과목 또는 목표가 비어 있으면 API를 호출하지 않고 `st.warning`으로 안내한다.

### 로딩과 오류

요청 중에는 다음과 같이 로딩 상태를 표시한다.

```python
with st.spinner("맞춤 학습 계획을 만들고 있습니다..."):
    result = run_learning_assistant(payload)
```

`BackendAPIError`는 페이지에서 처리한다.

```python
except BackendAPIError as error:
    st.error(str(error))
    st.info("백엔드 서버 실행 상태를 확인한 뒤 다시 시도해 주세요.")
```

내부 stack trace나 원본 예외는 사용자에게 표시하지 않는다.

## 6. 결과 렌더링 순서

백엔드의 최종 상세 응답 구조가 확정되면 키 이름을 맞추되, 공통 필드는 `.get()`으로 안전하게 읽는다.

### 6.1 핵심 요약

- `summary`가 있으면 `st.success` 또는 읽기 쉬운 본문으로 표시
- 값이 없으면 `응답 요약이 없습니다.` 안내

### 6.2 학습 계획과 추천 결과

- `recommendations`를 학습 순서대로 반복 표시
- 항목별 제목, 소요 시간, 핵심 내용이 있으면 구분해 표시
- 상세 객체의 일부 키가 없어도 전체 페이지가 중단되지 않게 처리

백엔드 응답이 확정되기 전에는 `recommendations` 전체를 특정 구조로 단정하지 않는다. dict이면 필드별로 표시하고, 문자열이면 그대로 표시하는 방식을 사용한다.

### 6.3 추천 이유와 다음 학습

- `reasoning`을 목록으로 표시
- `followUpQuestions`가 있으면 후속 학습 또는 확인 질문으로 표시
- 빈 배열이면 해당 섹션을 생략하거나 간단한 안내만 표시

### 6.4 Tool 결과

Tool 결과는 최종 답변보다 먼저 강조하지 않는다. 페이지 하단의 접을 수 있는 영역에 표시한다.

```python
with st.expander("Agent Tool 실행 결과", expanded=False):
    st.json(result.get("toolResults", []))
```

Happy Case에서 다음 두 Tool의 실행 결과를 확인할 수 있어야 한다.

1. 학습 계획 생성 Tool
2. 퀴즈 생성·채점 Tool

### 6.5 빈 응답

`summary`, `recommendations`, `toolResults`가 모두 비어 있으면 성공 화면처럼 보이지 않도록 다음과 같이 안내한다.

```text
표시할 학습 결과가 없습니다. 입력을 확인하고 다시 시도해 주세요.
```

## 7. 3차 작업: 화면 검증

### 정적 확인

- Python 문법 오류가 없어야 한다.
- `run_learning_assistant` import가 성공해야 한다.
- 사용하지 않는 import가 없어야 한다.
- 제거 예정인 예제 함수에 의존하지 않아야 한다.

예시 명령:

```powershell
python -m py_compile frontend\app_pages\02_learning_assistant.py
python -m py_compile frontend\clients\agent_client.py
```

### 동작 확인

- 기본값으로 버튼을 한 번 눌러 요청되는지 확인
- 요약, 학습 계획, 개념/예제, 문제/해설이 표시되는지 확인
- Tool 결과 두 개가 표시되는지 확인
- 백엔드가 꺼진 상태에서 연결 오류 안내 확인
- 잘못된 요청에 대한 4xx 오류 안내 확인
- 빈 배열이나 선택 필드 누락 응답에서 화면이 깨지지 않는지 확인

`app.py` 등록은 `yj` 담당이다. `yj`가 페이지를 등록한 뒤 사이드바 진입과 전체 실행을 함께 확인한다.

권장 커밋:

```text
feat(frontend): add learning assistant page
```

## 8. 4차 작업: 기존 Client 함수 정리

`yj`도 최종 브랜치에서 기존 01~17 페이지를 제거하고 신규 두 페이지만 남기는 것이 확정되어 있으므로, `dy`는 학습 페이지 구현과 검증을 마친 뒤 자신의 브랜치에서 기존 Client 함수를 바로 제거한다. `yj`의 `app.py` 전환 커밋을 기다리지 않는다.

정리 후 `dy` 브랜치만 단독 실행하면 아직 남아 있는 기존 예제 페이지가 제거된 Client 함수를 import해 오류가 날 수 있다. 이는 두 브랜치가 합쳐지기 전의 일시적인 상태다. `dy`는 신규 학습 페이지와 Client의 문법·호출을 검증하고, 최종 통합 실행은 `yj`의 예제 페이지 제거 변경까지 머지된 상태에서 확인한다.

### 제거 대상

`agent_client.py`에서 다음 예제 기능의 함수와 불필요한 import를 제거한다.

- health와 Provider 실습
- 개념 비교와 여행 분류
- 일반 LLM 호출과 Provider 비교
- Prompt 미리보기
- Pydantic/Structured Output 실습
- Tool 목록, 선택, 실행, Agent Cycle
- 이미지 분석과 TTS
- 더 이상 사용하지 않는 `request_bytes`, `upload`

### 최종 형태

```python
from typing import Any

from core.api_client import request


def run_menu_recommendation(payload: dict[str, Any]):
    return request("POST", "/api/agents/menu-recommendation", json=payload)


def run_learning_assistant(payload: dict[str, Any]):
    return request("POST", "/api/agents/learning-assistant", json=payload)
```

정리 후 저장소 전체에서 제거한 함수 이름을 검색해 남은 참조가 없는지 확인한다.

권장 커밋:

```text
refactor(frontend): remove legacy example API clients
```

## 9. `yj`에게 전달할 내용

1차 Client 커밋 후 다음 정보를 공유한다.

```text
- 커밋 해시
- run_menu_recommendation 함수 이름
- run_learning_assistant 함수 이름
- 확정된 API 경로
- 요청 payload 예시
- 확인된 응답 예시
```

학습 페이지 완료 후에는 다음을 공유한다.

```text
- 최종 파일 경로: frontend/app_pages/02_learning_assistant.py
- app.py에 등록할 페이지 제목: 학습 도우미 Agent
- Happy Case 실행 여부
- 백엔드 미구현 또는 응답 키 불일치 등 남은 이슈
```

## 10. 브랜치와 커밋 계획

권장 브랜치:

```text
feature/frontend-dy-learning
```

커밋은 다음 세 단위로 분리한다.

```text
1. feat(frontend): add menu and learning agent API clients
2. feat(frontend): add learning assistant page
3. refactor(frontend): remove legacy example API clients
```

세 번째 정리 커밋은 학습 페이지 구현과 검증이 끝난 직후 자신의 브랜치에서 만든다. `yj`의 작업 완료를 기다릴 필요는 없다.

머지 전 확인:

```powershell
git diff main...HEAD -- frontend
```

다음 파일 외에 의도하지 않은 변경이 없어야 한다.

```text
frontend/app_pages/02_learning_assistant.py
frontend/clients/agent_client.py
```

## 11. 완료 체크리스트

### API Client

- [ ] `run_menu_recommendation`이 메뉴 추천 endpoint를 호출한다.
- [ ] `run_learning_assistant`가 학습 도우미 endpoint를 호출한다.
- [ ] payload를 Client에서 임의로 변경하지 않는다.
- [ ] 함수 이름과 경로를 `yj`에게 공유했다.

### 학습 화면

- [ ] 과목, 목표, 수준, 시간, 학습 방식 입력이 있다.
- [ ] Happy Case 기본값이 채워져 있다.
- [ ] 폼 제출 전에는 API를 호출하지 않는다.
- [ ] 빈 과목과 목표를 프론트에서 차단한다.
- [ ] 요청 중 spinner가 표시된다.
- [ ] 요약과 학습 계획이 표시된다.
- [ ] 개념, 예제, 문제와 해설을 확인할 수 있다.
- [ ] 후속 질문과 Tool 결과가 표시된다.
- [ ] 빈 응답을 안전하게 처리한다.
- [ ] `BackendAPIError`를 사용자용 문구로 안내한다.

### 정리 및 통합

- [ ] 학습 페이지 구현 후 기존 예제 Client 함수를 자신의 브랜치에서 제거했다.
- [ ] 제거된 함수에 대한 남은 참조가 없다.
- [ ] 두 담당 파일 모두 문법 검사를 통과한다.
- [ ] `yj` 담당 파일을 수정하지 않았다.
- [ ] 메뉴 추천 페이지에서도 Client 함수가 정상 import된다.
- [ ] 외부 API 키와 DB 없이 Mock Provider로 Happy Case가 동작한다.

## 12. 완료 기준

다음 조건을 모두 만족하면 `dy` 작업이 완료된다.

- 학습 도우미 페이지가 기본값 한 번의 제출로 정상 결과를 표시한다.
- 학습 계획과 퀴즈 Tool 결과를 한 화면에서 확인할 수 있다.
- 로딩, 빈 응답, 연결 오류, API 오류가 화면에서 안전하게 처리된다.
- 메뉴 추천과 학습 도우미가 공통 Client를 통해 각각 올바른 endpoint를 호출한다.
- 최종 `agent_client.py`에는 신규 Agent용 함수만 남는다.
- `yj` 담당 파일과 충돌하지 않는 독립 커밋으로 머지할 수 있다.
