from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest

from app.rag.conversation_store import ConversationStore
from app.rag.kiosk_knowledge import KIOSK_COLLECTION, KIOSK_KNOWLEDGE_DOCUMENTS
from app.rag.rag_retriever import EMBEDDING_DIMENSION, RagConfigurationError, RagRetriever


class FakeCursor:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.executions = []
        self.executemany_call = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, parameters):
        self.executions.append((sql, parameters))

    def executemany(self, sql, rows):
        self.executemany_call = (sql, list(rows))

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class FakeConnection:
    def __init__(self, rows=None):
        self.cursor_instance = FakeCursor(rows)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self.cursor_instance


def embedding(value: float = 0.0) -> list[float]:
    return [value] * EMBEDDING_DIMENSION


def test_knowledge_ids_are_deterministic_and_unique() -> None:
    ids = [document.document_id for document in KIOSK_KNOWLEDGE_DOCUMENTS]

    assert len(ids) == len(set(ids))
    first = KIOSK_KNOWLEDGE_DOCUMENTS[0]
    assert first.document_id == uuid5(NAMESPACE_URL, f"{KIOSK_COLLECTION}:{first.source}:{first.chunk_index}")


def test_retrieve_uses_pgvector_cosine_query_and_maps_documents() -> None:
    document_id = uuid4()
    connection = FakeConnection(
        [(document_id, "매운 메뉴 추천", "매운 치킨 버거를 추천합니다.", 0.91, {"intent": "recommendation"})]
    )
    retriever = RagRetriever(connection_factory=lambda: connection, embedder=lambda _text: embedding())

    result = retriever.retrieve("매운 버거", limit=1)

    assert result[0].document_id == document_id
    assert result[0].score == 0.91
    sql, parameters = connection.cursor_instance.executions[0]
    assert "embedding <=> %s::vector" in sql
    assert "collection_name = %s" in sql
    assert parameters[1] == "kiosk_menu"
    assert parameters[-1] == 1


def test_retrieve_rejects_wrong_embedding_dimension_before_database_call() -> None:
    retriever = RagRetriever(connection_factory=lambda: FakeConnection(), embedder=lambda _text: [0.0, 1.0])

    with pytest.raises(RagConfigurationError, match="768-dimensional"):
        retriever.retrieve("불고기 버거")


def test_upsert_knowledge_documents_is_deterministic_and_idempotent_sql() -> None:
    connection = FakeConnection()
    retriever = RagRetriever(connection_factory=lambda: connection, embedder=lambda _text: embedding(0.1))

    count = retriever.upsert_documents(KIOSK_KNOWLEDGE_DOCUMENTS[:2])

    assert count == 2
    sql, rows = connection.cursor_instance.executemany_call
    assert "ON CONFLICT (id) DO UPDATE" in sql
    assert rows[0][0] == KIOSK_KNOWLEDGE_DOCUMENTS[0].document_id
    assert rows[0][1] == "kiosk_menu"
    assert len(rows[0][9]) == EMBEDDING_DIMENSION


def test_index_check_skips_embedding_when_all_approved_documents_exist() -> None:
    connection = FakeConnection([(len(KIOSK_KNOWLEDGE_DOCUMENTS),)])
    retriever = RagRetriever(connection_factory=lambda: connection, embedder=lambda _text: embedding())

    indexed = retriever.ensure_documents_indexed()

    assert indexed == 0
    sql, parameters = connection.cursor_instance.executions[0]
    assert "embedding IS NOT NULL" in sql
    assert parameters[1] == "kiosk_menu"
    assert connection.cursor_instance.executemany_call is None


def test_conversation_store_appends_transcript_to_session_log_only() -> None:
    session_id = uuid4()
    turn_id = uuid4()
    document_id = uuid4()
    now = datetime.now(timezone.utc)
    connection = FakeConnection([(turn_id, session_id, "매운 버거 추천해 줘", 0.94, [document_id], now)])
    store = ConversationStore(connection_factory=lambda: connection)

    turn = store.append_turn(str(session_id), "매운 버거 추천해 줘", 0.94, [str(document_id)])

    assert turn.turn_id == turn_id
    assert turn.document_ids == [document_id]
    statements = [sql for sql, _parameters in connection.cursor_instance.executions]
    assert any("INSERT INTO conversation_turns" in sql for sql in statements)
    assert all("INSERT INTO documents" not in sql for sql in statements)


def test_conversation_store_reads_turns_in_session_order() -> None:
    session_id = uuid4()
    turn_id = uuid4()
    now = datetime.now(timezone.utc)
    connection = FakeConnection([(turn_id, session_id, "포장해 줘", 0.9, [], now)])
    store = ConversationStore(connection_factory=lambda: connection)

    turns = store.get_turns(str(session_id))

    assert [turn.transcript for turn in turns] == ["포장해 줘"]
    sql, parameters = connection.cursor_instance.executions[0]
    assert "ORDER BY created_at, turn_id" in sql
    assert parameters == (session_id,)
