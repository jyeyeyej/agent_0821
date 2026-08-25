# 햄버거 주문 음성 키오스크 프론트엔드 구현 계획

## 1. 목표와 범위

현재 Streamlit 프론트엔드에 `햄버거 주문 음성 키오스크` 페이지를 추가한다. 고객은 한 화면에서 음성을 녹음하거나 텍스트를 입력하고, Agent 안내와 메뉴 추천을 확인하며, 장바구니를 수정한 뒤 결제 직전 상태까지 진행한다.

프론트엔드의 책임은 다음으로 제한한다.

- 음성 녹음 및 텍스트 대체 입력
- Backend 응답의 인식 문장, Agent 답변, 추천 메뉴, 장바구니 표시
- 주문 추가·수정·삭제·초기화 및 포장/매장 식사 선택
- 고객의 명시적인 확인을 받은 뒤 `ready_for_payment` 요청
- 로딩, 재입력, 확인 필요, 품절·알레르기 경고, 통신 오류 상태 표시

결제 승인, 카드 정보 입력, PG/POS 연동, 재고 변경은 구현하지 않는다. 가격·품절·옵션 유효성·최종 합계는 화면에서 계산하거나 추측하지 않고 Backend 응답만 표시한다.

```text
음성 또는 텍스트 입력
→ Backend STT/RAG/Agent 처리
→ 인식 문장과 안내 표시
→ Backend가 검증한 장바구니 갱신
→ 고객 주문 확인
→ ready_for_payment 화면
```

## 2. 현재 구조와 변경 파일

기존 `frontend/core/api_client.py`의 `request()`와 `BackendAPIError`를 재사용한다. 다만 기존 개인 LAN Backend 주소 `http://192.168.1.25:8000`은 더 이상 기본값으로 사용하지 않고, 모든 팀원이 각자 실행한 로컬 Backend에 연결하도록 기본 주소를 `http://127.0.0.1:8000`으로 변경한다. `request()`는 임의 HTTP method 문자열을 받을 수 있으므로 장바구니 변경 API의 `UPDATE` 메서드는 별도 HTTP 함수 추가 없이 호출할 수 있다.

```text
frontend/
├─ app.py                              # 수정: 음성 키오스크 페이지 등록
├─ app_pages/
│  └─ 05_voice_kiosk.py                # 신규: 음성 주문 화면과 상태 관리
├─ clients/
│  └─ kiosk_client.py                  # 신규: /api/kiosk API 전용 함수
└─ core/
   └─ api_client.py                    # 수정: 기본 Backend 주소를 127.0.0.1로 변경
```

기존 메뉴 추천, 학습 도우미, 주차 Workflow, 주차 Agent 페이지는 제거하지 않는다. 음성 키오스크는 다섯 번째 페이지로 추가한다.

## 3. 역할 분담

| 담당자 | 소유 파일 | 주요 책임 |
|---|---|---|
| `dy` | `frontend/clients/kiosk_client.py` | 5개 키오스크 API 함수, 요청 payload 구성, 응답 형식 검증, Client 단위 확인 |
| `dy` | `frontend/core/api_client.py` | 기본 Backend URL을 로컬 `127.0.0.1:8000`으로 변경하고 환경변수 우선순위 유지 |
| `jy` | `frontend/app_pages/05_voice_kiosk.py` | 녹음·텍스트 입력, 세션 상태, Agent 답변·추천·장바구니 UI, 주문 확인 화면 |
| `jy` | `frontend/app.py` | `음성 주문 키오스크` 페이지 등록과 내비게이션 최종 통합 |

공통 파일을 동시에 수정하지 않는다. `dy`는 페이지와 `app.py`를 수정하지 않고, `jy`는 `kiosk_client.py`와 `core/api_client.py`를 수정하지 않는다. `core/api_client.py`는 `dy`가 로컬 주소 변경만 수행하며 다른 공통 HTTP 동작은 정리하거나 변경하지 않는다. Backend 파일은 두 사람 모두 수정하지 않으며 API 계약 변경이 필요하면 구현 전에 Backend 담당자와 합의한다.

### 작업량 균형

