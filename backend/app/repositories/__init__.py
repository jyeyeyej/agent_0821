"""PostgreSQL repositories owned by the parking DB module."""

from app.repositories.vehicle_repository import (
    DatabaseConnectionError,
    VehicleRecord,
    VehicleRepository,
    get_vehicle_by_plate,
)

__all__ = ["DatabaseConnectionError", "VehicleRecord", "VehicleRepository", "get_vehicle_by_plate"]
