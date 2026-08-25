"""Read-only PostgreSQL lookup for current kiosk menu facts."""

from collections.abc import Callable
import json
from typing import Any

from app.core.config import settings
from app.rag.rag_retriever import RagConfigurationError, _psycopg_url
from app.schemas.kiosk_rag import MenuCatalogItem, MenuCatalogResult, SearchMenuCatalogArgs


ConnectionFactory = Callable[[], Any]


class MenuCatalogRepository:
    def __init__(self, database_url: str | None = None, connection_factory: ConnectionFactory | None = None) -> None:
        self._database_url = database_url if database_url is not None else settings.database_url
        self._connection_factory = connection_factory

    def search(self, args: SearchMenuCatalogArgs) -> MenuCatalogResult:
        pattern = f"%{args.query}%"
        sql = """
            SELECT
                menu_id,
                name,
                category,
                price,
                description,
                available,
                allergens,
                available_options,
                alternative_menu_id,
                CASE
                    WHEN lower(name) = lower(%s) THEN 0
                    WHEN name ILIKE %s THEN 1
                    WHEN description ILIKE %s THEN 2
                    ELSE 3
                END AS match_rank
            FROM menu_catalog
            WHERE (%s::text IS NULL OR category = %s::text)
              AND (cardinality(%s::text[]) = 0 OR NOT allergens && %s::text[])
              AND (name ILIKE %s OR description ILIKE %s OR category ILIKE %s)
            ORDER BY match_rank, available DESC, price, menu_id
            LIMIT %s
        """
        parameters = (
            args.query,
            pattern,
            pattern,
            args.category,
            args.category,
            args.allergens_to_avoid,
            args.allergens_to_avoid,
            pattern,
            pattern,
            pattern,
            args.limit,
        )
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, parameters)
                rows = cursor.fetchall()

        items = [
            MenuCatalogItem(
                menu_id=row[0],
                name=row[1],
                category=row[2],
                price=row[3],
                description=row[4],
                available=row[5],
                allergens=list(row[6] or []),
                available_options=self._json_object(row[7]),
                alternative_menu_id=row[8],
            )
            for row in rows
        ]
        return MenuCatalogResult(query=args.query, items=items, matched_count=len(items))

    def _connect(self) -> Any:
        if self._connection_factory is not None:
            return self._connection_factory()
        if not self._database_url:
            raise RagConfigurationError("DATABASE_URL is not configured.")
        try:
            import psycopg
        except ImportError as error:
            raise RagConfigurationError("psycopg is required for menu catalog access.") from error
        return psycopg.connect(_psycopg_url(self._database_url))

    @staticmethod
    def _json_object(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        return {}


_default_repository = MenuCatalogRepository()


def set_menu_catalog_repository(repository: MenuCatalogRepository | None) -> None:
    global _default_repository
    _default_repository = repository or MenuCatalogRepository()


def search_menu_catalog(args: SearchMenuCatalogArgs) -> dict:
    result = _default_repository.search(args)
    return result.model_dump(mode="json", by_alias=False)