- `dy`는 단순 함수 추가에 그치지 않고 모든 성공 응답이 JSON 객체인지 검증하고, 잘못된 응답을 `BackendAPIError`로 통일하며, camelCase 요청 필드와 함수별 필수 인자를 점검한다.
- `jy`는 Streamlit 재실행 특성을 고려해 녹음, 전송 중, 확인 대기, 장바구니, 결제 대기 상태를 `st.session_state`로 관리한다.
- API 연결 전에는 `dy`가 함수 인터페이스와 예시 응답을 먼저 공유하고, `jy`는 그 인터페이스만 사용해 병렬 구현한다.

## 4. 선행 확정 사항

두 사람이 구현을 시작하기 전에 아래 항목을 Backend 담당자와 고정한다.

- 모든 JSON 요청·응답 필드는 camelCase를 사용한다.
- 공통 접두사는 `/api/kiosk`다.
- 브라우저 녹음 MIME은 우선 `audio/wav` 또는 Streamlit 위젯이 반환한 실제 MIME을 그대로 전송한다.
- `audioBase64`에는 data URL 접두사를 붙이지 않은 순수 Base64 문자열을 전송한다.
- 세션이 없을 때 프론트엔드가 UUID를 생성하고 이후 모든 요청에서 같은 `sessionId`를 사용한다.
- `UPDATE`가 Backend 프레임워크 또는 프록시에서 허용되지 않으면 양쪽 합의 후 `PATCH`로 바꾸며, 변경은 `kiosk_client.py` 한 곳에만 반영한다.
- `ready_for_payment` 이후 화면은 읽기 전용으로 전환한다.

### 4.1 로컬 Backend 실행 및 연결 기준

이번 시스템부터 특정 팀원의 IP 주소로 실행한 공용 Backend를 사용하지 않는다. 각 팀원은 자신의 PC에서 Backend를 실행하고 같은 PC의 Streamlit 프론트엔드를 연결한다.

기본 연결 주소는 다음과 같이 변경한다.

```python
BACKEND_URL = os.getenv(
    "BACKEND_API_URL",
    "http://127.0.0.1:8000",
).rstrip("/")
```

- 기본값은 `http://127.0.0.1:8000`이다.
- `BACKEND_API_URL` 환경변수가 설정되어 있으면 환경변수 값을 우선한다.
- 개인 LAN IP인 `http://192.168.1.25:8000`을 코드, 문서, 예시 환경파일의 기본값으로 남기지 않는다.
- 프론트엔드와 Backend를 모두 호스트 PC에서 실행할 때만 `127.0.0.1`을 사용한다.
- 프론트엔드를 Docker 컨테이너 안에서 실행하면 컨테이너의 `127.0.0.1`은 호스트 Backend가 아니다. 이 경우 `BACKEND_API_URL=http://host.docker.internal:8000` 또는 같은 Docker Compose 네트워크의 Backend 서비스명을 사용한다.
- 팀원별 환경 차이는 코드의 IP를 다시 고치는 방식이 아니라 `BACKEND_API_URL` 환경변수로 처리한다.

호스트 PC에서 Backend를 실행하는 기본 예시는 다음과 같다.

```powershell
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

프론트엔드 실행 전에 브라우저 또는 명령행에서 `http://127.0.0.1:8000/docs`에 접근되는지 확인한다.

## 5. `dy` 작업 명세 — API Client

### 5.1 공개 함수

`frontend/clients/kiosk_client.py`에 아래 함수만 공개한다.

```python
def submitVoiceTurn(session_id, audio_bytes, mime_type, order_type): ...
def submitTextTurn(session_id, text, order_type): ...
def getOrderCart(session_id): ...
def updateOrderCart(session_id, payload): ...
def readyForPayment(session_id): ...
```

프로젝트의 기존 Python 스타일에 맞추기 위해 실제 구현 함수명은 snake_case로 정할 수도 있지만, Backend 계약서의 Frontend 함수명과 다르게 정할 경우 `jy`와 먼저 합의하고 문서·import를 함께 고정한다. 권장 구현은 Python 표준에 맞춘 아래 이름이다.

```python
submit_voice_turn
submit_text_turn
get_order_cart
update_order_cart
ready_for_payment
```

### 5.2 API 매핑

