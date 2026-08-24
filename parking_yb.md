# 주차 출입 시스템 · yb 프론트엔드 담당

## 담당 범위

yb는 주차 출입 시스템의 **Frontend A**를 담당한다. 고정된 Backend Workflow를 호출하는 화면과 최종 내비게이션 통합을 맡는다.

### 담당 파일

```text
frontend/
├─ app.py                                  # 주차 페이지 내비게이션 등록·통합
├─ app_pages/
│  └─ 03_parking_workflow.py               # Workflow 출입 화면
└─ clients/
   └─ parking_workflow_client.py           # Workflow API 호출
```

## 구현한 화면

`03_parking_workflow.py`는 다음 고정 순서를 사용자에게 보여 준다.

```text
카메라로 번호판 촬영
→ POST /api/parking/workflow/entry 요청
→ 번호판 인식 결과·DB 조회·Backend 정책 결과 표시
```

- `st.camera_input`으로 번호판 사진을 촬영한다.
- 촬영 이미지를 미리 표시한다.
- 요청 중 Spinner를 표시한다.
- 번호판, OCR 신뢰도, 차단기 명령, 판단 사유를 표시한다.
- `approved=true`이면 `출입이 승인되었습니다.` 성공 문구를 표시한다.
- `approved=false`이면 차량 등록 또는 출입 권한 확인을 안내하는 오류 문구를 표시한다.
- Workflow Trace는 Expander에서 확인할 수 있다.

## API 계약

```text
POST /api/parking/workflow/entry
Content-Type: multipart/form-data
```

| 필드 | 값 |
|---|---|
| `image` | 카메라에서 촬영한 이미지 파일 |
| `source` | `workflow` |

응답에서 사용하는 필드:

```json
{
  "recognized_plate_number": "12가3456",
  "recognition_confidence": 0.98,
  "approved": true,
  "gate_command": "open",
  "reason": "등록된 활성 차량입니다.",
  "trace": []
}
```

## 병합 규칙

- yb만 `frontend/app.py`를 수정해 주차 페이지를 등록한다.
- AI Agent 화면인 `04_parking_agent.py`와 `parking_agent_client.py`는 다른 프론트 담당자의 전용 파일이므로 수정하지 않는다.
- `frontend/core/api_client.py`는 공통 파일이므로 수정하지 않고 기존 `upload()` 함수를 재사용한다.
- Backend API 계약이 바뀌면 `parking_master.md`, `parking_frontend.md`와 먼저 맞춘 뒤 프론트 코드를 수정한다.

## 완료 상태

- [x] Workflow 카메라 UI
- [x] Workflow 전용 API 클라이언트
- [x] 주차 Workflow 페이지 내비게이션 등록
- [x] 승인·거절 결과 UI
- [x] 프론트 문법 검사
- [ ] Backend Workflow API 연동 확인
- [ ] 실제 카메라 브라우저 권한 및 End-to-End 테스트
