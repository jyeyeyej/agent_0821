# DY 주차 출입 시스템 백엔드 단계별 개발 계획서

## 1. 담당 목표

dy는 주차 출입 시스템의 **DB 인프라·SQL·Repository 구현을 제외한 백엔드 전체**를 담당한다.

최종 결과는 다음 두 API가 하나의 읽기 전용 `vehicle_lookup` Tool과 하나의 결정적 출입 정책을 공용으로 사용하는 것이다.

```text
POST /api/parking/workflow/entry
POST /api/parking/agent/entry
```

- Workflow는 이미지 검증 → OCR → Tool → 정책 순서를 고정한다.
- Agent는 OCR 결과에 따라 Tool 호출 또는 재촬영만 선택한다.
- 실제 차단기는 제어하지 않고 `gate_command: open | keep_closed`만 반환한다.
- OCR, Tool, DB 장애는 모두 `keep_closed`로 처리한다.

## 2. 작업 범위

### dy가 생성·수정할 파일

```text
backend/app/
├─ main.py
├─ core/config.py
├─ routers/parking_router.py
├─ schemas/parking.py
├─ services/plate_recognition_service.py
├─ services/entry_policy_service.py
├─ services/parking_workflow_service.py
├─ agents/parking_entry_agent.py
├─ tools/vehicle_lookup.py
└─ tools/registry.py

backend/tests/
├─ test_plate_recognition_service.py
├─ test_entry_policy_service.py
├─ test_vehicle_lookup.py
├─ test_parking_workflow_api.py
└─ test_parking_agent_api.py
```

### dy가 수정하지 않을 yj 소유 파일

```text
docker-compose.yml
backend/db/init.sql
backend/db/seed.sql
backend/app/repositories/vehicle_repository.py
backend/tests/test_vehicle_repository.py
```

dy는 SQL을 직접 작성하거나 실행하지 않으며 별도 PostgreSQL 컨테이너를 만들지 않는다.

## 3. 고정 API 계약

요청 형식:

```text
Content-Type: multipart/form-data
image=<번호판 이미지>
source=workflow | agent
```

공통 응답:

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

프론트엔드가 기대하는 필드 이름을 임의로 변경하지 않는다. 선택 필드가 필요하면 기존 공통 필드는 유지한 채 추가한다.

## 4. 단계 0: 기존 구조 및 협업 계약 확인

### 목적

기존 Tool/Agent 동작을 깨뜨리지 않고 yj Repository와 연결할 경계를 먼저 고정한다.

### 확인할 파일

```text
backend/app/main.py
backend/app/core/config.py
backend/app/tools/registry.py
backend/app/tools/executor.py
backend/app/agents/runtime.py
backend/app/providers/mock.py
backend/app/routers/menu_recommendation_router.py
backend/app/services/menu_recommendation_service.py
```

### yj와 확정할 항목

```python
get_vehicle_by_plate(plate_number: str) -> VehicleRecord | None
```

- 함수가 동기인지 비동기인지
- `VehicleRecord`의 실제 타입과 필드 접근 방식
- 미등록 차량이 `None`인지
- DB 연결/쿼리 실패 예외 타입
- `access_expires_at` timezone 기준
- Repository 객체 생성 또는 의존성 주입 방식

### 완료 조건

- [ ] Repository 호출 예시를 문서 또는 팀 채널에 남겼다.
- [ ] dy 테스트에서 사용할 Fake Repository 형태를 정했다.
- [ ] yj 파일을 수정하지 않고 병렬 개발할 수 있다.

## 5. 단계 1: 주차 Schema와 환경 설정

### 대상 파일

```text
backend/app/schemas/parking.py
backend/app/core/config.py
```

### 구현 항목

1. `SystemType`: `workflow | agent`
2. `GateCommand`: `open | keep_closed`
3. `AccessStatus`: `active | inactive | not_registered`
4. 번호판 Tool 입력 모델
5. OCR 후보/결과 모델
6. 차량 조회 Tool 결과 모델
7. 출입 정책 결과 모델
8. Trace 항목 모델
9. 공통 API 응답 모델

번호판 정규화는 최소한 다음 규칙을 적용한다.

- 앞뒤 공백 제거
- 내부 공백 제거
- 허용된 한글·영문·숫자 외 문자 거절
- 허용 길이 검증
- 빈 값 거절