| 함수 | Method / Path | 핵심 요청 |
|---|---|---|
| `submit_voice_turn` | `POST /api/kiosk/voice-turn` | `sessionId`, Base64 변환한 `audioBase64`, `mimeType`, `orderType` |
| `submit_text_turn` | `POST /api/kiosk/text-turn` | `sessionId`, 공백 제거 후 검증한 `text`, `orderType` |
| `get_order_cart` | `GET /api/kiosk/sessions/{sessionId}/cart` | path parameter |
| `update_order_cart` | `UPDATE /api/kiosk/sessions/{sessionId}/cart` | `operation`, `menuId`, `quantity`, `orderType`, `selection` 등 |
| `ready_for_payment` | `POST /api/kiosk/sessions/{sessionId}/ready-for-payment` | 빈 JSON 객체 또는 Backend가 확정한 body |

### 5.3 Client 규칙

- 오디오 bytes의 Base64 인코딩은 Client에서 한 번만 수행한다.
- 빈 오디오, 빈 텍스트, 빈 `sessionId`, 지원하지 않는 `orderType`은 요청 전에 거부한다.
- `orderType`은 `dine_in | takeout`만 허용한다.
- API 결과가 `dict`가 아니면 `BackendAPIError`를 발생시킨다.
- Backend의 오류 메시지는 `core.api_client.request()`가 처리하도록 중복 HTTP 코드를 작성하지 않는다.
- URL path의 `sessionId`는 안전하게 인코딩하거나 UUID 형식을 검증한다.
- 페이지가 Backend 응답 키를 재작성하지 않도록 원본 JSON 객체를 반환한다.
- 가격, 할인, 합계를 Client에서 계산하지 않는다.

### 5.4 `dy` 완료 기준

- 5개 함수의 method, path, camelCase payload가 설계서와 일치한다.
- 한글 텍스트 및 바이너리 음성이 손실 없이 요청 payload로 변환된다.
- 빈 입력과 비정상 JSON 응답이 사용자에게 표시 가능한 `BackendAPIError`로 통일된다.
- `jy`가 Backend URL이나 HTTP 세부 구현을 알지 않고 공개 함수만 호출할 수 있다.
- `core/api_client.py`의 기본 주소가 `http://127.0.0.1:8000`이며 `BACKEND_API_URL` 환경변수 우선 동작은 유지된다.
- 기존 개인 LAN IP가 프론트엔드 코드에 남아 있지 않다.

## 6. `jy` 작업 명세 — Streamlit 페이지

### 6.1 화면 구성

`frontend/app_pages/05_voice_kiosk.py`는 `layout="wide"` 환경에서 다음 영역을 한 화면에 배치한다.

```text
┌─────────────────────────────────────────────────────────┐
│ 음성 주문 안내 / 매장 식사·포장 선택                   │
├─────────────────────────────┬───────────────────────────┤
│ 대화 영역                   │ 장바구니                  │
│ - Agent 안내                │ - 메뉴/옵션/수량/금액     │
│ - 인식된 고객 발화          │ - 수정/삭제/초기화        │
│ - 추천 메뉴와 확인 질문     │ - Backend 최종 합계       │
├─────────────────────────────┴───────────────────────────┤
│ 음성 녹음 / 텍스트 대체 입력 / 전송 버튼               │
└─────────────────────────────────────────────────────────┘
```

- 제목: `🎙️ 햄버거 음성 주문 키오스크`
- 주문 시작 전에 `매장에서 먹기(dine_in)` 또는 `포장(takeout)`을 선택한다.
- `st.audio_input`을 우선 사용하고, 실행 중인 Streamlit 버전에서 지원하지 않으면 파일 업로드 또는 텍스트 입력을 개발 대체 수단으로 사용한다.
- 텍스트 입력은 접근성 지원과 STT 실패 테스트를 위해 항상 제공한다.
- 음성과 텍스트가 동시에 입력되면 자동 전송하지 않고 사용자가 전송 방식을 명시적으로 선택하게 한다.
- 처리 중에는 spinner를 표시하고 전송·수정·주문 완료 버튼을 비활성화한다.

### 6.2 세션 상태

최소한 아래 값을 `st.session_state`에 둔다. 키에는 `kiosk_` 접두사를 붙여 다른 페이지 상태와 충돌하지 않게 한다.

