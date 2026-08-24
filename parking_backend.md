# 주차 출입 시스템 백엔드 개발 계획서

## 1. 목표와 범위

기존 FastAPI, Agent, Tool 구조와 메뉴 추천·학습 도우미 기능을 유지하면서 다음 두 주차 출입 방식을 추가한다.

1. **주차 출입 Workflow**: 이미지 검증 → OCR → 차량 조회 Tool → 출입 정책을 고정 순서로 실행
2. **주차 출입 AI Agent**: OCR 결과를 바탕으로 Agent가 차량 조회 Tool 호출 또는 재촬영을 선택

두 방식은 읽기 전용 `vehicle_lookup` Tool과 결정적 Backend 출입 정책을 공용으로 사용한다. 실제 CCTV나 차단기는 제어하지 않고 `gate_command: open | keep_closed`만 반환한다.

## 2. 담당자별 역할

### yj: 데이터베이스 담당

- Docker PostgreSQL(pgvector) 구성 및 공용 인스턴스 운영
- `docker-compose.yml`
- `backend/db/init.sql`, `backend/db/seed.sql`
- `vehicles`, `entry_events` 테이블, 제약 조건, 인덱스
- pgvector 확장 활성화
- 임의 번호판 seed 데이터 관리
- DB 연결/세션 구성
- `backend/app/repositories/vehicle_repository.py`
- Repository 및 실제 DB 통합 테스트
- 스키마 적용, 백업, 네트워크 접근 정보 공유

### dy: DB 이외 백엔드 담당

- 주차 Pydantic Schema와 API 계약
- 이미지 파일 검증 및 번호판 OCR/Vision 서비스
- 공용 `vehicle_lookup` Tool과 안전 실행기 연동
- 결정적 출입 승인 정책
- 고정 Workflow orchestration
- 주차 출입 AI Agent orchestration 및 Mock Agent
- FastAPI Router와 앱 등록
- OCR·이미지·Agent 관련 환경 설정
- 단위 테스트, API 테스트, 전체 회귀 테스트

### 소유권 원칙

- yj만 DB 컨테이너, SQL, seed, Repository 구현을 수정한다.
- dy는 Repository의 공개 인터페이스만 사용하며 SQL을 직접 실행하지 않는다.
- `main.py`, `core/config.py`, `tools/registry.py` 같은 공통 파일은 dy가 주차 기능에 필요한 최소 범위만 수정한다.
- Repository 계약이나 DB Schema 변경은 코드 수정 전에 두 사람이 합의한다.

## 3. 추가 파일 구조와 소유자

```text
agent_0821/
├─ docker-compose.yml                              # yj
├─ .env.example                                    # 공동 합의, 담당자 1명만 수정
├─ backend/
│  ├─ db/
│  │  ├─ init.sql                                  # yj
│  │  └─ seed.sql                                  # yj
│  ├─ app/
│  │  ├─ main.py                                   # dy
│  │  ├─ core/config.py                            # dy, DB 항목은 yj와 합의
│  │  ├─ routers/parking_router.py                 # dy
│  │  ├─ schemas/parking.py                        # dy
│  │  ├─ services/plate_recognition_service.py     # dy
│  │  ├─ services/parking_workflow_service.py      # dy
│  │  ├─ services/entry_policy_service.py          # dy
│  │  ├─ agents/parking_entry_agent.py             # dy
│  │  ├─ repositories/vehicle_repository.py        # yj
│  │  ├─ tools/vehicle_lookup.py                   # dy
│  │  └─ tools/registry.py                         # dy, Tool 1개만 등록
│  └─ tests/
│     ├─ test_vehicle_repository.py                # yj
│     ├─ test_plate_recognition_service.py         # dy
│     ├─ test_entry_policy_service.py              # dy
│     ├─ test_vehicle_lookup.py                    # dy
│     ├─ test_parking_workflow_api.py               # dy
│     └─ test_parking_agent_api.py                  # dy
```

`learning_unit`, `starter`, `solution`은 참고 자료이며 애플리케이션 구현 파일로 복제하지 않는다.

## 4. 프론트엔드 연동 계약

### Endpoint와 요청

```text
POST /api/parking/workflow/entry
POST /api/parking/agent/entry
Content-Type: multipart/form-data
```

| 필드 | 타입 | 규칙 |
|---|---|---|
| `image` | file | 필수 번호판 이미지 |
| `source` | string | Workflow는 `workflow`, Agent는 `agent` |