OCR confidence는 `0.0~1.0` 범위로 제한한다.

설정 후보:

```text
MAX_IMAGE_SIZE_MB
PARKING_ALLOWED_IMAGE_MIME_TYPES
PARKING_OCR_CONFIDENCE_THRESHOLD
PARKING_OCR_MODE=mock | vision
PARKING_ALLOW_MANUAL_PLATE_INPUT
```

`.env.example`은 yj와 수정 담당을 정한 경우에만 반영한다.

### 검증

- 정상 번호판이 정규화된다.
- 빈 값, 특수문자, 잘못된 confidence가 Pydantic 검증에서 거절된다.
- Enum 외 상태와 차단기 명령을 만들 수 없다.

### 완료 조건

- [ ] 이후 서비스가 dict 대신 주차 Schema를 사용할 수 있다.
- [ ] 설정 기본값만으로 Mock 모드가 실행된다.

### 권장 커밋

```text
feat(parking): add parking schemas and configuration
```

## 6. 단계 2: 이미지 검증 및 번호판 OCR 서비스

### 대상 파일

```text
backend/app/services/plate_recognition_service.py
backend/tests/test_plate_recognition_service.py
```

### 처리 순서

```text
빈 파일 검사
→ 크기 제한 검사
→ MIME allowlist 검사
→ 실제 파일 시그니처 검사
→ 손상 이미지 검사
→ OCR 실행
→ 번호판 정규화
→ 후보와 confidence 반환
```

### 구현 원칙

- `image/jpeg`, `image/png` 등 명시된 형식만 허용한다.
- 선언 MIME만 신뢰하지 않고 실제 시그니처도 확인한다.
- 전체 이미지를 로그에 남기거나 디스크에 장기 저장하지 않는다.
- OCR 결과가 없으면 정상적인 재촬영 케이스로 구분한다.
- 번호판 문자를 임의로 추측하거나 보정하지 않는다.
- Vision API 키가 없어도 Mock OCR로 테스트가 가능해야 한다.
- OCR Provider 예외는 안전한 도메인 오류로 변환한다.

### 테스트 케이스

- 정상 JPEG/PNG
- 빈 파일
- 제한 크기 초과
- 허용되지 않은 MIME
- MIME과 시그니처 불일치
- 손상 이미지
- OCR 후보 없음
- confidence 기준 미만·동일·초과
- Mock OCR Happy Case `12가3456`

### 완료 조건

- [ ] 서비스가 정규화 번호판과 confidence를 반환한다.
- [ ] 실패 결과만으로 Tool 호출 여부를 결정할 수 있다.
- [ ] 원본 이미지가 저장되지 않는다.

### 권장 커밋

```text
feat(parking): add image validation and plate recognition
```

## 7. 단계 3: 결정적 출입 정책

### 대상 파일

```text
backend/app/services/entry_policy_service.py
backend/tests/test_entry_policy_service.py
```

### 정책표

| 입력 상태 | approved | gate_command | 사유 |
|---|---:|---|---|
| 등록 + active + 미만료 | true | open | 활성 차량 |
| 미등록 | false | keep_closed | 미등록 차량 |
| inactive | false | keep_closed | 비활성 차량 |
| 만료 | false | keep_closed | 출입 권한 만료 |
| OCR/Tool/DB 오류 | false | keep_closed | 조회 또는 처리 실패 |

### 구현 원칙

- LLM을 호출하지 않는 순수 함수로 구현한다.
- `access_expires_at == now`는 만료로 처리한다.
- timezone-aware datetime만 비교하거나 명확한 변환 규칙을 둔다.
- Agent가 `approved=true`를 생성해도 정책 결과에 반영하지 않는다.
- 사용자용 사유와 내부 오류 로그를 분리한다.

### 테스트 케이스

- active + 만료 없음
- active + 미래 만료
- inactive
- 과거 만료
- 현재 시각과 동일한 만료
- 미등록
- Tool 실패
- timezone 경계

### 완료 조건

- [ ] 승인 가능한 유일한 조건이 등록·active·미만료다.
- [ ] 모든 오류 경로가 fail-closed다.

### 권장 커밋

```text
feat(parking): add deterministic entry policy
```

