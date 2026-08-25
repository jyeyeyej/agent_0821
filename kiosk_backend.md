# 햄버거 주문 음성 키오스크 백엔드 설계서

## 1. 목적과 범위

본 문서는 [kiosk_master.md](kiosk_master.md)를 구현하기 위한 백엔드 분업 기준이다. 고객은 음성 또는 텍스트로 메뉴를 탐색하고 장바구니를 완성한다. 범위는 결제 직전의 `ready_for_payment`까지이며, 결제 승인·POS 전송·재고 차감·개인정보 처리는 제외한다.

- Agent가 쓰는 Tool은 정확히 3개다: `transcribe_and_retrieve`, `search_menu_catalog`, `update_order_cart`.
- 가격, 품절, 옵션 호환성, 장바구니 합계는 Tool 데이터가 최종 기준이다.
- 기존 FastAPI, Pydantic, Provider, Tool Registry, 안전 실행기를 재사용한다.
- RAG·카탈로그·세션·장바구니는 Docker PostgreSQL + pgvector에 저장한다. Python 메모리 저장소는 사용하지 않는다.
- RAG 임베딩과 검색 방식은 `06_pgvector_ollama_example.py`와 동일하게 Ollama `embeddinggemma`, `psycopg`, `pgvector.psycopg.register_vector`, 코사인 거리 연산자 `<=>`를 사용한다.

## 2. A/B 충돌 방지 원칙

각 담당자는 자신에게 배정된 파일만 수정한다. 공유 파일은 B가 모든 기능이 준비된 뒤 한 번만 통합한다. 상대 파일의 import 정리, 포매팅, 리팩터링은 금지한다.

| 구분 | Part A | Part B |
|---|---|---|
| 책임 | STT, 세션 발화 로그, RAG, 메뉴 사실 조회 | 장바구니, 주문 Agent, Service, API |
| 구현 Tool | `transcribe_and_retrieve`, `search_menu_catalog` | `update_order_cart` |
| 공유 파일 | 수정 금지 | 통합 단계에서만 수정 |

```text
1. A branch merge
2. B branch merge
3. B가 main.py·tools/registry.py 등록만 반영
4. 전체 pytest 실행
```

`tools/executor.py`는 기존 allowlist/Pydantic 검증 구조를 그대로 쓴다. 수정이 필요하면 합의 후 B만 처리한다.

## 3. 공통 API 계약

JSON은 camelCase, Python 모델은 snake_case와 Pydantic alias를 사용한다. 여기서 **UPDATE는 CRUD 행위명**이며 실제 FastAPI HTTP method는 `PATCH`다.

| CRUD | API | Backend 함수 | 담당 |
|---|---|---|---|
| Create | `POST /api/kiosk/voice-turn` | `process_voice_turn` | B |
| Create | `POST /api/kiosk/text-turn` | `process_text_turn` | B |
| Read | `GET /api/kiosk/sessions/{sessionId}/cart` | `get_order_cart` | B |
| Update | `UPDATE /api/kiosk/sessions/{sessionId}/cart` | `update_order_cart` | B |
| Update | `POST /api/kiosk/sessions/{sessionId}/ready-for-payment` | `mark_ready_for_payment` | B |

```json
{
  "sessionId": "uuid",
  "transcript": "불고기 버거 세트 하나 주세요",
  "assistantMessage": "불고기 버거 세트 1개를 담았습니다.",
  "speakText": "불고기 버거 세트 1개를 담았습니다.",
  "cart": {"status": "active", "items": [], "total": 0},
  "retrievals": [],
  "suggestions": [],
  "requiresConfirmation": false,
  "trace": []
}
```

## 3.1 `.env` 설정

키오스크는 Docker PostgreSQL + pgvector와 Ollama `embeddinggemma`를 사용한다. `.env`는 Git에 커밋하지 않으며, 팀원은 각자 로컬 `.env`를 아래 기준으로 수정한다.

```env
# Docker PostgreSQL(pgvector)
POSTGRES_DB=agent_db
POSTGRES_USER=agent_user
POSTGRES_PASSWORD=<팀에서 정한 비밀번호>
DATABASE_URL=postgresql://agent_user:<팀에서 정한 비밀번호>@<DB_HOST>:5432/agent_db

# Ollama Embedding
OLLAMA_BASE_URL=http://<OLLAMA_HOST>:11434
OLLAMA_EMBEDDING_MODEL=embeddinggemma

# Frontend → Backend 공통 API Client 주소
BACKEND_API_URL=http://<BACKEND_HOST>:8000
```

