# 햄버거 주문 음성 키오스크 마스터 설계서

## 1. 목표와 범위

이 문서는 현재 `C:\mini_frontend\agent_0821\agent_0821` 구조를 유지하면서 추가할 **햄버거 주문 음성 키오스크**의 구현 기준이다. 고객은 음성으로 메뉴를 탐색·추천받고 옵션을 조정하여 장바구니를 완성한다.

범위는 **결제 직전 주문 확인**까지다. 결제 승인, PG 연동, 실제 POS 전송, 회원 식별, 쿠폰 소진은 구현하지 않는다. 주문 최종 화면에서 고객이 명시적으로 `주문 완료`를 말하거나 누르면 `ready_for_payment` 상태로만 전환한다.

```text
음성 입력 → STT → RAG 검색 → Agent 판단 → 메뉴/장바구니 Tool → 주문 확인 → 결제 대기
```

음성 UI는 `C:\mini\_agent\mini\_agent\_01\_llm`의 1~7 페이지 수준처럼 녹음 버튼, 인식 텍스트 미리보기, 처리 중 표시, Agent 답변과 장바구니를 한 화면에 보여 주는 방식으로 구현한다. 세부 구현은 이후 Python 파일을 추가할 때 이 문서를 따른다.

## 2. 핵심 원칙

- RAG는 메뉴·정책·추천 지식의 근거를 제공하며, 가격·품절·장바구니를 임의로 결정하지 않는다.
- 주문 변경은 LLM 텍스트가 아닌 검증된 `cart_update` Tool만 수행한다.
- 품절·가격·옵션 가능 여부는 Tool의 현재 데이터가 최종 기준이다.
- 알레르기 정보는 안내용이다. Agent는 고객이 알레르기를 언급하면 위험 메뉴를 경고하고, 확답 대신 성분표 확인을 안내한다.
- Agent는 결제·POS·재고 상태를 변경할 수 없다.
- 음성 원본은 기본적으로 저장하지 않는다. 동의한 경우에만 파일 경로 또는 객체 저장소 키를 짧은 보존 기간으로 기록한다.

## 3. RAG 데이터 설계

RAG 저장소는 Docker PostgreSQL의 **pgvector만** 사용한다. `backend/app/rag/rag_retriever.py`는 PostgreSQL에 메뉴 지식 문서를 적재하고 임베딩 유사도 검색을 수행한다. 원본 데이터는 지식 문서이며 Agent는 Tool을 통해서만 검색한다.

### 3.1 지식 문서 유형

| 유형 | 필수 내용 | 예시 질문 |
|---|---|---|
| 메뉴 | ID, 메뉴명, 카테고리, 가격, 설명, 구성, 맵기 | “매운 버거 있어?” |
| 옵션 | 단품/세트, 세트 구성, 사이즈업, 패티·치즈 추가, 음료 변경 제약 | “치즈 하나 더 넣어 줘” |
| 재료·알레르기 | 재료, 알레르겐, 제외 가능한 재료, 교차오염 고지 | “우유 안 들어간 메뉴 있어?” |
| 판매 상태 | 판매 가능/품절, 판매 시간, 품절 대체 후보 | “새우버거 주문돼?” |
| 추천 | 조건, 추천 메뉴/세트, 추천 근거 | “아이랑 먹기 좋은 세트 추천해 줘” |
| 매장 정책 | 포장, 세트 규칙, 쿠폰·할인 조건, 주문 변경 가능 시점 | “포장으로 바꿔 줘” |

각 문서는 한 가지 사실 또는 한 메뉴 단위를 설명하는 150~400자 내외의 독립 청크로 저장한다. `menu_id`, `category`, `available`, `allergens`, `intent`, `updated_at` 메타데이터를 반드시 둔다. 가격·판매 상태가 바뀌면 해당 문서를 갱신한다.

```json
{
  "document_id": "menu-bulgogi-001",
  "type": "menu",
  "menu_id": "burger_bulgogi",
  "title": "불고기 버거",
  "content": "불고기 버거는 달콤한 불고기 소스와 소고기 패티, 양상추, 피클로 구성된 단품 메뉴입니다. 가격은 6,500원이며 세트 변경이 가능합니다.",
  "metadata": {
    "category": "burger",
    "available": true,
    "allergens": ["밀", "대두", "계란"],
    "updated_at": "2026-08-25"
  }
}
```

### 3.2 음성 텍스트의 저장 원칙