| 상태 | 용도 |
|---|---|
| `kiosk_session_id` | 최초 진입 시 생성한 UUID, 새 주문 전까지 유지 |
| `kiosk_order_type` | `dine_in` 또는 `takeout` |
| `kiosk_messages` | 고객 발화와 Agent 답변 표시 이력 |
| `kiosk_cart` | 가장 최근 Backend 장바구니 스냅샷 |
| `kiosk_suggestions` | 최근 추천 카드 목록 |
| `kiosk_requires_confirmation` | 모호한 주문 또는 Agent 확인 질문 상태 |
| `kiosk_processing` | 중복 요청 방지 |
| `kiosk_status` | `active` 또는 `ready_for_payment` |

페이지 최초 진입이나 새로고침 시 `get_order_cart()`로 서버 상태를 다시 조회한다. 세션 상태는 화면 캐시일 뿐이며 Backend 장바구니와 충돌하면 Backend 응답으로 덮어쓴다.

### 6.3 응답 표시 규칙

- `transcript`는 `내가 말한 내용`으로 표시해 오인식 여부를 즉시 확인하게 한다.
- `assistantMessage`는 화면 답변으로 표시하고, `speakText`는 후속 TTS가 붙을 수 있도록 별도 값으로 보존한다. 이 단계에서 브라우저 자동 재생이나 별도 TTS API는 만들지 않는다.
- `requiresConfirmation=true`이면 장바구니 변경 성공처럼 표현하지 않고 확인 질문을 강조한다.
- `suggestions`는 이름, 추천 근거, 현재 가격, 판매 가능 여부가 있을 때 카드로 표시한다.
- `retrievals`와 `trace`는 기본 화면을 복잡하게 하지 않도록 개발자용 expander 안에 표시한다.
- 선택 필드는 `.get()`과 안전한 기본값으로 읽어 일부 필드 누락 때문에 전체 페이지가 중단되지 않게 한다.

### 6.4 장바구니 규칙

- 품목명, 단품/세트, 선택 옵션, 수량, 단가, 옵션 금액, 항목 합계를 표시한다.
- 수량 변경과 삭제는 `update_order_cart()`를 호출한 뒤 반환된 전체 cart로 즉시 교체한다.
- `clear`는 장바구니가 비어 있지 않을 때만 확인 UI를 거쳐 호출한다.
- 주문 유형 변경은 활성 주문에서만 허용하고 Backend 결과가 성공한 뒤 화면 값을 변경한다.
- 알레르기 및 옵션 경고는 `warnings` 내용을 생략하거나 완화하지 않고 눈에 띄게 표시한다.
- subtotal, discount, total은 Backend가 반환한 값을 원 단위로 포맷만 한다.
- `ready_for_payment` 상태에서는 입력과 장바구니 변경 버튼을 모두 잠그고 `결제 대기 중` 안내와 `새 주문 시작`만 제공한다.
- `새 주문 시작`은 기존 세션을 임의로 되살리지 않고 새 UUID와 빈 로컬 상태를 만든다.

### 6.5 오류 및 안전 UX

- 낮은 STT 신뢰도 또는 `requiresConfirmation=true`에서는 재발화/텍스트 입력 안내를 보여 주고 변경 성공 메시지를 표시하지 않는다.
- 품절 메뉴와 불가능한 옵션은 Backend 경고를 표시하고 대체 추천이 있으면 함께 보여 준다.
- 알레르기 관련 답변에는 `성분표와 매장 직원에게 다시 확인해 주세요` 안내를 유지한다.
- 마이크 권한 거부 시 브라우저 설정 안내와 텍스트 입력을 제공한다.
- `BackendAPIError` 발생 시 기존 장바구니를 지우지 않고 재시도 안내를 표시한다.
- 예기치 않은 예외의 내부 stack trace, API 키, 요청 원문을 고객 화면에 노출하지 않는다.
- 카드 번호나 결제 정보를 말하거나 입력하도록 요구하지 않는다.

### 6.6 `app.py` 등록

`jy`가 페이지 구현 완료 후 아래 페이지를 기존 navigation 끝에 추가한다.

```python
voice_kiosk = st.Page(
    "app_pages/05_voice_kiosk.py",
    title="음성 주문 키오스크",
    icon="🎙️",
)
```