- DB와 Ollama를 **각자 PC Docker에서 실행**하면 `<DB_HOST>`, `<OLLAMA_HOST>`는 모두 `127.0.0.1`이다.
- 한 팀원의 Docker를 **공용 인프라로 사용**하면 모든 팀원이 `<DB_HOST>`, `<OLLAMA_HOST>`를 그 담당자 PC의 LAN IP로 맞춘다. 이때 `localhost`를 쓰면 각자 자기 PC에 연결되므로 안 된다.
- 공용 DB를 처음 만드는 담당자는 `docker compose up -d db` 후 `backend/db/init.sql`, `backend/db/seed.sql`이 적용됐는지 확인한다. Ollama 담당자는 `ollama pull embeddinggemma`를 한 번 실행한다.
- 프론트엔드 전용 `BACKEND_API_URL`은 Backend 서버 주소다. 같은 PC에서 Backend를 실행하면 `http://127.0.0.1:8000`, 공용 Backend를 쓰면 해당 서버의 LAN IP와 포트를 사용한다. 이 값은 `DATABASE_URL`과 다른 용도다.

### Frontend 공통 API Client 연결 수정

`frontend/core/api_client.py`는 이미 아래 코드로 `.env`의 `BACKEND_API_URL`을 읽는다. 따라서 키오스크 개발자가 IP를 Python 코드에 하드코딩하지 말고, 각자의 `.env`에서 `BACKEND_API_URL`만 변경한다.

```python
BACKEND_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000").rstrip("/")
```

키오스크 Frontend Client는 `frontend/clients/kiosk_client.py`에 만들고 위 공통 `request()`를 재사용한다. URL은 아래처럼 상대 경로만 작성한다.

```python
request("POST", "/api/kiosk/text-turn", payload)
request("GET", f"/api/kiosk/sessions/{session_id}/cart")
request("PATCH", f"/api/kiosk/sessions/{session_id}/cart", payload)
request("POST", f"/api/kiosk/sessions/{session_id}/ready-for-payment")
```

이 방식이면 팀원별 Backend IP 변경은 `.env`의 `BACKEND_API_URL` 한 곳에서만 관리된다.

## 4. 파일 구조와 소유권

```text
backend/app/
├─ agents/kiosk_order_agent.py                 # B
├─ rag/
│  ├─ __init__.py                              # A
│  ├─ kiosk_knowledge.py                       # A
│  ├─ rag_retriever.py                         # A
│  └─ conversation_store.py                    # A
├─ routers/kiosk_router.py                     # B
├─ schemas/
│  ├─ kiosk_rag.py                             # A
│  └─ kiosk_order.py                           # B
├─ services/
│  ├─ speech_service.py                        # A: 기존 파일 확장
│  └─ kiosk_order_service.py                   # B
├─ tools/kiosk/
│  ├─ __init__.py                              # A
│  ├─ transcribe_and_retrieve.py               # A
│  ├─ search_menu_catalog.py                   # A
│  └─ update_order_cart.py                     # B
├─ tools/registry.py                           # B: 마지막 통합만
└─ main.py                                     # B: 마지막 통합만

backend/db/
├─ init.sql                                    # A: vector 확장·테이블·인덱스
└─ seed.sql                                    # A: 메뉴·RAG 지식 seed

backend/tests/
├─ test_kiosk_rag.py                           # A
├─ test_kiosk_catalog_tools.py                 # A
└─ test_kiosk_order_api.py                     # B
```

공동 수정 충돌을 막기 위해 `schemas/kiosk.py` 하나를 만들지 않는다. A는 `kiosk_rag.py`, B는 `kiosk_order.py`를 각각 소유하고 B Router가 두 모듈을 import한다.

# Part A. 음성·RAG·메뉴 카탈로그

## A1. 책임

A는 음성→텍스트 변환, transcript의 세션 로그 저장, 승인된 메뉴 지식 RAG 검색, 현재 메뉴 카탈로그 조회를 구현한다. 장바구니 변경, Agent, Router는 구현하지 않는다.

### A 소유 파일

```text
backend/app/rag/
backend/app/schemas/kiosk_rag.py
backend/app/services/speech_service.py
backend/app/tools/kiosk/__init__.py
backend/app/tools/kiosk/transcribe_and_retrieve.py
backend/app/tools/kiosk/search_menu_catalog.py
backend/tests/test_kiosk_rag.py
backend/tests/test_kiosk_catalog_tools.py
```

## A2. RAG와 세션 로그

`kiosk_knowledge.py`에는 seed에 사용할 메뉴, 옵션, 재료·알레르기, 품절, 추천, 정책 문서 정의를 둔다. 문서는 예제와 같은 Docker PostgreSQL `documents` 테이블에 적재한다. 최소 필드는 `id(UUID)`, `collection_name`, `title`, `content`, `source`, `chunk_index`, `embedding_provider`, `embedding_model`, `embedding_dimension`, `embedding(vector)`, `metadata(JSONB)`다. 키오스크 RAG의 `collection_name`은 `kiosk_menu`로 고정한다. 메뉴 문서는 한 메뉴 또는 한 규칙당 독립 청크로 만든다.

