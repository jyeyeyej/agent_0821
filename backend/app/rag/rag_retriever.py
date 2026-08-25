"""Ollama embedding and pgvector cosine retrieval for approved kiosk data."""

from collections.abc import Callable, Sequence
import json
import os
from typing import Any

import httpx

from app.core.config import settings
from app.rag.kiosk_knowledge import (
    DEFAULT_EMBEDDING_MODEL,
    EMBEDDING_DIMENSION,
    EMBEDDING_PROVIDER,
    KIOSK_COLLECTION,
    KIOSK_KNOWLEDGE_DOCUMENTS,
    KnowledgeDocument,
)
from app.schemas.kiosk_rag import RetrievedDocument


class RagConfigurationError(RuntimeError):
    """Raised when PostgreSQL or the embedding runtime is unavailable."""


ConnectionFactory = Callable[[], Any]
Embedder = Callable[[str], Sequence[float]]


def _psycopg_url(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


class RagRetriever:
    def __init__(
        self,
        database_url: str | None = None,
        connection_factory: ConnectionFactory | None = None,
        embedder: Embedder | None = None,
        embedding_model: str | None = None,
    ) -> None:
        self._database_url = database_url if database_url is not None else settings.database_url
        self._connection_factory = connection_factory
        self._embedder = embedder
        self._embedding_model = embedding_model or os.getenv("OLLAMA_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)

    def retrieve(self, query: str, limit: int = 3) -> list[RetrievedDocument]:
        cleaned_query = query.strip()
        if not cleaned_query:
            raise ValueError("query must not be empty")
        if not 1 <= limit <= 5:
            raise ValueError("limit must be between 1 and 5")

        embedding = self._create_embedding(cleaned_query)
        sql = """
            SELECT
                id,
                title,
                content,
                1 - (embedding <=> %s::vector) AS score,
                metadata
            FROM documents
            WHERE collection_name = %s
              AND embedding_provider = %s
              AND embedding_model = %s
              AND embedding_dimension = %s
              AND embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector, id
            LIMIT %s
        """
        parameters = (
            embedding,
            KIOSK_COLLECTION,
            EMBEDDING_PROVIDER,
            self._embedding_model,
            EMBEDDING_DIMENSION,
            embedding,
            limit,
        )
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, parameters)
                rows = cursor.fetchall()

        return [
            RetrievedDocument(
                document_id=str(row[0]),
                title=row[1],
                content=row[2],
                score=max(-1.0, min(1.0, float(row[3]))),
                metadata=self._metadata(row[4]),
            )
            for row in rows
        ]

    def ensure_documents_indexed(
        self,
        documents: Sequence[KnowledgeDocument] = KIOSK_KNOWLEDGE_DOCUMENTS,
    ) -> int:
        """Embed approved seed documents only when their vectors are missing."""
        if not documents:
            return 0
        document_ids = [document.document_id for document in documents]
        sql = """
            SELECT count(*)
            FROM documents
            WHERE id = ANY(%s::uuid[])
              AND collection_name = %s
              AND embedding_provider = %s
              AND embedding_model = %s
              AND embedding_dimension = %s
              AND embedding IS NOT NULL
        """
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql,
                    (
                        document_ids,
                        KIOSK_COLLECTION,
                        EMBEDDING_PROVIDER,
                        self._embedding_model,
                        EMBEDDING_DIMENSION,
                    ),
                )
                row = cursor.fetchone()
        indexed_count = int(row[0]) if row is not None else 0
        if indexed_count == len(documents):
            return 0
        return self.upsert_documents(documents)

    def upsert_documents(self, documents: Sequence[KnowledgeDocument] = KIOSK_KNOWLEDGE_DOCUMENTS) -> int:
        sql = """
            INSERT INTO documents (
                id, collection_name, title, content, source, chunk_index,
                embedding_provider, embedding_model, embedding_dimension,
                embedding, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (id) DO UPDATE SET
                collection_name = EXCLUDED.collection_name,
                title = EXCLUDED.title,
                content = EXCLUDED.content,
                source = EXCLUDED.source,
                chunk_index = EXCLUDED.chunk_index,
                embedding_provider = EXCLUDED.embedding_provider,
                embedding_model = EXCLUDED.embedding_model,
                embedding_dimension = EXCLUDED.embedding_dimension,
                embedding = EXCLUDED.embedding,
                metadata = EXCLUDED.metadata,
                updated_at = CURRENT_TIMESTAMP
        """
        rows = []
        for document in documents:
            rows.append(
                (
                    document.document_id,
                    KIOSK_COLLECTION,
                    document.title,
                    document.content,
                    document.source,
                    document.chunk_index,
                    EMBEDDING_PROVIDER,
                    self._embedding_model,
                    EMBEDDING_DIMENSION,
                    self._create_embedding(document.content),
                    json.dumps(document.metadata, ensure_ascii=False),
                )
            )

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(sql, rows)
        return len(rows)

    def _create_embedding(self, text: str) -> list[float]:
        if self._embedder is not None:
            embedding = list(self._embedder(text))
        else:
            response = httpx.post(
                f"{settings.ollama_base_url}/api/embed",
                json={"model": self._embedding_model, "input": text},
                timeout=settings.request_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            embeddings = payload.get("embeddings")
            if not isinstance(embeddings, list) or not embeddings or not isinstance(embeddings[0], list):
                raise RagConfigurationError("Ollama embedding response is invalid.")
            embedding = embeddings[0]

        if len(embedding) != EMBEDDING_DIMENSION:
            raise RagConfigurationError(
                f"Expected {EMBEDDING_DIMENSION}-dimensional embeddings, received {len(embedding)}."
            )
        return [float(value) for value in embedding]

    def _connect(self) -> Any:
        if self._connection_factory is not None:
            return self._connection_factory()
        if not self._database_url:
            raise RagConfigurationError("DATABASE_URL is not configured.")
        try:
            import psycopg
            from pgvector.psycopg import register_vector
        except ImportError as error:
            raise RagConfigurationError("psycopg and pgvector are required for kiosk RAG.") from error

        connection = psycopg.connect(_psycopg_url(self._database_url))
        register_vector(connection)
        return connection

    @staticmethod
    def _metadata(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        return {}


def retrieve_knowledge(query: str, limit: int = 3) -> list[RetrievedDocument]:
    retriever = RagRetriever()
    retriever.ensure_documents_indexed()
    return retriever.retrieve(query, limit)


def upsert_knowledge_documents() -> int:
    return RagRetriever().upsert_documents()
