# 주차장 출입 시스템 프론트엔드 작업 계획

## 1. 목적

주차 출입 기능은 Workflow와 AI Agent를 별도 Streamlit 페이지로 제공한다. 두 페이지는 같은 카메라 입력 UX와 공통 Backend 응답 계약을 쓰지만, 화면 파일과 API 클라이언트 파일의 소유자를 분리해 Git 병합 충돌을 방지한다.

## 2. 담당 분리

| 담당 | 전용 파일 | 책임 |
|---|---|---|
| Frontend A | `frontend/app_pages/03_parking_workflow.py` | 카메라 촬영, 고정 Workflow 요청, 1~4단계 Trace, 승인/거절 UI |
| Frontend A | `frontend/clients/parking_workflow_client.py` | `POST /api/parking/workflow/entry` 이미지 업로드 |
| Frontend A (통합 담당) | `frontend/app.py` | 주차 페이지 두 개를 `st.navigation`에 한 번만 등록 |
| Frontend B | `frontend/app_pages/04_parking_agent.py` | 카메라 촬영, Agent 요청, Agent 판단·Tool Trace, 승인/거절 UI |
| Frontend B | `frontend/clients/parking_agent_client.py` | `POST /api/parking/agent/entry` 이미지 업로드 |

기존 `frontend/core/api_client.py`는 수정하지 않고 재사용한다. 공통 컴포넌트 파일을 새로 만들지 않으며, 작은 결과 표시 함수는 각 페이지 파일 내부에 둔다. 따라서 A와 B가 같은 파일을 동시에 수정할 필요가 없다.

## 3. 병합 순서와 규칙

1. A는 Workflow 전용 파일 두 개만 작업해 첫 PR을 만든다.
2. B는 최신 기본 브랜치에서 Agent 전용 파일 두 개만 작업해 별도 PR을 만든다.
3. B는 `frontend/app.py`를 수정하지 않는다.
4. A는 B의 PR 병합 후 마지막에 `frontend/app.py`에 두 페이지를 함께 등록한다.
5. Backend API 계약 변경은 `parking_master.md`와 팀 채널에서 먼저 합의한다. 프론트 담당자는 Backend 파일을 수정하지 않는다.

## 4. 공통 Backend 응답 계약

두 페이지는 다음 필드를 표시한다.

```json
{
  "system_type": "workflow | agent",
  "recognized_plate_number": "12가3456",
  "recognition_confidence": 0.98,
  "approved": true,
  "gate_command": "open | keep_closed",
  "reason": "등록된 활성 차량입니다.",
  "tool_result": {},
  "trace": []
}
```

업로드 필드 이름은 `image`, 추가 Form 데이터는 `source=workflow` 또는 `source=agent`로 고정한다. Backend 확정 전까지는 화면이 예상 API 경로와 계약을 기준으로 동작한다.

## 5. 공통 UI 정책

- `st.camera_input("번호판 이미지를 촬영하세요")`로 카메라를 연다.
- 촬영된 이미지는 요청 전 화면에 미리 표시한다.
- 분석 버튼을 누르면 Spinner를 표시하고 중복 클릭을 막는다.
- 번호판, OCR 신뢰도, Backend 판단 사유를 결과 카드에 표시한다.
- `approved=true`일 때 반드시 `st.success("출입이 승인되었습니다.")`를 표시한다.
- `approved=false`일 때 반드시 `st.error("출입이 승인되지 않았습니다. 차량 등록 또는 출입 권한을 확인해 주세요.")`를 표시한다.
- `trace`는 기본 화면을 복잡하게 하지 않도록 Expander 안에 JSON으로 보여 준다.
- 네트워크·Backend 오류는 `BackendAPIError`로 처리하고 재촬영/재시도 안내를 표시한다.

## 6. 페이지별 차이

### Workflow 페이지

- 제목: `🚗 주차 출입 Workflow`
- 고정 단계: 이미지 캡처 → 번호판 인식 → 차량 DB 조회 → Backend 출입 정책
- Trace는 단계 번호와 결과를 순서대로 표시한다.

### AI Agent 페이지

- 제목: `🤖 주차 출입 AI Agent`
- Agent가 OCR 후보를 바탕으로 Tool 호출 또는 재촬영을 결정한다는 안내를 표시한다.
- Trace에 Agent 판단, `vehicle_lookup` Tool 실행 결과, Backend 정책 결과를 표시한다.
- Agent가 최종 승인 권한을 갖지 않고 Backend 정책이 결정한다는 안내를 상시 표시한다.

## 7. 완료 기준

- 두 페이지가 독립적으로 접근·요청·결과 표시된다.
- 승인 응답은 초록 성공 문구, 거절 응답은 빨간 경고 문구를 표시한다.
- Workflow와 Agent 페이지 모두 카메라 촬영 이미지와 예상 API 경로를 사용한다.
- A와 B가 동시에 수정하는 파일은 없으며, A만 최종 내비게이션 통합을 수행한다.