`rag_retriever.py` 공개 계약:

```python
def retrieve_knowledge(query: str, limit: int = 3) -> list[RetrievedDocument]: ...
```

`OLLAMA_BASE_URL`, `OLLAMA_EMBEDDING_MODEL=embeddinggemma`, `DATABASE_URL`을 `.env`에서 읽는다. `httpx`로 Ollama `/api/embed`를 호출하고, `psycopg.connect()` 뒤 `register_vector(connection)`을 호출한다. 검색은 같은 collection/provider/model/dimension만 대상으로 `ORDER BY embedding <=> %s::vector`를 실행하고, 점수는 `1 - (embedding <=> %s::vector)`로 계산한다. 결과에는 ID, 제목, 본문, 점수, metadata를 포함한다.

문서 ID는 `uuid5(NAMESPACE_URL, f"{collection}:{source}:{chunk_index}")`로 결정적으로 만든다. seed 재실행 시에는 `ON CONFLICT (id) DO UPDATE`로 내용과 임베딩을 갱신해 중복을 방지한다.

`conversation_store.py` 공개 계약:

```python
def append_turn(session_id: str, transcript: str, confidence: float, document_ids: list[str]) -> ConversationTurn: ...
def get_turns(session_id: str) -> list[ConversationTurn]: ...
```

변환 텍스트는 PostgreSQL `conversation_turns`의 세션 RAG query log에 저장한다. 고객 발화를 영구 메뉴 지식 컬렉션에 추가하면 오인식과 개인정보가 지식으로 오염되므로 절대 저장하지 않는다.

## A3. Schema

`kiosk_rag.py` 모델:

```text
TranscribeAndRetrieveArgs
SearchMenuCatalogArgs
RetrievedDocument
TranscriptResult
MenuCatalogItem
MenuCatalogResult
```

- `session_id`: UUID
- `audio_base64`: 빈 문자열 불가
- `mime_type`: audio/webm, audio/wav, audio/mpeg만 허용
- `query`: 1~300자, `limit`: 1~5
- `allergens_to_avoid`: 최대 10개

## A4. Tool 1: `transcribe_and_retrieve`

```json
{"session_id":"uuid","audio_base64":"...","mime_type":"audio/webm"}
```

음성 크기·MIME·빈 데이터를 검증한 뒤 `speech_service.transcribe()`로 transcript를 만든다. transcript, confidence, 검색 문서 ID를 세션 로그에 저장하고 RAG 결과를 반환한다.

```json
{"turn_id":"uuid","transcript":"매운 버거 추천해 줘","confidence":0.94,"retrieved_documents":[],"needs_confirmation":false}
```

API 키가 없으면 Mock STT로 동작해야 한다. `transcript_override`는 개발 환경에서만 허용한다. confidence 0.70 미만은 `needs_confirmation=true`이며 장바구니 Tool을 호출하지 않는다.

## A5. Tool 2: `search_menu_catalog`

RAG는 추천 근거를 제공하고, 이 Tool은 PostgreSQL `menu_catalog`에서 주문 가능한 현재 사실을 제공한다.

```json
{"query":"매운 치킨 버거","category":"burger","allergens_to_avoid":["우유"],"limit":5}
```

각 결과는 `menu_id`, 이름, 카테고리, 가격, 설명, `available`, 알레르겐, 가능한 옵션, 대체 메뉴 ID를 포함한다. 품절 메뉴는 제거하지 않고 `available=false`로 반환한다.

## A6. A 완료 기준

- 메뉴·추천·정책 질문에 관련 RAG 문서를 반환한다.
- transcript와 문서 ID가 세션별로 저장된다.
- 잘못된 MIME, 빈/과대 음성은 검증 오류다.
- Mock STT가 외부 API 키 없이 동작한다.
- 카탈로그가 가격·알레르겐·품절·대체 메뉴를 정확히 반환한다.
- A Tool은 장바구니를 읽거나 변경하지 않는다.

# Part B. 장바구니·주문 Agent·API

## B1. 책임

B는 장바구니 상태와 서버 가격 계산을 구현하고 A Tool 결과를 사용하는 주문 Agent, Service, Router를 구현한다. A의 RAG 알고리즘·STT 코드는 수정하지 않는다.

### B 소유 파일