## 8. 단계 4: 공용 `vehicle_lookup` Tool

### 대상 파일

```text
backend/app/tools/vehicle_lookup.py
backend/app/tools/registry.py
backend/tests/test_vehicle_lookup.py
```

### Tool 계약

입력:

```json
{"plate_number": "12가3456"}
```

등록 차량:

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

미등록 차량:

```json
{
  "found": false,
  "plate_number": "12가3456",
  "access_status": "not_registered"
}
```

### 구현 순서

1. Pydantic으로 Tool arguments를 검증한다.
2. 번호판을 정규화한다.
3. yj Repository를 정확히 한 번 호출한다.
4. `VehicleRecord | None`을 Tool 결과 Schema로 변환한다.
5. `tools/registry.py`에 `vehicle_lookup`을 등록한다.
6. 기존 `execute_tool_safely()`를 통해서만 호출되는지 확인한다.

### 병렬 개발 방식

yj Repository가 준비되지 않았으면 테스트에서 Fake 또는 Monkeypatch를 사용한다. 임시 SQL이나 임시 Repository 구현을 애플리케이션 코드에 추가하지 않는다.

### 테스트 케이스

- 등록 차량 결과 변환
- 미등록 차량을 성공적인 업무 결과로 반환
- 잘못된 번호판 arguments 검증 실패
- Repository가 정확히 한 번 호출됨
- Repository 오류가 안전 실행기 실패로 변환됨
- 미허용 Tool 이름 차단
- 기존 Registry Tool 목록 회귀 확인

### 완료 조건

- [ ] Workflow와 Agent가 동일 Tool 이름과 구현을 재사용할 수 있다.
- [ ] Tool은 승인 판단과 DB 쓰기를 하지 않는다.

### 권장 커밋

```text
feat(parking): add shared vehicle lookup tool
```

## 9. 단계 5: 고정 Workflow 서비스

### 대상 파일

```text
backend/app/services/parking_workflow_service.py
backend/tests/test_parking_workflow_api.py
```

### 고정 실행 순서

```text
1. 이미지 캡처/검증
2. 번호판 인식
3. 차량 DB 조회 Tool
4. Backend 출입 정책
```

### 구현 항목

- 요청 UUID 생성
- 이미지 검증 및 OCR 호출
- confidence 기준 판정
- 저신뢰도/번호판 없음에서 재촬영 응답
- `execute_tool_safely("vehicle_lookup", ...)` 호출
- Tool 결과를 정책 서비스에 전달
- 공통 응답과 고정 순서 Trace 생성

### Trace 원칙

- 단계 이름과 순서가 항상 동일해야 한다.
- 원본 이미지, DB URL, 내부 예외를 넣지 않는다.
- OCR 실패 시 DB 조회 단계는 `skipped`로 표시할 수 있다.
- Tool 실패는 안전한 요약만 남긴다.

### 테스트 케이스

- active 차량 승인 및 `open`
- 미등록·inactive·expired 거절
- OCR 없음/저신뢰도에서 Tool 0회
- 정상 OCR에서 Tool 정확히 1회
- Tool/DB 실패 시 `keep_closed`
- Trace 고정 순서
- request ID 형식
- 내부 오류 미노출

### 완료 조건

- [ ] Mock 환경에서 Workflow Happy Case가 통과한다.
- [ ] 모든 실패 경로가 승인되지 않는다.

### 권장 커밋

```text
feat(parking): add fixed parking workflow service
```

## 10. 단계 6: 주차 출입 AI Agent

### 대상 파일

```text
backend/app/agents/parking_entry_agent.py
backend/tests/test_parking_agent_api.py
```

### Agent가 할 수 있는 결정

```text
명확한 OCR 후보 → vehicle_lookup 호출 요청
불명확한 후보     → 재촬영 요청
```

### 안전 제한

- 허용 Tool은 `vehicle_lookup` 하나다.
- 요청당 Tool 호출은 최대 한 번이다.
- 번호판을 추측·수정하지 않는다.
- DB/Repository에 직접 접근하지 않는다.
- 차단기 명령과 승인 여부를 결정하지 않는다.
- Tool 결과 이후 `entry_policy_service`가 최종 결과를 만든다.
- Provider/API 키가 없으면 같은 제한을 적용한 Mock Agent를 사용한다.

