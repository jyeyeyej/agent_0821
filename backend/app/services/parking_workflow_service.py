"""고정 주차 Workflow와 공통 안전 응답 조립 로직입니다."""

from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.schemas.parking import (
    ParkingEntryResponse,
    ParkingTraceItem,
    PlateRecognitionResult,
    VehicleLookupResult,
)
from app.services.entry_policy_service import deny_processing_failure, evaluate_entry_policy
from app.services.plate_recognition_service import ParkingImageValidationError, extract_plate
from app.tools.executor import execute_tool_safely


WORKFLOW_STAGES = (
    "1_image_validation",
    "2_plate_recognition",
    "3_vehicle_lookup",
    "4_entry_policy",
)


def _skipped(stage: str, reason: str) -> ParkingTraceItem:
    return ParkingTraceItem(stage=stage, status="skipped", data={"reason": reason})


def _recapture_response(
    system_type: str,
    request_id,
    reason: str,
    trace: list[ParkingTraceItem],
    recognition: PlateRecognitionResult | None = None,
) -> ParkingEntryResponse:
    return ParkingEntryResponse(
        system_type=system_type,
        request_id=request_id,
        recognized_plate_number=recognition.plate_number if recognition else None,
        recognition_confidence=recognition.confidence if recognition else None,
        approved=False,
        gate_command="keep_closed",
        reason=reason,
        needs_recapture=True,
        trace=trace,
    )


def safe_tool_data(raw_result: Any) -> dict[str, Any] | None:
    if not raw_result.success or not isinstance(raw_result.data, dict):
        return None
    return raw_result.data


def run_parking_workflow(content: bytes, content_type: str) -> ParkingEntryResponse:
    request_id = uuid4()
    trace: list[ParkingTraceItem] = []
    try:
        recognition = extract_plate(content, content_type)
        trace.append(ParkingTraceItem(
            stage=WORKFLOW_STAGES[0], status="success", data={"content_type": content_type.split(";", 1)[0]},
        ))
        trace.append(ParkingTraceItem(
            stage=WORKFLOW_STAGES[1],
            status="success" if recognition.plate_number else "rejected",
            data={"plate_number": recognition.plate_number, "confidence": recognition.confidence},
        ))
    except ParkingImageValidationError as error:
        trace.append(ParkingTraceItem(stage=WORKFLOW_STAGES[0], status="rejected", data={"reason": str(error)}))
        trace.extend(_skipped(stage, "이미지 검증 실패") for stage in WORKFLOW_STAGES[1:])
        return _recapture_response("workflow", request_id, str(error), trace)
    except Exception:
        trace.append(ParkingTraceItem(stage=WORKFLOW_STAGES[0], status="error", data={"reason": "이미지를 처리하지 못했습니다."}))
        trace.extend(_skipped(stage, "이미지 처리 실패") for stage in WORKFLOW_STAGES[1:])
        return _recapture_response("workflow", request_id, "번호판을 인식하지 못했습니다. 다시 촬영해 주세요.", trace)

    if not recognition.plate_number or recognition.confidence < settings.parking_ocr_confidence_threshold:
        trace.extend(_skipped(stage, "번호판 재촬영 필요") for stage in WORKFLOW_STAGES[2:])
        return _recapture_response(
            "workflow", request_id, "번호판이 명확하지 않습니다. 다시 촬영해 주세요.", trace, recognition,
        )

    raw_tool_result = execute_tool_safely("vehicle_lookup", {"plate_number": recognition.plate_number})
    tool_data = safe_tool_data(raw_tool_result)
    if tool_data is None:
        trace.append(ParkingTraceItem(stage=WORKFLOW_STAGES[2], status="error", data={"success": False}))
        policy = deny_processing_failure()
    else:
        trace.append(ParkingTraceItem(stage=WORKFLOW_STAGES[2], status="success", data=tool_data))
        try:
            policy = evaluate_entry_policy(VehicleLookupResult.model_validate(tool_data))
        except Exception:
            policy = deny_processing_failure()

    trace.append(ParkingTraceItem(
        stage=WORKFLOW_STAGES[3],
        status="success" if policy.approved else "rejected",
        data={"approved": policy.approved, "gate_command": policy.gate_command, "reason_code": policy.reason_code},
    ))
    return ParkingEntryResponse(
        system_type="workflow",
        request_id=request_id,
        recognized_plate_number=recognition.plate_number,
        recognition_confidence=recognition.confidence,
        approved=policy.approved,
        gate_command=policy.gate_command,
        reason=policy.reason,
        tool_result=tool_data,
        trace=trace,
    )
