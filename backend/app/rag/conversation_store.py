"""PostgreSQL-backed session transcript log for kiosk RAG queries."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.rag.rag_retriever import RagConfigurationError, _psycopg_url
from app.schemas.kiosk_rag import ConversationTurn


ConnectionFactory = Callable[[], Any]


class ConversationStore:
    def __init__(self, database_url: str | None = None, connection_factory: ConnectionFactory | None = None) -> None:
        self._database_url = database_url if database_url is not None else settings.database_url
        self._connection_factory = connection_factory

    def append_turn(
        self,
        session_id: str,
        transcript: str,
        confidence: float,
        document_ids: list[str],
    ) -> ConversationTurn:
        cleaned = transcript.strip()
        if not cleaned:
            raise ValueError("transcript must not be empty")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

        session_uuid = UUID(str(session_id))
        document_uuids = [UUID(str(document_id)) for document_id in document_ids]
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO order_sessions (session_id)
                    VALUES (%s)
                    ON CONFLICT (session_id) DO NOTHING
                    """,
                    (session_uuid,),
                )
                cursor.execute(
                    """
                    INSERT INTO conversation_turns (session_id, transcript, confidence, document_ids)
                    VALUES (%s, %s, %s, %s)
                    RETURNING turn_id, session_id, transcript, confidence, document_ids, created_at
                    """,
                    (session_uuid, cleaned, confidence, document_uuids),
                )
                row = cursor.fetchone()
        return self._to_turn(row)

    def get_turns(self, session_id: str) -> list[ConversationTurn]:
        session_uuid = UUID(str(session_id))
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT turn_id, session_id, transcript, confidence, document_ids, created_at
                    FROM conversation_turns
                    WHERE session_id = %s
                    ORDER BY created_at, turn_id
                    """,
                    (session_uuid,),
                )
                rows = cursor.fetchall()
        return [self._to_turn(row) for row in rows]

    def _connect(self) -> Any:
        if self._connection_factory is not None:
            return self._connection_factory()
        if not self._database_url:
            raise RagConfigurationError("DATABASE_URL is not configured.")
        try:
            import psycopg
        except ImportError as error:
            raise RagConfigurationError("psycopg is required for conversation storage.") from error
        return psycopg.connect(_psycopg_url(self._database_url))

    @staticmethod
    def _to_turn(row: Any) -> ConversationTurn:
        if row is None:
            raise RuntimeError("conversation turn was not returned by PostgreSQL")
        return ConversationTurn(
            turn_id=str(row[0]),
            session_id=str(row[1]),
            transcript=row[2],
            confidence=float(row[3]),
            document_ids=[str(value) for value in (row[4] or [])],
            created_at=row[5],
        )


def append_turn(session_id: str, transcript: str, confidence: float, document_ids: list[str]) -> ConversationTurn:
    return ConversationStore().append_turn(session_id, transcript, confidence, document_ids)


def get_turns(session_id: str) -> list[ConversationTurn]:
    return ConversationStore().get_turns(session_id)