### 구현 순서

1. OCR 후보와 confidence를 Agent 입력으로 구성한다.
2. 허용 Tool Schema 하나만 제공한다.
3. Agent 결정을 Pydantic으로 검증한다.
4. 재촬영 결정이면 Tool을 호출하지 않는다.
5. Tool 결정이면 안전 실행기로 최대 한 번 호출한다.
6. Tool 결과는 결정적 정책으로 평가한다.
7. Agent 판단 → Tool Call → Tool Result → 정책 결과 Trace를 만든다.

기존 `agents/runtime.py`가 요구사항과 맞으면 재사용하고, 맞지 않으면 주차 전용 orchestration을 신규 파일에 둔다. 주차 규칙을 공통 Runtime에 추가하지 않는다.

### 테스트 케이스

- 명확한 번호판에서 Tool 1회
- 저신뢰도에서 재촬영 및 Tool 0회
- Agent가 미허용 Tool을 선택하면 차단
- Agent가 arguments를 변조하면 검증 실패
- Agent가 승인 의견을 내도 정책이 최종 결과를 덮어씀
- 미등록·inactive·expired 거절
- Tool/DB/Provider 오류에서 `keep_closed`
- Mock Agent Happy Case
- 호출 횟수 최대 1회

### 완료 조건

- [ ] Agent와 Workflow가 동일 Tool과 정책을 사용한다.
- [ ] Agent는 승인 권한이나 직접 DB 접근 권한이 없다.

### 권장 커밋

```text
feat(parking): add parking entry agent
```

## 11. 단계 7: FastAPI Router와 앱 등록

### 대상 파일

```text
backend/app/routers/parking_router.py
backend/app/routers/__init__.py       # 프로젝트 패턴상 필요한 경우만
backend/app/main.py
```

### 구현 항목

- `POST /api/parking/workflow/entry`
- `POST /api/parking/agent/entry`
- multipart의 `image`와 `source` 수신
- Endpoint와 `source` 불일치 검증
- 서비스 결과를 공통 응답 Schema로 반환
- Router를 `main.py`에 한 번 등록
- OpenAPI tag와 설명 추가

### 오류 처리 원칙

- 잘못된 파일/요청은 일관된 4xx 응답을 사용한다.
- OCR 실패/저신뢰도처럼 예상된 업무 결과는 재촬영 가능한 응답으로 반환한다.
- DB/Tool 내부 오류는 사용자용 안전 메시지와 `keep_closed`로 변환한다.
- Stack Trace와 원본 예외 문자열을 응답에 넣지 않는다.

### 검증

- OpenAPI에서 `image`, `source`, 응답 Schema 확인
- Workflow Endpoint에 `source=agent` 요청 거절
- Agent Endpoint에 `source=workflow` 요청 거절
- 기존 Router가 그대로 동작하는지 확인

### 완료 조건

- [ ] 프론트엔드 클라이언트 계약과 요청 필드가 일치한다.
- [ ] 두 Endpoint가 독립적으로 호출된다.

### 권장 커밋

```text
feat(parking): expose workflow and agent entry APIs
```

## 12. 단계 8: yj DB 통합

### 선행 조건

yj에게 다음을 전달받는다.

- Repository 구현 완료 커밋
- 함수/모델/예외 타입
- 공용 DB 주소와 개발 계정 사용법
- Schema 및 seed 적용 완료 상태
- timezone 기준

### 통합 작업

1. Fake Repository를 실제 yj Repository로 교체한다.
2. Tool의 import와 호출 방식만 계약에 맞춘다.
3. SQL이나 yj Repository 내부 구현은 수정하지 않는다.
4. 공용 DB의 seed 차량으로 조회와 정책을 확인한다.
5. DB 연결을 끊은 상태에서 fail-closed를 확인한다.

### 통합 케이스

| 번호판/상태 | 예상 결과 |
|---|---|
| `12가3456`, active, 미만료 | 승인/open |
| `34나5678`, inactive | 거절/keep_closed |
| `56다7890`, expired | 거절/keep_closed |
| 미등록 번호판 | 거절/keep_closed |
| DB 연결 실패 | 거절/keep_closed |

### 완료 조건

