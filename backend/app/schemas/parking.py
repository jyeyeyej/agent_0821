"""주차 출입 Workflow, Agent, Tool의 공통 데이터 계약입니다."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


SystemType = Literal["workflow", "agent"]
GateCommand = Literal["open", "keep_closed"]
AccessStatus = Literal["active", "inactive", "not_registered"]


def normalize_plate_number(value: str) -> str:
    normalized = re.sub(r"\s+", "", value.strip()).upper()
    if not normalized:
        raise ValueError("번호판을 입력해 주세요.")
    if not 5 <= len(normalized) <= 12:
        raise ValueError("번호판 길이가 올바르지 않습니다.")
    if not re.fullmatch(r"[0-9A-Z가-힣]+", normalized):
        raise ValueError("번호판에는 한글, 영문, 숫자만 사용할 수 있습니다.")
    return normalized


class ParkingBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VehicleLookupArgs(ParkingBaseModel):
    plate_number: str = Field(min_length=5, max_length=12)

    @field_validator("plate_number", mode="before")
    @classmethod
    def validate_plate_number(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("번호판은 문자열이어야 합니다.")
        return normalize_plate_number(value)


class PlateRecognitionResult(ParkingBaseModel):
    plate_number: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    provider: str = Field(min_length=1)

    @field_validator("plate_number", mode="before")
    @classmethod
    def normalize_optional_plate(cls, value: object) -> str | None:
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise ValueError("번호판은 문자열이어야 합니다.")
        return normalize_plate_number(value)


class VehicleLookupResult(ParkingBaseModel):
    found: bool
    plate_number: str
    vehicle_id: UUID | str | None = None
    owner_label: str | None = None
    access_status: AccessStatus
    access_expires_at: datetime | None = None


class EntryPolicyResult(ParkingBaseModel):
    approved: bool
    gate_command: GateCommand
    reason: str = Field(min_length=1, max_length=300)
    reason_code: str = Field(min_length=1, max_length=50)


class ParkingTraceItem(ParkingBaseModel):
    stage: str = Field(min_length=1)
    status: Literal["success", "rejected", "skipped", "error"]
    data: dict[str, Any] = Field(default_factory=dict)


class ParkingEntryResponse(ParkingBaseModel):
    system_type: SystemType
    request_id: UUID
    recognized_plate_number: str | None = None
    recognition_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    approved: bool
    gate_command: GateCommand
    reason: str = Field(min_length=1, max_length=300)
    needs_recapture: bool = False
    tool_result: dict[str, Any] | None = None
    trace: list[ParkingTraceItem] = Field(default_factory=list)


class ParkingAgentDecision(ParkingBaseModel):
    action: Literal["lookup_vehicle", "request_recapture"]
    plate_number: str | None = None
    reason: str = Field(min_length=1, max_length=300)

    @field_validator("plate_number", mode="before")
    @classmethod
    def normalize_decision_plate(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("번호판은 문자열이어야 합니다.")
        return normalize_plate_number(value)
