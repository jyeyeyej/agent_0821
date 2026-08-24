"""Read-only PostgreSQL repository for registered parking vehicles."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.config import settings


class DatabaseConnectionError(RuntimeError):
    """Raised when the parking database cannot be reached or queried safely."""


@dataclass(frozen=True)
class VehicleRecord:
    vehicle_id: str
    plate_number: str
    owner_label: str
    access_status: str
    access_expires_at: datetime | None


ConnectionFactory = Callable[[], Any]


class VehicleRepository:
    """Provides exact-match, read-only access to the ``vehicles`` table.

    This repository intentionally does not decide entry approval. It returns a
    registered vehicle or ``None`` for an unregistered plate, while connection
    and SQL failures are surfaced as ``DatabaseConnectionError``.
    """

    def __init__(self, database_url: str | None = None, connection_factory: ConnectionFactory | None = None) -> None:
        self._database_url = database_url if database_url is not None else settings.database_url
        self._connection_factory = connection_factory

    def get_vehicle_by_plate(self, plate_number: str) -> VehicleRecord | None:
        """Return one registered vehicle for an already-normalized plate number."""
        if not plate_number:
            raise ValueError("plate_number must not be empty")

        query = """
            SELECT vehicle_id, plate_number, owner_label, access_status, access_expires_at
            FROM vehicles
            WHERE plate_number = %s
        """

        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(query, (plate_number,))
                    row = cursor.fetchone()
        except DatabaseConnectionError:
            raise
        except Exception as error:
            raise DatabaseConnectionError("Unable to query the parking database.") from error

        if row is None:
            return None

        return VehicleRecord(
            vehicle_id=str(row[0]),
            plate_number=row[1],
            owner_label=row[2],
            access_status=row[3],
            access_expires_at=row[4],
        )

    def _connect(self) -> Any:
        if self._connection_factory is not None:
            return self._connection_factory()

        if not self._database_url:
            raise DatabaseConnectionError("DATABASE_URL is not configured.")

        try:
            import psycopg
        except ImportError as error:
            raise DatabaseConnectionError("psycopg is required for PostgreSQL access.") from error

        try:
            return psycopg.connect(self._psycopg_connection_url())
        except Exception as error:
            raise DatabaseConnectionError("Unable to connect to the parking database.") from error

    def _psycopg_connection_url(self) -> str:
        """Convert the project SQLAlchemy URL to the URI accepted by psycopg."""
        return self._database_url.replace("postgresql+psycopg://", "postgresql://", 1)


_default_repository = VehicleRepository()


def get_vehicle_by_plate(plate_number: str) -> VehicleRecord | None:
    """Public repository contract used by the read-only vehicle lookup Tool."""
    return _default_repository.get_vehicle_by_plate(plate_number)
