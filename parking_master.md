# 주차장 차량 출입 시스템 마스터 설계서

## 1. 프로젝트 방향

이 문서는 기존 `C:\mini_frontend\agent_0821\agent_0821` 프로젝트를 이어서 개발하는 주차장 차량 출입 시스템의 기준 설계다. 기존 메뉴 추천·학습 도우미 기능과 이미 있는 FastAPI/Streamlit/Tool 구조는 삭제하지 않고 유지한다.

신규 기능은 사이드바의 독립 페이지 두 개로 제공한다.

1. **주차 출입 Workflow**: Backend가 정해진 1~4단계를 고정 순서로 실행한다.
2. **주차 출입 AI Agent**: Agent가 번호판 인식 결과를 바탕으로 공용 Tool 호출 또는 재촬영 요청을 선택한다.

두 시스템은 차량 등록 정보를 조회하는 공용 Tool 하나, `vehicle_lookup`을 반드시 함께 사용한다. 실제 차단기나 CCTV는 제어하지 않고 `gate_command: open | keep_closed`만 반환하는 안전한 시뮬레이션으로 시작한다.

## 2. 공통 입차 흐름

```text
1. Streamlit 카메라로 차량 번호판 이미지를 캡처한다.
2. Backend Vision/OCR 서비스가 번호판을 인식하고 추출한다.
3. vehicle_lookup Tool이 Docker PostgreSQL의 차량 데이터를 조회한다.
4. 등록·활성 차량이면 Backend 정책이 승인하고, 아니면 거절한다.
```

카메라 UI는 `C:\mini_agent\mini_agent_01_llm\frontend\app_pages\09_camera_voice_guide.py` 수준을 따른다.

- `st.camera_input`으로 사진을 촬영하고 미리보기를 표시한다.
- 분석 중 Spinner, 성공·거절·재촬영 메시지를 같은 페이지에 표시한다.
- 카메라·이미지 업로드는 기본적으로 한 번의 입차 요청만 처리하며, 이미지 원본은 장기 저장하지 않는다.
- 개발과 테스트에서는 카메라를 사용할 수 없을 때 테스트 이미지 업로드 또는 명시적 번호판 입력을 허용한다.

## 3. Workflow와 AI Agent의 책임 분리

| 항목 | Workflow 시스템 | AI Agent 시스템 |
|---|---|---|
| 프론트 페이지 | `03_parking_workflow.py` | `04_parking_agent.py` |
| 처리 순서 | OCR → Tool → 정책 평가가 고정 | Agent가 OCR 후보·신뢰도를 보고 Tool 호출 또는 재촬영을 결정 |
| DB 조회 | 공용 `vehicle_lookup` | 동일 공용 `vehicle_lookup` |
| 최종 승인 | 결정적 Backend 정책 | 동일한 결정적 Backend 정책 |
| 표시 정보 | 고정 4단계 Trace | Agent 판단, Tool Call, Tool Result, 정책 Trace |

Agent는 차단기를 열거나 DB를 직접 접근할 수 없다. Agent는 허용 목록에 등록된 읽기 전용 `vehicle_lookup` Tool을 최대 한 번 호출할 수 있으며, `approved`와 `gate_command`는 항상 Backend 정책 함수가 결정한다.

## 4. 공용 Tool 계약

```text
name: vehicle_lookup
purpose: 번호판으로 PostgreSQL 차량 등록·활성·만료 상태를 읽기 전용 조회
```

입력은 Pydantic으로 검증·정규화한다.

```json
{"plate_number": "12가3456"}
```

Tool은 OCR, 승인 판단, 차단기 제어 또는 DB 상태 변경을 수행하지 않는다.

```json
{
  "found": true,
  "plate_number": "12가3456",
  "vehicle_id": "uuid",
  "owner_label": "테스트 차량 A",
  "access_status": "active",
  "access_expires_at": null
}
```

미등록도 오류가 아니라 업무 결과다.

```json
{"found": false, "plate_number": "12가3456", "access_status": "not_registered"}
```

## 5. Backend 동작

### 5.1 고정 Workflow