사용자 발화를 메뉴 지식과 같은 컬렉션에 영구 임베딩하면 오인식·개인정보·프롬프트 주입이 지식으로 섞이는 문제가 생긴다. 따라서 필수 Tool은 STT 결과를 **세션 대화 로그(RAG query log)**에 저장하고, 그 텍스트로 승인된 메뉴 지식 컬렉션을 검색한다. 이것을 이 프로젝트에서 “변환 텍스트를 RAG에 저장하고 가져오기”로 정의한다.

```text
음성 파일 → transcript 생성 → conversation_turns 저장
                         └→ transcript 임베딩 → kiosk_knowledge 검색 → 근거 문서 반환
```

세션 로그는 주문 세션 종료 후 삭제하거나 익명 통계로만 보존한다. 고객 발화를 RAG 지식 문서로 승격하는 일은 관리자 검토 과정 없이는 허용하지 않는다.

## 4. Tool 설계: 총 3개

모든 Tool은 `backend/app/tools/registry.py` 등록과 `tools/executor.py`의 allowlist·Pydantic 인자 검증을 통과해야 한다. Agent가 Python 함수를 직접 호출하면 안 된다.

### Tool 1. `transcribe_and_retrieve` — 필수

역할: 음성 입력을 텍스트로 변환하고, 변환 텍스트를 세션 로그에 저장한 뒤 RAG에서 근거 문서를 가져온다.

```json
{
  "session_id": "uuid",
  "audio_base64": "...",
  "mime_type": "audio/webm"
}
```

```json
{
  "turn_id": "uuid",
  "transcript": "불고기 버거 세트 하나 주세요",
  "confidence": 0.94,
  "retrieved_documents": [
    {"document_id": "menu-bulgogi-001", "title": "불고기 버거", "score": 0.91}
  ],
  "needs_confirmation": false
}
```

- MIME, 최대 파일 크기, 빈 오디오를 먼저 검증한다.
- `speech_service`가 OpenAI STT 또는 Mock STT를 사용한다. API 키가 없으면 테스트용 `transcript_override`를 개발 환경에서만 허용한다.
- transcript·신뢰도·검색 문서 ID를 `conversation_turns`에 기록한다.
- 인식 신뢰도가 기준 미만이면 메뉴 변경 Tool을 호출하지 않고 재발화를 요청한다.

### Tool 2. `search_menu_catalog`

역할: RAG 근거를 바탕으로도 반드시 현재 메뉴 카탈로그에서 정확한 메뉴·옵션·알레르기·품절 여부를 검증한다. 읽기 전용 Tool이다.

```json
{
  "query": "매운 메뉴",
  "category": "burger",
  "allergens_to_avoid": ["우유"],
  "limit": 5
}
```

반환에는 `menu_id`, 이름, 현재 가격, 판매 가능 여부, 가능한 옵션, 알레르겐, 추천 근거를 포함한다. 품절 메뉴는 숨기지 않고 `available=false`와 대체 메뉴를 함께 반환한다.

### Tool 3. `update_order_cart`

역할: 검증된 메뉴와 옵션으로 장바구니를 만들거나 변경한다. 결제나 POS 전송은 수행하지 않는다.

```json
{
  "session_id": "uuid",
  "operation": "add",
  "menu_id": "burger_bulgogi",
  "quantity": 1,
  "order_type": "takeout",
  "selection": {
    "order_form": "set",
    "size_up": false,
    "extra_patty": 0,
    "extra_cheese": 1,
    "drink_id": "drink_cola_zero"
  }
}
```

`operation`은 `add | update | remove | clear | ready_for_payment`만 허용한다. Tool은 메뉴 존재, 수량, 품절, 옵션 호환성, 세트 구성, 할인 조건을 서버 데이터로 검증하고, 성공 시 가격을 서버에서 재계산한다. 고객에게 보여줄 최종 합계는 이 Tool 결과만 사용한다.

```json
{
  "cart_status": "active",
  "items": [],
  "subtotal": 0,
  "discount": 0,
  "total": 0,
  "warnings": [],
  "next_action": "confirm_order"
}
```

## 5. 음성 주문 AI Agent

파일: `backend/app/agents/kiosk_order_agent.py`

Agent는 고객 친화적인 한국어 답변과 Tool 호출 계획만 만든다. 주문 상태·금액·유효 옵션은 Tool 결과를 인용한다. 한번의 턴에서 Tool 호출은 최대 3회이며 다음 순서를 지킨다.

```text
1. 음성 입력이면 transcribe_and_retrieve
2. 메뉴·추천·알레르기·품절 질문이면 search_menu_catalog
3. 고객이 명확히 주문/변경 의사를 표시하면 update_order_cart
4. Tool 결과를 근거로 짧은 음성 응답과 화면용 카드 반환
```