개발·테스트 환경에서는 카메라가 없을 때 테스트 이미지 업로드를 허용한다. 명시적 번호판 입력을 지원할 경우 production에서 비활성화되는 설정 플래그와 별도 필드를 사용하고 Trace에 입력 출처를 표시한다.

### 공통 응답

```json
{
  "system_type": "workflow",
  "request_id": "uuid",
  "recognized_plate_number": "12가3456",
  "recognition_confidence": 0.98,
  "approved": true,
  "gate_command": "open",
  "reason": "등록된 활성 차량입니다.",
  "tool_result": {},
  "trace": []
}
```

- `system_type`: `workflow | agent`
- `gate_command`: `open | keep_closed`
- OCR 실패 또는 저신뢰도는 `approved=false`, `gate_command=keep_closed`이며 재촬영 사유를 반환한다.
- 프론트엔드가 단계별 화면을 만들 수 있도록 Workflow Trace는 고정 순서를 유지한다.
- Agent Trace에는 Agent 판단, Tool Call, Tool Result, 정책 결과를 구분해 담는다.
- 내부 예외, SQL, 접속 문자열, Stack Trace는 응답에 포함하지 않는다.

## 5. DB 및 Repository 계약

### 차량 데이터

`vehicles` 최소 필드:

```text
vehicle_id
plate_number
owner_label
access_status: active | inactive
access_expires_at: timezone-aware datetime | null
```

- `plate_number`는 exact match와 unique index를 사용한다.
- 승인 판단에는 pgvector를 사용하지 않는다.
- seed에는 실제 번호판이나 개인정보를 넣지 않는다.

초기 테스트 차량:

| 번호판 | 상태 | 만료 | 예상 결과 |
|---|---|---|---|
| `12가3456` | active | 없음 | 승인 |
| `34나5678` | inactive | 없음 | 거절 |
| `56다7890` | active | 과거 | 거절 |

### Repository 공개 인터페이스

```python
get_vehicle_by_plate(plate_number: str) -> VehicleRecord | None
```

- 입력은 dy가 정규화한 번호판이다.
- 미등록은 예외가 아니라 `None`을 반환한다.
- 연결·쿼리 실패는 별도 Repository 예외로 전달한다.
- Repository는 OCR, 승인 판단, Tool 응답 조립을 수행하지 않는다.
- 동기/비동기 방식, 세션 수명, 예외 타입은 구현 전 확정한다.

### 공용 PostgreSQL 운영

```env
DATABASE_URL=postgresql+psycopg://<user>:<password>@<yj-db-host>:5432/<database>
```

- yj만 공용 DB 생성, 초기화, seed, 백업을 수행한다.
- dy와 다른 팀원은 별도 컨테이너를 만들지 않고 yj 호스트 주소를 사용한다.
- `localhost`를 다른 팀원의 DB 주소로 사용하지 않는다.
- `.env`는 커밋하지 않고 `.env.example`에는 변수 형식만 기록한다.
- DB 연결 또는 조회 실패 시 출입을 승인하지 않는다.

## 6. 공용 `vehicle_lookup` Tool

### 책임

정규화된 번호판으로 Repository를 한 번 호출해 등록·활성·만료 정보를 읽기 전용으로 반환한다.

입력:

```json
{"plate_number": "12가3456"}
```

등록 차량 결과:

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

미등록 결과:

```json
{
  "found": false,
  "plate_number": "12가3456",
  "access_status": "not_registered"
}
```

### 제한

- Pydantic으로 입력을 검증하고 공백 제거 등 번호판을 정규화한다.
- OCR, 승인 판단, 차단기 명령, DB 쓰기를 수행하지 않는다.
- `backend/app/tools/registry.py` Allowlist에 `vehicle_lookup`만 추가한다.
- 기존 `execute_tool_safely()`를 재사용한다.
- Tool/Repository 오류는 최종 API에서 안전한 거절 사유로 일반화한다.

## 7. dy 구현 계획

### 7.1 Schema와 설정

- 번호판 입력, OCR 후보, Tool 입출력, 정책 결과, API 응답 모델을 분리한다.
- 상태값과 명령은 Enum 또는 `Literal`로 제한한다.
- confidence는 `0.0~1.0` 범위로 검증한다.
- `MAX_IMAGE_SIZE_MB`, 허용 MIME, OCR 기준 신뢰도, Vision Provider, Mock 사용 설정을 추가한다.

### 7.2 이미지 검증과 OCR

`plate_recognition_service` 처리 순서:

