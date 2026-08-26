"""번호판으로 차량 등록 정보를 읽기 전용 조회하는 공용 Tool입니다."""

from collections.abc import Callable
from typing import Any

from app.schemas.parking import VehicleLookupArgs, VehicleLookupResult


RepositoryGetter = Callable[[str], Any]
_repository_getter: RepositoryGetter | None = None

#Repository 조회 함수를 받을 준비
def set_vehicle_repository_getter(getter: RepositoryGetter | None) -> None:
    """테스트 주입 또는 Repository 조립을 위한 작은 경계입니다."""
    global _repository_getter
    _repository_getter = getter


#실제 Repository 함수 가져오기
def _get_repository_getter() -> RepositoryGetter:
    if _repository_getter is not None:
        return _repository_getter
    try:
        from app.repositories.vehicle_repository import get_vehicle_by_plate
    except (ImportError, ModuleNotFoundError) as error:
        raise RuntimeError("차량 Repository가 준비되지 않았습니다.") from error
    return get_vehicle_by_plate

#_field() — dict든 객체든 값 꺼내기
def _field(record: Any, name: str, default: Any = None) -> Any:
    if isinstance(record, dict):
        return record.get(name, default)
    return getattr(record, name, default)

#vehicle_lookup() — 실제 Tool 핵심
def vehicle_lookup(args: VehicleLookupArgs) -> dict:
    
    #번호판으로 차량 조회
    record = _get_repository_getter()(args.plate_number)
    
    #차량이 없으면 미등록 반환
    if record is None:
        return VehicleLookupResult(
            found=False,
            plate_number=args.plate_number,
            access_status="not_registered",
        ).model_dump(mode="json")
    #차량이 있으면 등록 정보 반환
    result = VehicleLookupResult(
        found=True,
        plate_number=_field(record, "plate_number", args.plate_number),
        vehicle_id=_field(record, "vehicle_id"),
        owner_label=_field(record, "owner_label"),
        access_status=_field(record, "access_status"),
        access_expires_at=_field(record, "access_expires_at"),
    )
    #Pydantic 결과를 dict로 변환
    return result.model_dump(mode="json")
