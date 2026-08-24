"""번호판 조회 또는 재촬영만 선택할 수 있는 제한된 주차 Agent입니다."""

import json
from uuid import uuid4

from app.core.config import settings
from app.schemas.parking import (
    ParkingAgentDecision,
    ParkingEntryResponse,
    ParkingTraceItem,
    PlateRecognitionResult,
    VehicleLookupResult,
)
from app.services.entry_policy_service import deny_processing_failure, evaluate_entry_policy
from app.services.parking_workflow_service import safe_tool_data
from app.services.plate_recognition_service import ParkingImageValidationError, extract_plate
from app.tools.executor import execute_tool_safely
from app.tools.registry import get_tool_definitions


def _mock_decision(recognition: PlateRecognitionResult) -> ParkingAgentDecision:
    if recognition.plate_number and recognition.confidence >= settings.parking_ocr_confidence_threshold:
        return ParkingAgentDecision(
            action="lookup_vehicle", plate_number=recognition.plate_number, reason="번호판과 신뢰도가 조회 기준을 충족합니다.",
        )
    return ParkingAgentDecision(action="request_recapture", reason="번호판이 명확하지 않아 재촬영이 필요합니다.")


def _openai_decision(recognition: PlateRecognitionResult) -> ParkingAgentDecision:
    if not settings.openai_api_key:
        raise RuntimeError("Agent API 설정이 없습니다.")
    from openai import OpenAI

    tool_schema = get_tool_definitions({"vehicle_lookup"})
    response = OpenAI(api_key=settings.openai_api_key).responses.parse(
        model=settings.openai_model,
        instructions=(
            "주차 번호판 인식 결과가 명확하면 lookup_vehicle, 아니면 request_recapture만 선택하세요. "
            "번호판을 추측하거나 수정하지 말고 승인 여부도 결정하지 마세요."
        ),
        input=json.dumps({
            "plate_number": recognition.plate_number,
            "confidence": recognition.confidence,
            "minimum_confidence": settings.parking_ocr_confidence_threshold,
            "allowed_tools": tool_schema,
        }, ensure_ascii=False),
        text_format=ParkingAgentDecision,
    )
    if response.output_parsed is None:
        raise RuntimeError("Agent 결정을 구조화하지 못했습니다.")
    return response.output_parsed


def decide_parking_action(recognition: PlateRecognitionResult) -> ParkingAgentDecision:
    if settings.parking_agent_mode == "mock":
        return _mock_decision(recognition)
    if settings.parking_agent_mode == "openai":
        return _openai_decision(recognition)
    raise RuntimeError("지원하지 않는 주차 Agent 모드입니다.")


def run_parking_entry_agent(content: bytes, content_type: str) -> ParkingEntryResponse:
    request_id = uuid4()
    trace: list[ParkingTraceItem] = []
    try:
        recognition = extract_plate(content, content_type)
        trace.append(ParkingTraceItem(stage="1_plate_recognition", status="success", data={
            "plate_number": recognition.plate_number, "confidence": recognition.confidence,
        }))
    except ParkingImageValidationError as error:
        trace.append(ParkingTraceItem(stage="1_plate_recognition", status="rejected", data={"reason": str(error)}))
        return ParkingEntryResponse(
            system_type="agent", request_id=request_id, approved=False, gate_command="keep_closed",
            reason=str(error), needs_recapture=True, trace=trace,
        )
    except Exception:
        trace.append(ParkingTraceItem(stage="1_plate_recognition", status="error", data={"reason": "번호판 인식 실패"}))
        return ParkingEntryResponse(
            system_type="agent", request_id=request_id, approved=False, gate_command="keep_closed",
            reason="번호판을 인식하지 못했습니다. 다시 촬영해 주세요.", needs_recapture=True, trace=trace,
        )

    try:
        decision = decide_parking_action(recognition)
    except Exception:
        decision = ParkingAgentDecision(action="request_recapture", reason="Agent 판단을 완료하지 못했습니다.")

    # Agent가 OCR 결과를 바꾸거나 낮은 신뢰도를 우회하지 못하게 Backend가 재검증합니다.
    valid_lookup = (
        decision.action == "lookup_vehicle"
        and recognition.plate_number is not None
        and decision.plate_number == recognition.plate_number
        and recognition.confidence >= settings.parking_ocr_confidence_threshold
    )
    trace.append(ParkingTraceItem(stage="2_agent_decision", status="success" if valid_lookup else "rejected", data={
        "action": decision.action, "reason": decision.reason,
    }))
    if not valid_lookup:
        return ParkingEntryResponse(
            system_type="agent", request_id=request_id,
            recognized_plate_number=recognition.plate_number, recognition_confidence=recognition.confidence,
            approved=False, gate_command="keep_closed", reason="번호판이 명확하지 않습니다. 다시 촬영해 주세요.",
            needs_recapture=True, trace=trace,
        )

    raw_tool_result = execute_tool_safely("vehicle_lookup", {"plate_number": recognition.plate_number})
    tool_data = safe_tool_data(raw_tool_result)
    trace.append(ParkingTraceItem(
        stage="3_tool_execution", status="success" if tool_data is not None else "error",
        data=tool_data or {"success": False},
    ))
    if tool_data is None:
        policy = deny_processing_failure()
    else:
        try:
            policy = evaluate_entry_policy(VehicleLookupResult.model_validate(tool_data))
        except Exception:
            policy = deny_processing_failure()
    trace.append(ParkingTraceItem(stage="4_entry_policy", status="success" if policy.approved else "rejected", data={
        "approved": policy.approved, "gate_command": policy.gate_command, "reason_code": policy.reason_code,
    }))
    return ParkingEntryResponse(
        system_type="agent", request_id=request_id,
        recognized_plate_number=recognition.plate_number, recognition_confidence=recognition.confidence,
        approved=policy.approved, gate_command=policy.gate_command, reason=policy.reason,
        tool_result=tool_data, trace=trace,
    )