1. 빈 파일 검사
2. 파일 크기 제한
3. MIME allowlist 검사
4. 선언 MIME과 실제 파일 시그니처 일치 검사
5. 손상 이미지 검사
6. OCR 후보와 confidence 추출
7. 번호판 정규화 및 형식 검증

원본 이미지는 장기 저장하거나 로그에 남기지 않는다. OCR 문자열을 임의로 추측·보정하지 않는다. API 키가 없는 환경에서는 Mock OCR로 Happy Case를 재현한다.

### 7.3 결정적 출입 정책

`entry_policy_service.evaluate()`는 LLM과 분리된 순수 함수로 구현한다.

| 조건 | approved | gate_command |
|---|---:|---|
| 등록 + active + 미만료 | true | open |
| 미등록 | false | keep_closed |
| inactive | false | keep_closed |
| 만료 | false | keep_closed |
| OCR/Tool/DB 오류 | false | keep_closed |

- `access_expires_at == now`도 만료로 처리한다.
- timezone 기준은 yj Repository 계약과 통일한다.
- Agent가 만든 승인 의견은 정책 입력으로 신뢰하지 않는다.

### 7.4 고정 Workflow

```text
이미지 검증
→ OCR
→ 신뢰도 판정
→ vehicle_lookup 안전 실행
→ 결정적 정책 평가
→ 응답 및 고정 4단계 Trace 생성
```

- OCR 결과 없음/저신뢰도이면 Tool 호출 없이 재촬영을 요청한다.
- 정상 OCR이면 Tool을 정확히 한 번 호출한다.
- 요청마다 UUID를 생성한다.
- DB 또는 Tool 실패 시 fail-closed 응답을 반환한다.

### 7.5 AI Agent

Agent는 OCR 후보·confidence·Tool Schema를 보고 다음 중 하나만 선택한다.

1. 명확한 번호판이면 `vehicle_lookup` 호출 요청
2. 불명확하면 재촬영 요청

안전 규칙:

- 허용 Tool은 `vehicle_lookup` 하나다.
- Tool 호출은 최대 한 번이다.
- Agent는 번호판을 추측하거나 수정하지 않는다.
- Agent는 DB/Repository에 직접 접근하지 않는다.
- Agent는 차단기를 제어하지 않는다.
- 최종 `approved`와 `gate_command`는 정책 서비스만 결정한다.
- API 키가 없으면 동일 규칙의 Mock Agent를 사용한다.

기존 Agent Runtime을 검토하되 주차 전용 규칙을 공통 Runtime에 넣지 않는다. 필요한 orchestration은 `parking_entry_agent.py` 안에 격리한다.

### 7.6 Router와 이벤트

- Router는 두 Endpoint의 multipart 요청을 검증하고 서비스 결과를 반환한다.
- `source`와 Endpoint가 일치하지 않으면 검증 오류로 처리한다.
- OpenAPI에서 요청 필드와 공통 응답 Schema를 확인한다.
- `entry_events` 기록은 yj가 쓰기 Repository 계약을 제공하고 실패 정책을 합의한 뒤 연결한다.
- 이벤트 저장 실패가 이미 계산된 승인 결과를 바꿀지는 구현 전에 명시적으로 결정한다.

## 8. yj 구현 계획

1. Docker Compose로 PostgreSQL(pgvector)을 구성한다.
2. pgvector 확장과 `vehicles`, `entry_events` Schema를 작성한다.
3. 번호판 unique index와 필요한 상태/시간 제약을 적용한다.
4. 세 개의 임의 차량을 중복 없이 넣는 seed를 작성한다.
5. DB 연결/세션과 Repository 조회를 구현한다.
6. exact match, 미등록, 연결 실패, timezone을 테스트한다.
7. 공용 DB 접속 방법과 적용된 Schema 버전을 dy에게 공유한다.
8. 필요 시 이벤트 기록 Repository 계약을 별도로 제안한다.

pgvector는 활성화만 하고 1차 승인 로직에서는 사용하지 않는다.

## 9. 테스트 계획

### dy 단위 테스트

- 이미지 크기, MIME, 시그니처, 빈/손상 파일
- OCR 없음과 confidence 경계값
- 번호판 정규화 및 잘못된 형식
- active, inactive, expired, not registered 정책
- 만료 경계 시각과 timezone
- Tool 입력 검증, Repository 결과 변환, Repository 예외

### dy API 테스트