```text
POST /api/parking/workflow/entry
→ 이미지 MIME·크기·시그니처 검증
→ plate_recognition_service.extract_plate(image)
→ 번호판 없음 또는 신뢰도 미달 시 재촬영 요청
→ vehicle_lookup(plate_number)
→ entry_policy_service.evaluate(vehicle)
→ 승인/거절·Trace 반환
```

- 등록됨 + 활성 + 만료되지 않음: `approved=true`, `gate_command=open`
- 미등록, 비활성, 만료, OCR 오류: `approved=false`, `gate_command=keep_closed`
- OCR 실패 때는 Tool을 호출하지 않는다.

### 5.2 AI Agent 방식

```text
POST /api/parking/agent/entry
→ 이미지 검증 및 OCR 후보 추출
→ parking_entry_agent가 후보·신뢰도·Tool Schema를 평가
→ 명확한 번호판일 때만 vehicle_lookup Tool Call 생성
→ tools/executor.py의 Allowlist + Pydantic 검증 후 Tool 실행
→ entry_policy_service가 최종 승인/거절
→ Agent가 Tool Result 기반 안내문과 Trace 생성
```

- Agent가 번호판을 추측하거나 미등록 차량을 승인하면 안 된다.
- Tool 호출은 최대 한 번이다.
- API 키가 없는 환경에서는 Mock Agent로 Happy Case를 재현한다.

## 6. Docker 데이터 저장소

프로젝트 루트에 `docker-compose.yml`을 추가해 PostgreSQL(pgvector)을 실행한다.

### 공용 PostgreSQL 운영 원칙

PostgreSQL은 팀원 한 명의 인스턴스를 공용으로 사용한다. DB 담당자만 Docker PostgreSQL의 생성·업데이트·백업과 `init.sql`·`seed.sql` 실행을 담당한다. 다른 개발자는 자신의 PostgreSQL 컨테이너를 별도로 만들지 않고, 각자의 `.env`에서 담당자 DB의 연결 정보만 설정해 Backend를 실행한다.

모든 팀원은 `.env`의 `DATABASE_URL`을 **Docker PostgreSQL을 실행하는 담당자 컴퓨터의 IP 또는 서버 주소**로 변경해야 한다. 다른 팀원의 `localhost`는 각자 자신의 컴퓨터를 뜻하므로 공용 DB 연결값으로 사용하면 안 된다.

```env
DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:5432/<database>
```

예를 들어 담당자 PC의 주소가 `192.168.0.10`이면, 다른 팀원의 `.env`도 다음처럼 설정한다.

```env
DATABASE_URL=postgresql+psycopg://parking_user:<password>@192.168.0.10:5432/parking_db
```

- `.env`는 Git에 커밋하지 않고, `.env.example`에는 변수 이름과 예시 형식만 둔다.
- DB 담당자는 pgvector 확장, 테이블, 인덱스와 임의 차량 seed 데이터를 먼저 준비한다.
- 스키마·seed 변경은 담당자가 적용하거나 팀 합의 후 한 번만 적용한다. 각 개발자가 임의로 공용 DB를 초기화하거나 seed를 중복 삽입하지 않는다.
- 공용 DB 연결·조회 실패 시 출입을 승인하지 않는다.

```text
PostgreSQL(pgvector)
  - vehicles: 차량 번호, 표시명, 활성 여부, 만료일
  - entry_events: 요청 ID, 인식 번호, 승인 결과, 사유, 생성 시각
  - CREATE EXTENSION vector
```

1차 차량 조회는 `vehicles.plate_number`의 exact match와 unique index를 사용한다. pgvector는 확장을 활성화하되, 차량 승인 판단에는 사용하지 않는다. 향후 주차 정책 문서·관리자 메모 의미 검색에만 확장 가능하다.

초기 데이터는 `backend/db/seed.sql`에 임의 번호판만 넣는다. 실제 번호판·개인정보는 사용하지 않는다.

| plate_number | owner_label | access_status | access_expires_at |
|---|---|---|---|
| `12가3456` | 테스트 차량 A | active | null |
| `34나5678` | 테스트 차량 B | inactive | null |
| `56다7890` | 테스트 차량 C | active | 과거 시각 |