기존 기본 페이지와 다른 네 페이지의 순서·경로는 변경하지 않는다. 키오스크를 기본 페이지로 바꾸지 않는다.

### 6.7 `jy` 완료 기준

- 음성 또는 텍스트 한 가지 방식으로 주문 턴을 전송할 수 있다.
- 인식 문장, Agent 답변, 추천, 확인 질문, 경고, 장바구니가 한 화면에 표시된다.
- Streamlit rerun 후에도 같은 세션과 최신 장바구니가 유지된다.
- 중복 클릭으로 같은 주문이 두 번 추가되지 않는다.
- 결제 전 확정 이후 모든 변경 입력이 잠긴다.

## 7. 공통 응답 계약

페이지는 다음 응답을 기준으로 구현한다.

```json
{
  "sessionId": "uuid",
  "transcript": "불고기 버거 세트 하나 주세요",
  "assistantMessage": "불고기 버거 세트 1개를 담을까요?",
  "speakText": "불고기 버거 세트 1개를 담을까요?",
  "cart": {
    "status": "active",
    "items": [],
    "subtotal": 0,
    "discount": 0,
    "total": 0,
    "warnings": [],
    "nextAction": "confirm_order"
  },
  "retrievals": [],
  "suggestions": [],
  "requiresConfirmation": true,
  "trace": []
}
```

Backend가 Pydantic alias를 적용하지 않아 snake_case를 반환하는 문제를 프론트엔드가 조용히 흡수하지 않는다. 개발 중에는 계약 불일치로 보고 Backend에서 camelCase로 수정한다.

## 8. 구현 및 병합 순서

```text
main
├─ feature/kiosk-client-dy
└─ feature/kiosk-page-jy
```

1. Backend 담당자와 method, path, request/response 예시를 확정한다.
2. `dy`가 `core/api_client.py`의 기본 Backend 주소를 `127.0.0.1:8000`으로 변경하고 `kiosk_client.py`의 공개 함수 시그니처와 상수를 먼저 커밋해 공유한다.
3. `jy`가 해당 시그니처를 기준으로 `05_voice_kiosk.py`를 병렬 구현한다.
4. `dy`가 Base64, 입력 검증, 응답 검증과 API 연결 확인을 마친 뒤 먼저 병합한다.
5. `jy`가 최신 기본 브랜치를 반영하고 실제 Client로 Happy Case를 확인한다.
6. `jy`가 `app.py` 등록을 마지막 커밋으로 분리해 병합한다.
7. 두 사람이 함께 Mock STT/LLM 및 실제 브라우저 마이크 흐름을 확인한다.

권장 커밋:

```text
feat(frontend): add kiosk API client
chore(frontend): use local backend URL by default
feat(frontend): add voice kiosk page
feat(frontend): handle kiosk cart and confirmation states
feat(frontend): register voice kiosk navigation
```

## 9. 충돌 방지 규칙

- 상대방 소유 파일을 수정하거나 자동 포맷하지 않는다.
- `frontend/core/api_client.py`는 `dy`만 수정하고 기본 Backend URL 외의 공통 동작은 변경하지 않는다.
- 전체 `frontend/` 대상 자동 포맷은 실행하지 않는다.
- API 계약 변경은 채팅 합의만으로 끝내지 않고 이 문서와 Backend 스키마에 함께 반영한다.
- `app.py` 수정은 페이지 동작 확인 후 `jy`가 단독 수행한다.
- `git diff main...HEAD -- frontend`로 담당 외 변경이 없는지 병합 전에 확인한다.
- 기능 구현과 기존 코드 정리는 같은 커밋에 넣지 않는다.

## 10. 통합 검증 시나리오

### Happy Case

1. 포장을 선택한다.
2. `불고기 버거 세트 하나 주세요`를 음성 또는 Mock STT로 입력한다.
3. 인식 문장과 확인 질문이 표시되는지 본다.
4. 세트, 치즈 추가, 제로 콜라를 확정한다.
5. Backend가 계산한 품목과 총액이 표시되는지 본다.
6. 수량을 변경했다가 다시 조회해 서버 상태와 일치하는지 본다.
7. `주문 완료` 버튼을 누르고 명시적인 확인을 거친다.
8. `ready_for_payment`가 표시되고 이후 수정이 차단되는지 본다.

