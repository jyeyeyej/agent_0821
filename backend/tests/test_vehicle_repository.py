from datetime import datetime, timezone

import pytest

from app.repositories.vehicle_repository import DatabaseConnectionError, VehicleRepository


class FakeCursor:
    def __init__(self, row):
        self.row = row
        self.query = None
        self.parameters = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, parameters):
        self.query = query
        self.parameters = parameters

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, row):
        self.cursor_instance = FakeCursor(row)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self.cursor_instance


def test_get_vehicle_by_plate_returns_exact_registered_vehicle() -> None:
    expires_at = datetime(2027, 1, 1, tzinfo=timezone.utc)
    connection = FakeConnection(("vehicle-uuid", "12가3456", "테스트 차량 A", "active", expires_at))
    repository = VehicleRepository(connection_factory=lambda: connection)

    vehicle = repository.get_vehicle_by_plate("12가3456")

    assert vehicle is not None
    assert vehicle.vehicle_id == "vehicle-uuid"
    assert vehicle.access_expires_at == expires_at
    assert connection.cursor_instance.parameters == ("12가3456",)
    assert "WHERE plate_number = %s" in connection.cursor_instance.query


def test_get_vehicle_by_plate_returns_none_when_not_registered() -> None:
    repository = VehicleRepository(connection_factory=lambda: FakeConnection(None))

    assert repository.get_vehicle_by_plate("99라9999") is None


def test_get_vehicle_by_plate_rejects_empty_plate() -> None:
    repository = VehicleRepository(connection_factory=lambda: FakeConnection(None))

    with pytest.raises(ValueError, match="must not be empty"):
        repository.get_vehicle_by_plate("")


def test_get_vehicle_by_plate_wraps_query_failure() -> None:
    def failing_connection_factory():
        raise OSError("database unavailable")

    repository = VehicleRepository(connection_factory=failing_connection_factory)

    with pytest.raises(DatabaseConnectionError, match="Unable to query"):
        repository.get_vehicle_by_plate("12가3456")


def test_repository_requires_database_url_when_no_factory_is_supplied() -> None:
    repository = VehicleRepository(database_url="")

    with pytest.raises(DatabaseConnectionError, match="DATABASE_URL"):
        repository.get_vehicle_by_plate("12가3456")


def test_repository_converts_sqlalchemy_url_for_psycopg() -> None:
    repository = VehicleRepository(database_url="postgresql+psycopg://parking_user:password@localhost:5432/parking_db")

    assert repository._psycopg_connection_url() == "postgresql://parking_user:password@localhost:5432/parking_db"