대표 흐름:

```text
“매운 거 좋아하는데 든든하게 먹고 싶어”
→ STT + 추천 RAG 검색
→ 메뉴 카탈로그 검색
→ “매운 맛을 원하시면 매운 치킨 버거 세트를 추천드려요. 주문할까요?”

“그걸로 세트 하나, 치즈 추가하고 콜라 제로로”
→ STT + RAG 검색
→ 메뉴/옵션 정확성 확인
→ 장바구니 추가
→ “매운 치킨 버거 세트 1개, 치즈 추가, 제로 콜라로 담았습니다. 총액은 …원입니다.”

“주문 완료”
→ 장바구니 상태 확인 후 ready_for_payment
→ “주문을 확인했습니다. 화면에서 결제 수단을 선택해 주세요.”
```

### Agent 안전 규칙

- 알레르기와 품절 여부는 `search_menu_catalog` 결과 없이는 단정하지 않는다.
- “치즈 빼줘”처럼 대상 메뉴가 모호하면 최근 장바구니 항목을 추측하지 않고 확인 질문을 한다.
- 인식이 불명확하면 “다시 말씀해 주세요”로 끝내며 장바구니를 변경하지 않는다.
- `ready_for_payment` 이후에는 주문 변경 API를 거부하고 새 주문 또는 결제 전 화면 복귀를 안내한다.
- 결제 정보, 카드 번호, 개인정보를 음성으로 요청·저장하지 않는다.

## 6. 백엔드·프론트엔드 공통 API 계약

모든 JSON 필드는 camelCase를 사용한다. Python Pydantic 모델은 alias로 snake_case를 매핑한다. 공통 접두사는 `/api/kiosk`다.

| 목적 | Method / API | Backend 함수 | Frontend client 함수 |
|---|---|---|---|
| 음성 인식+RAG 조회 | `POST /api/kiosk/voice-turn` | `process_voice_turn` | `submitVoiceTurn` |
| 텍스트 주문/RAG 조회 | `POST /api/kiosk/text-turn` | `process_text_turn` | `submitTextTurn` |
| 장바구니 조회 | `GET /api/kiosk/sessions/{sessionId}/cart` | `get_order_cart` | `getOrderCart` |
| 장바구니 직접 변경 | `UPDATE /api/kiosk/sessions/{sessionId}/cart` | `update_order_cart` | `updateOrderCart` |
| 결제 전 주문 확정 | `POST /api/kiosk/sessions/{sessionId}/ready-for-payment` | `mark_ready_for_payment` | `readyForPayment` |

`voice-turn` 요청 예시:

```json
{
  "sessionId": "uuid",
  "audioBase64": "...",
  "mimeType": "audio/webm",
  "orderType": "takeout"
}
```

공통 응답 예시:

```json
{
  "sessionId": "uuid",
  "transcript": "불고기 버거 세트 하나 주세요",
  "assistantMessage": "불고기 버거 세트 1개를 담을까요?",
  "speakText": "불고기 버거 세트 1개를 담을까요?",
  "cart": {"status": "active", "items": [], "total": 0},
  "retrievals": [],
  "suggestions": [],
  "requiresConfirmation": true,
  "trace": []
}
```

`text-turn`은 `audioBase64`, `mimeType` 대신 `text`를 받으며, 테스트·접근성·음성 인식 실패 대체 입력으로 사용한다. `ready-for-payment`은 `cart.status=ready_for_payment`만 반환하며 결제를 시작하지 않는다.

## 7. 추가할 파일 구조

현재 폴더와 기존 기능은 그대로 두고 다음 Python 파일만 추가 또는 최소 수정한다. RAG 학습 코드의 00~06 수준을 맞춰 데이터 로딩, 청킹, 임베딩, 검색, Agent 결합을 작고 읽기 쉬운 모듈로 분리한다.