### 예외 Case

- 빈 오디오와 빈 텍스트는 요청되지 않는다.
- 낮은 STT 신뢰도에서는 장바구니가 바뀌지 않는다.
- 품절 메뉴 주문 시 경고와 대체 후보가 표시된다.
- 불가능한 옵션은 이전 장바구니를 유지한 채 오류가 표시된다.
- 모호한 `치즈 빼줘` 요청은 대상 확인 질문으로 끝난다.
- Backend timeout 후 재시도해도 같은 주문이 중복 추가되지 않는다.
- 빈 장바구니에서는 주문 완료가 비활성화된다.
- `ready_for_payment` 이후 update 요청을 보내지 않는다.
- 페이지 재실행 후 `get_order_cart()` 결과로 상태가 복원된다.
- API 키가 없어도 텍스트 입력과 Mock STT Happy Case가 동작한다.

## 11. 최종 체크리스트

### `dy`

- [ ] 키오스크 API 함수 5개가 구현되어 있다.
- [ ] 음성 bytes가 순수 Base64 문자열로 변환된다.
- [ ] method, path, camelCase payload가 Backend 계약과 일치한다.
- [ ] 입력 오류와 잘못된 응답이 `BackendAPIError`로 처리된다.
- [ ] 가격·재고·옵션을 Client가 임의 계산하지 않는다.
- [ ] `core/api_client.py`의 기본 Backend 주소가 `http://127.0.0.1:8000`이다.
- [ ] `BACKEND_API_URL` 환경변수를 설정하면 해당 주소가 기본값보다 우선한다.
- [ ] 기존 개인 LAN IP가 프론트엔드 코드에서 제거되어 있다.

### `jy`

- [ ] `05_voice_kiosk.py`에서 음성과 텍스트 입력을 모두 제공한다.
- [ ] 인식 문장, Agent 답변, 추천, 장바구니, 경고를 표시한다.
- [ ] 처리 중 중복 요청을 막고 오류 후 기존 cart를 보존한다.
- [ ] 주문 완료 전에 고객의 명시적 확인을 받는다.
- [ ] `ready_for_payment` 이후 화면을 읽기 전용으로 전환한다.
- [ ] `app.py`에 기존 페이지를 유지한 채 키오스크를 등록한다.

### 공동

- [ ] 음성 → STT/RAG/Agent → 장바구니 → 결제 대기 흐름이 동작한다.
- [ ] 텍스트 대체 입력과 Mock Provider로도 Happy Case가 동작한다.
- [ ] 품절, 알레르기, 모호한 요청, 낮은 신뢰도 시 잘못된 주문 변경이 없다.
- [ ] 화면의 가격과 합계가 Backend Tool 결과와 일치한다.
- [ ] 결제, POS, 카드 정보 입력 기능이 포함되지 않는다.
- [ ] 두 사람의 브랜치가 같은 파일을 수정하지 않는다.
- [ ] 각 팀원의 로컬 Backend와 프론트엔드가 `127.0.0.1:8000`을 통해 연결된다.
- [ ] Docker 실행 시 `BACKEND_API_URL`로 호스트 또는 Backend 서비스 주소를 지정한다.

## 12. 프론트엔드 완료 기준

- 기존 프로젝트 구조를 유지하면서 다섯 번째 Streamlit 페이지로 음성 키오스크가 제공된다.
- 고객이 음성 또는 텍스트로 메뉴를 탐색하고, 추천과 확인 질문을 거쳐 장바구니를 완성할 수 있다.
- 모든 주문 변경과 금액은 Backend 응답을 단일 기준으로 사용한다.
- 오류나 불명확한 음성 입력이 장바구니 변경으로 이어지지 않는다.
- 주문 확정은 결제를 실행하지 않고 `ready_for_payment` 상태 전환까지만 수행한다.
- `dy`와 `jy`의 파일 소유권, 선행 의존성, 병합 순서가 명확해 병렬 작업 시 충돌이 없다.
- 기본 Backend 주소는 특정 팀원의 IP가 아닌 `127.0.0.1:8000`이며, 다른 실행 환경은 `BACKEND_API_URL`로 주입한다.