```text
backend/app/schemas/kiosk_order.py
backend/app/tools/kiosk/update_order_cart.py
backend/app/agents/kiosk_order_agent.py
backend/app/services/kiosk_order_service.py
backend/app/routers/kiosk_router.py
backend/tests/test_kiosk_order_api.py
backend/app/tools/registry.py                 # 마지막 통합만
backend/app/main.py                           # 마지막 통합만
```

## B2. Schema와 상태

`kiosk_order.py` 모델:

```text
CartSelection
CartUpdateArgs
CartItem
OrderCart
VoiceTurnRequest
TextTurnRequest
KioskTurnResponse
ReadyForPaymentResponse
```

상태는 `active | ready_for_payment | cancelled`다. `ready_for_payment` 이후에는 장바구니 변경을 거부한다. `operation`은 `add | update | remove | clear | ready_for_payment`만 허용한다. 수량은 1~10, 패티·치즈 추가는 0~3으로 제한하고, 가격·합계는 입력으로 받지 않는다.

## B3. Tool 3: `update_order_cart`

이 Tool만 PostgreSQL 트랜잭션 안에서 장바구니를 변경한다. 메뉴 존재·품절·세트 규칙·옵션 호환성을 서버 카탈로그로 재검증하고 가격을 재계산한다. A의 공개 카탈로그 함수를 import할 수 있으나 A 파일은 수정하지 않는다.

```json
{
  "session_id":"uuid",
  "operation":"add",
  "menu_id":"burger_bulgogi",
  "quantity":1,
  "order_type":"takeout",
  "selection":{"order_form":"set","size_up":false,"extra_patty":0,"extra_cheese":1,"drink_id":"drink_cola_zero"}
}
```

반환값은 최신 장바구니와 `subtotal`, `discount`, `total`, `warnings`이다. 결제·POS·재고 차감은 절대 수행하지 않는다.

## B4. Agent와 Service

`kiosk_order_agent.py`는 Tool 함수를 직접 호출하지 않고 안전 실행기를 사용한다.

```text
음성: transcribe_and_retrieve → 필요 시 search_menu_catalog → 명확한 주문이면 update_order_cart
텍스트: RAG retrieve → 필요 시 search_menu_catalog → 명확한 주문이면 update_order_cart
```

confidence가 낮거나 대상이 모호하면 확인 질문만 반환한다. 알레르기·품절·가격은 카탈로그 Tool 근거 없이 단정하지 않는다. “주문 완료”이고 장바구니가 비어 있지 않을 때만 `ready_for_payment`를 실행한다. 요청당 Tool 호출은 최대 3회다.

`kiosk_order_service.py`는 Agent 결과를 API 응답으로 조립하고 내부 오류·traceback은 노출하지 않는다.

## B5. Router 통합

`kiosk_router.py` endpoint:

```text
POST /api/kiosk/voice-turn
POST /api/kiosk/text-turn
GET  /api/kiosk/sessions/{session_id}/cart
PATCH /api/kiosk/sessions/{session_id}/cart
POST /api/kiosk/sessions/{session_id}/ready-for-payment
```

모든 신규 파일과 테스트가 준비된 뒤 B만 다음을 수행한다.

1. `tools/registry.py`에 A Tool 2개와 B Tool 1개를 등록한다.
2. `main.py`에 `kiosk_router`를 import·등록한다.

공통 파일에는 다른 기능의 리팩터링이나 포맷을 하지 않고 필요한 등록만 추가한다.

## B6. B 완료 기준

- 메뉴 추가·옵션/수량 변경·삭제·비우기·포장 변경이 서버 가격으로 동작한다.
- 품절 메뉴와 불가능한 옵션은 담기지 않는다.
- 비어 있지 않은 장바구니만 결제 전 확정할 수 있으며 이후 수정은 거부된다.
- 음성/텍스트 Happy Case가 Tool trace와 최신 장바구니를 반환한다.
- 모호한 주문, 낮은 confidence, 알레르기 질문은 장바구니를 바꾸지 않는다.
- 결제 관련 API, 데이터, 외부 호출이 없다.

## 5. 통합 Happy Case

```text
“매운 거 좋아하는데 든든한 메뉴 추천해 줘”
→ STT/RAG + search_menu_catalog
“매운 치킨 버거 세트 하나, 치즈 추가, 제로 콜라로 주세요”
→ 메뉴/옵션 검증 + update_order_cart(add)
“주문 완료”
→ update_order_cart(ready_for_payment) + 결제 화면 안내
```

`docker-compose.yml`의 PostgreSQL 서비스를 먼저 실행하고 `backend/db/init.sql`, `backend/db/seed.sql`을 적용한 뒤 테스트한다. 전체 테스트는 외부 API 키 없이 Mock STT와 Mock LLM 또는 결정적 규칙 기반 응답으로 통과해야 한다.
