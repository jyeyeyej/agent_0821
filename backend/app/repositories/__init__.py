"""PostgreSQL repositories owned by the parking DB module."""

from app.repositories.vehicle_repository import (
    DatabaseConnectionError,
    VehicleRecord,
    VehicleRepository,
)

__all__ = ["DatabaseConnectionError", "VehicleRecord", "VehicleRepository"]
