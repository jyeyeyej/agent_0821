"""주차 출입 Workflow와 AI Agent Endpoint입니다."""

from typing import Literal

from fastapi import APIRouter, File, Form, UploadFile

from app.agents.parking_entry_agent import run_parking_entry_agent
from app.schemas.parking import ParkingEntryResponse
from app.services.parking_workflow_service import run_parking_workflow


parking_router = APIRouter(prefix="/api/parking", tags=["주차 출입"])


@parking_router.post("/workflow/entry", response_model=ParkingEntryResponse)
async def parking_workflow_entry(
    image: UploadFile = File(...),
    source: Literal["workflow"] = Form(...),
) -> ParkingEntryResponse:
    return run_parking_workflow(await image.read(), image.content_type or "")


@parking_router.post("/agent/entry", response_model=ParkingEntryResponse)
async def parking_agent_entry(
    image: UploadFile = File(...),
    source: Literal["agent"] = Form(...),
) -> ParkingEntryResponse:
    return run_parking_entry_agent(await image.read(), image.content_type or "")