- Workflow active 차량 승인
- 미등록·비활성·만료 차량 거절
- OCR 실패/저신뢰도에서 Tool 0회
- 정상 Workflow에서 Tool 정확히 1회
- Agent 명확한 번호판에서 Tool 최대 1회
- Agent 재촬영 판단에서 Tool 0회
- 미허용 Tool 차단
- DB/Tool 오류에서 `keep_closed`
- 요청 ID와 요구된 Trace 포함
- 내부 예외와 비밀정보 미노출
- 외부 API 키·DB 없이 Mock Happy Case 실행

### yj DB 테스트

- Schema 및 seed 중복 실행 안전성
- 번호판 unique 제약과 exact match
- 세 seed 차량 조회
- 미등록 시 `None`
- 연결/쿼리 실패 시 정의된 예외
- timezone-aware 만료 값

### 통합 및 회귀 테스트

- yj 공용 DB에서 active, inactive, expired, not registered, DB failure를 확인한다.
- 두 Endpoint가 동일한 Tool과 정책 결과를 사용하는지 비교한다.
- 기존 메뉴·학습·Tool 테스트를 포함한 전체 `backend/tests`를 실행한다.

```powershell
pytest backend/tests/test_vehicle_repository.py
pytest backend/tests/test_plate_recognition_service.py
pytest backend/tests/test_entry_policy_service.py
pytest backend/tests/test_vehicle_lookup.py
pytest backend/tests/test_parking_workflow_api.py
pytest backend/tests/test_parking_agent_api.py
pytest backend/tests
```

## 10. 개발 및 병합 순서

1. 두 사람이 Repository 함수, 반환 모델, 예외 타입, timezone을 확정한다.
2. yj가 DB Schema·seed·Repository를 구현한다.
3. dy는 Fake Repository로 Schema·OCR·정책·Tool을 병렬 구현한다.
4. dy가 Workflow API를 구현하고 Mock 테스트를 통과시킨다.
5. dy가 동일 Tool/정책을 사용하는 Agent API를 구현한다.
6. yj DB와 `vehicle_lookup`을 연결해 핵심 상태를 통합 테스트한다.
7. 프론트엔드 담당자에게 Endpoint, `image`, `source`, 응답 예시를 공유한다.
8. 프론트엔드 두 페이지와 End-to-End Happy Case를 확인한다.
9. 전체 회귀 테스트 후 공통 파일 충돌을 정리한다.

권장 커밋:

```text
yj: feat(parking-db): add postgres schema and seed
yj: feat(parking-db): add vehicle repository
dy: feat(parking): add schemas, image validation, and OCR
dy: feat(parking): add entry policy and vehicle lookup tool
dy: feat(parking): add workflow entry API
dy: feat(parking): add agent entry API
test(parking): add integration and failure-path coverage
```

## 11. 협업 체크리스트

### yj가 dy에게 공유

- [ ] Repository 함수와 반환 모델
- [ ] DB 예외 타입
- [ ] timezone 기준
- [ ] 공용 DB 주소와 개발 계정 사용법
- [ ] Schema/seed 적용 완료 시점과 버전

### dy가 yj 및 프론트엔드에 공유

- [ ] 번호판 정규화 규칙
- [ ] Tool 입출력 Schema
- [ ] 정책 상태값과 사용자용 사유
- [ ] 두 Endpoint 요청·응답 예시
- [ ] `image` 및 `source` Form 계약
- [ ] Mock 및 실제 DB 테스트 결과

## 12. 완료 기준

- [ ] Workflow와 Agent Endpoint가 각각 동작한다.
- [ ] 두 방식이 하나의 `vehicle_lookup` 구현을 공용으로 사용한다.
- [ ] 카메라 이미지 → OCR → PostgreSQL 조회 → 정책 결과 흐름이 동작한다.
- [ ] 등록·활성·미만료 차량만 승인된다.
- [ ] OCR 실패/저신뢰도는 Tool 호출 없이 재촬영을 요청한다.
- [ ] Agent는 Tool을 직접 실행하거나 DB에 접근하지 않는다.
- [ ] Agent Tool 호출은 Allowlist와 Pydantic 검증을 거치며 최대 한 번이다.
- [ ] 최종 승인과 차단기 명령은 결정적 Backend 정책만 정한다.
- [ ] DB/OCR/Tool 장애는 모두 fail-closed로 처리된다.
- [ ] 이미지 원본, 개인정보, DB 인증 정보, 내부 예외가 노출되지 않는다.
- [ ] Mock 환경에서 외부 API 키와 DB 없이 테스트가 통과한다.
- [ ] yj 공용 DB 통합 테스트와 전체 백엔드 회귀 테스트가 통과한다.
- [ ] 프론트엔드 두 페이지에서 승인·거절·재촬영·Trace가 정상 표시된다.