```text
backend/app/
├─ agents/kiosk_order_agent.py                 # 신규: Tool 계획·최종 안내
├─ rag/
│  ├─ __init__.py                              # 신규
│  ├─ kiosk_knowledge.py                       # 신규: 메뉴/정책 RAG 문서 목 데이터
│  ├─ rag_retriever.py                         # 신규: 청킹·임베딩·유사도 검색 인터페이스
│  └─ conversation_store.py                    # 신규: 세션별 transcript·검색 이력
├─ routers/kiosk_router.py                     # 신규: 공통 API
├─ schemas/kiosk.py                            # 신규: 요청·응답·Tool Args 검증
├─ services/kiosk_order_service.py             # 신규: API 흐름 조정
├─ services/speech_service.py                  # 기존 파일 확장: STT 제공자·Mock 지원
├─ tools/kiosk/
│  ├─ __init__.py                              # 신규
│  ├─ transcribe_and_retrieve.py               # 신규: Tool 1
│  ├─ search_menu_catalog.py                   # 신규: Tool 2
│  └─ update_order_cart.py                     # 신규: Tool 3
├─ tools/registry.py                           # 기존: Tool 3개 등록
├─ tools/executor.py                           # 기존: allowlist/Pydantic 실행 재사용
└─ main.py                                     # 기존: kiosk_router 등록

frontend/
├─ app.py                                      # 기존: 페이지 메뉴 등록
├─ app_pages/05_voice_kiosk.py                 # 신규: 녹음·텍스트 대체·장바구니 UI
└─ clients/kiosk_client.py                     # 신규: 위 공통 API 함수

backend/tests/
├─ test_kiosk_rag.py                           # 신규
├─ test_kiosk_tools.py                         # 신규
└─ test_kiosk_api.py                           # 신규
```

## 8. 데이터 모델과 상태

초기 버전도 Docker PostgreSQL + pgvector를 사용한다. 메뉴 지식·현재 메뉴 카탈로그·주문 세션·장바구니·대화 로그를 모두 PostgreSQL에 저장한다. 외부 API 키 없이 Mock STT/LLM으로 Happy Case가 동작해야 하지만, Backend 실행 전에는 Docker DB를 반드시 기동하고 초기 스키마·seed를 적용해야 한다.

```text
OrderSession
  ├─ session_id
  ├─ status: active | ready_for_payment | cancelled
  ├─ order_type: dine_in | takeout
  ├─ cart_items
  └─ conversation_turns

CartItem
  ├─ menu_id / name / quantity
  ├─ order_form: single | set
  ├─ selected_options
  ├─ unit_price / option_price / line_total
  └─ allergen_snapshot
```

```text
PostgreSQL + pgvector
  - documents: collection_name=kiosk_menu, 지식 본문, metadata(JSONB), embedding(vector)
  - menu_catalog: 현재 가격, 옵션, 알레르겐, 판매 상태
  - order_sessions: 주문 유형, 주문 상태, 생성·수정 시각
  - order_cart_items: 메뉴·선택 옵션·서버 계산 금액
  - conversation_turns: transcript, STT 신뢰도, 검색 문서 ID
```

`backend/db/init.sql`은 `CREATE EXTENSION IF NOT EXISTS vector`와 예제 호환 `documents` 테이블·인덱스를 만들고, `backend/db/seed.sql`은 테스트 메뉴와 RAG 문서를 적재한다. 임베딩은 Ollama `embeddinggemma`, 연결은 `psycopg` + `register_vector`, 검색은 pgvector `<=>` 코사인 거리 연산자를 사용한다. `docker-compose.yml`의 PostgreSQL·Ollama 서비스만 기동한다. 향후 POS/재고 API를 붙일 때는 `search_menu_catalog`과 `update_order_cart` 내부의 카탈로그 Provider만 교체하며 API·Agent·프론트엔드 계약은 유지한다.

## 9. 구현 순서와 완료 기준

1. `schemas/kiosk.py`, 메뉴·옵션·정책 RAG 문서와 카탈로그 목 데이터를 만든다.
2. RAG retriever와 세션 transcript 저장소를 구현하고 검색 테스트를 작성한다.
3. `transcribe_and_retrieve`, `search_menu_catalog`, `update_order_cart` 세 Tool을 구현·등록한다.
4. kiosk Agent와 Service, Router를 연결한다.
5. Streamlit 음성 키오스크 페이지와 공통 API client를 추가한다.
6. Mock STT와 Mock LLM으로 전체 Happy Case 및 예외 테스트를 통과시킨다.

완료 조건은 다음과 같다.

- 고객 음성은 텍스트로 변환되고 세션 로그에 저장되며 메뉴 지식 RAG 검색 결과를 반환한다.
- 메뉴, 옵션, 재료/알레르기, 품절, 추천, 매장 정책을 근거 문서로 검색할 수 있다.
- Agent는 정확히 위 3개 Tool만 allowlist로 사용한다.
- 품절 메뉴, 불가능한 옵션, 모호한 주문, 낮은 STT 신뢰도에서 장바구니를 잘못 변경하지 않는다.
- 주문 추가·수정·삭제·포장 변경과 결제 전 주문 확정이 가능하다.
- 가격·합계는 Backend Tool이 계산하고, 결제·POS는 호출하지 않는다.
- API 키 없이 텍스트 입력과 Mock STT Happy Case가 동작하고 pytest가 통과한다.