PostgreSQL 조회에 실패하면 출입을 승인하지 않는다. 내부 오류 상세는 사용자 화면에 노출하지 않는다.

## 7. 기존 프로젝트에 추가할 구조

기존 `frontend`, `backend/app`, `backend/tests` 폴더를 재사용한다. `learning_unit`, `starter`, `solution`은 애플리케이션 구현 대상으로 복제하지 않는다.

```text
agent_0821/
├─ docker-compose.yml                         # 신규
├─ .env.example                               # DB·Vision 설정 추가
├─ frontend/
│  ├─ app.py                                  # 주차 메뉴 2개 등록
│  ├─ app_pages/
│  │  ├─ 03_parking_workflow.py               # 신규
│  │  └─ 04_parking_agent.py                  # 신규
│  ├─ clients/parking_client.py               # 신규
│  └─ core/api_client.py                      # 기존 공통 HTTP 처리 재사용
├─ backend/
│  ├─ db/
│  │  ├─ init.sql                             # 신규
│  │  └─ seed.sql                             # 신규
│  ├─ app/
│  │  ├─ main.py                              # parking_router 등록
│  │  ├─ core/config.py                       # DB·이미지 제한 설정 추가
│  │  ├─ routers/parking_router.py            # 신규
│  │  ├─ schemas/parking.py                   # 신규
│  │  ├─ services/plate_recognition_service.py# 신규
│  │  ├─ services/parking_workflow_service.py # 신규
│  │  ├─ services/entry_policy_service.py     # 신규
│  │  ├─ agents/parking_entry_agent.py        # 신규
│  │  ├─ repositories/vehicle_repository.py   # 신규 폴더·파일
│  │  └─ tools/vehicle_lookup.py              # 신규, 공용 Tool
│  └─ tests/
│     ├─ test_vehicle_lookup.py                # 신규
│     ├─ test_parking_workflow_api.py          # 신규
│     └─ test_parking_agent_api.py             # 신규
└─ master.md
```

`backend/app/tools/registry.py`와 `backend/app/tools/executor.py`의 현재 안전 실행 방식을 재사용한다. `vehicle_lookup`만 Allowlist에 추가하며, 메뉴·학습 Tool과 충돌하지 않게 독립적인 Tool 이름과 스키마를 사용한다.

## 8. API 공통 결과

```text
POST /api/parking/workflow/entry
POST /api/parking/agent/entry
```

```json
{
  "system_type": "workflow | agent",
  "request_id": "uuid",
  "recognized_plate_number": "12가3456",
  "recognition_confidence": 0.98,
  "approved": true,
  "gate_command": "open | keep_closed",
  "reason": "등록된 활성 차량입니다.",
  "tool_result": {},
  "trace": []
}
```

## 9. 완료 기준과 구현 순서

### 완료 기준

- 두 주차 시스템은 서로 다른 Streamlit 페이지에서 실행된다.
- 두 시스템은 하나의 `vehicle_lookup` Tool 구현을 공용으로 사용한다.
- 카메라 이미지 → OCR → PostgreSQL 조회 → Backend 승인 결과가 동작한다.
- 등록·활성 차량은 승인, 미등록·비활성·만료 차량은 거절한다.
- OCR 실패 또는 신뢰도 미달은 Tool 호출 없이 재촬영을 요청한다.
- Agent는 Tool을 직접 실행하지 않으며 안전 실행기와 Backend 정책을 거친다.

### 구현 순서

1. Docker Compose와 PostgreSQL 스키마·seed 연결 설정을 추가한다.
2. `vehicle_lookup` Tool과 `vehicle_repository`를 만들고 DB 조회 테스트를 작성한다.
3. OCR/Vision 추출과 이미지 검증 서비스를 구현한다.
4. Workflow API와 `03_parking_workflow.py`를 구현한다.
5. 동일 Tool 계약을 쓰는 Agent API와 `04_parking_agent.py`를 구현한다.
6. 정책·중복 요청·오류 처리와 전체 테스트를 완료한다.