- [ ] 실제 DB 결과가 Tool Schema로 정상 변환된다.
- [ ] Workflow와 Agent의 정책 결과가 동일하다.
- [ ] DB 실패 상세가 API 응답에 노출되지 않는다.

### 권장 커밋

```text
test(parking): integrate vehicle repository with parking flows
```

## 13. 단계 9: 회귀 테스트와 프론트엔드 인계

### 테스트 실행

```powershell
pytest backend/tests/test_plate_recognition_service.py
pytest backend/tests/test_entry_policy_service.py
pytest backend/tests/test_vehicle_lookup.py
pytest backend/tests/test_parking_workflow_api.py
pytest backend/tests/test_parking_agent_api.py
pytest backend/tests
```

### 프론트엔드에 전달할 내용

- Endpoint 두 개
- multipart 필드 `image`, `source`
- 승인·거절·재촬영 응답 예시
- Workflow Trace 단계 이름과 순서
- Agent Trace 단계 이름
- 파일 크기/MIME 제한
- timeout 및 사용자 재시도 기준

### End-to-End 확인

- Workflow 페이지에서 승인/거절/재촬영 표시
- Agent 페이지에서 판단·Tool·정책 Trace 표시
- 같은 active 차량에 대해 두 API 모두 승인
- 미등록/비활성/만료 차량에 대해 두 API 모두 거절
- Backend 중단/DB 장애 시 프론트가 안전하게 오류 표시

### 완료 조건

- [ ] 신규 테스트와 기존 백엔드 전체 테스트가 통과한다.
- [ ] 프론트엔드 계약 불일치가 없다.
- [ ] dy 소유 범위 밖의 의도하지 않은 변경이 없다.

## 14. 작업 중 보류할 항목

다음 항목은 별도 계약이 확정되기 전에는 구현하지 않는다.

- 실제 차단기 또는 CCTV 제어
- 이미지 원본 장기 저장
- 실제 개인정보 사용
- 번호판 유사도/vector 검색
- Agent의 DB 직접 접근
- Agent의 최종 승인 결정
- 임의 DB Schema/seed 수정
- `entry_events` 쓰기 Repository 연결

`entry_events` 기록은 yj가 쓰기 인터페이스를 제공하고, 저장 실패가 승인 결과에 미치는 영향을 팀이 정한 뒤 별도 단계로 추가한다.

## 15. 전체 완료 체크리스트

### Schema·OCR

- [ ] 번호판과 confidence가 Pydantic으로 검증된다.
- [ ] 이미지 크기, MIME, 시그니처, 손상 여부를 확인한다.
- [ ] 원본 이미지를 장기 저장하거나 로그에 남기지 않는다.
- [ ] Mock OCR이 API 키 없이 동작한다.

### Tool·정책

- [ ] `vehicle_lookup`이 Registry와 안전 실행기를 통과한다.
- [ ] Repository를 한 번만 호출하며 DB 쓰기를 하지 않는다.
- [ ] 등록·active·미만료만 승인된다.
- [ ] 모든 오류는 `keep_closed`다.

### Workflow·Agent

- [ ] Workflow의 실행 및 Trace 순서가 고정되어 있다.
- [ ] OCR 실패/저신뢰도에서 Tool을 호출하지 않는다.
- [ ] Agent Tool 호출은 최대 한 번이다.
- [ ] Agent는 번호판 추측, DB 직접 접근, 승인 결정을 하지 않는다.
- [ ] 두 방식은 동일 Tool과 정책을 사용한다.

### API·통합

- [ ] 두 Endpoint가 `image`, `source`를 받는다.
- [ ] 응답이 프론트엔드 공통 계약과 일치한다.
- [ ] yj DB의 핵심 5개 케이스를 확인했다.
- [ ] 내부 예외, DB URL, 인증 정보가 노출되지 않는다.
- [ ] 전체 회귀 테스트와 End-to-End 확인을 마쳤다.

## 16. 최종 커밋 순서 요약

```text
1. feat(parking): add parking schemas and configuration
2. feat(parking): add image validation and plate recognition
3. feat(parking): add deterministic entry policy
4. feat(parking): add shared vehicle lookup tool
5. feat(parking): add fixed parking workflow service
6. feat(parking): add parking entry agent
7. feat(parking): expose workflow and agent entry APIs
8. test(parking): integrate repository and cover failure paths
```
