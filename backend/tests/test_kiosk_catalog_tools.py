import base64
import importlib
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.kiosk_rag import (
    ConversationTurn,
    RetrievedDocument,
    SearchMenuCatalogArgs,
    TranscribeAndRetrieveArgs,
)
from app.services.speech_service import SpeechTranscript, SpeechValidationError, transcribe
from app.tools.kiosk.search_menu_catalog import MenuCatalogRepository, search_menu_catalog, set_menu_catalog_repository


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.query = None
        self.parameters = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, parameters):
        self.query = query
        self.parameters = parameters

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows):
        self.cursor_instance = FakeCursor(rows)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self.cursor_instance


@pytest.fixture(autouse=True)
def reset_catalog_repository():
    yield
    set_menu_catalog_repository(None)


def test_catalog_returns_current_price_options_and_sold_out_alternative() -> None:
    connection = FakeConnection(
        [
            (
                "burger_shrimp",
                "새우 버거",
                "burger",
                6800,
                "현재 품절인 새우 버거",
                False,
                ["새우", "밀"],
                {"order_forms": {"single": 0, "set": 2500}},
                "burger_classic",
                1,
            )
        ]
    )
    set_menu_catalog_repository(MenuCatalogRepository(connection_factory=lambda: connection))

    result = search_menu_catalog(SearchMenuCatalogArgs(query="새우 버거", category="burger"))

    assert result["matched_count"] == 1
    assert result["items"][0]["price"] == 6800
    assert result["items"][0]["available"] is False
    assert result["items"][0]["alternative_menu_id"] == "burger_classic"
    assert "SELECT" in connection.cursor_instance.query
    assert all(keyword not in connection.cursor_instance.query for keyword in ("INSERT", "UPDATE", "DELETE"))


def test_catalog_passes_allergen_filter_and_limit_to_sql() -> None:
    connection = FakeConnection([])
    repository = MenuCatalogRepository(connection_factory=lambda: connection)

    repository.search(SearchMenuCatalogArgs(query="버거", allergensToAvoid=["우유"], limit=2))

    assert connection.cursor_instance.parameters[5] == ["우유"]
    assert connection.cursor_instance.parameters[6] == ["우유"]
    assert connection.cursor_instance.parameters[-1] == 2


def test_catalog_matches_menu_names_without_spacing() -> None:
    connection = FakeConnection([])
    repository = MenuCatalogRepository(connection_factory=lambda: connection)

    repository.search(SearchMenuCatalogArgs(query="새우버거"))

    assert "regexp_replace(name" in connection.cursor_instance.query
    assert "%새우버거%" in connection.cursor_instance.parameters


@pytest.mark.parametrize(
    "payload",
    [
        {"query": ""},
        {"query": "버거", "limit": 0},
        {"query": "버거", "limit": 6},
        {"query": "버거", "allergensToAvoid": [""]},
        {"query": "버거", "allergensToAvoid": [str(index) for index in range(11)]},
    ],
)
def test_catalog_schema_rejects_invalid_arguments(payload) -> None:
    with pytest.raises(ValidationError):
        SearchMenuCatalogArgs.model_validate(payload)


def test_mock_stt_works_without_external_api_key(monkeypatch) -> None:
    monkeypatch.setenv("KIOSK_STT_MODE", "mock")
    monkeypatch.setenv("KIOSK_MOCK_TRANSCRIPT", "불고기 버거 하나 주세요")
    monkeypatch.setenv("KIOSK_MOCK_STT_CONFIDENCE", "0.93")

    result = transcribe(b"not-stored-audio", "audio/webm")

    assert result == SpeechTranscript(text="불고기 버거 하나 주세요", confidence=0.93, provider="mock")


def test_stt_rejects_empty_and_oversized_audio(monkeypatch) -> None:
    with pytest.raises(SpeechValidationError, match="빈 음성"):
        transcribe(b"", "audio/webm")

    monkeypatch.setenv("KIOSK_MAX_AUDIO_SIZE_BYTES", "2")
    with pytest.raises(SpeechValidationError, match="최대 크기"):
        transcribe(b"123", "audio/webm")


def test_transcript_override_is_rejected_outside_development(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(SpeechValidationError, match="개발 환경"):
        transcribe(b"audio", "audio/webm", "테스트 발화")


def test_transcribe_and_retrieve_logs_retrievals_and_marks_low_confidence(monkeypatch) -> None:
    tool_module = importlib.import_module("app.tools.kiosk.transcribe_and_retrieve")
    session_id = uuid4()
    turn_id = uuid4()
    document_id = uuid4()
    calls = {}

    monkeypatch.setattr(
        tool_module,
        "transcribe",
        lambda *_args: SpeechTranscript(text="매운 버거 추천해 줘", confidence=0.69, provider="mock"),
    )
    monkeypatch.setattr(
        tool_module,
        "retrieve_knowledge",
        lambda query, limit: [
            RetrievedDocument(
                document_id=document_id,
                title="매운 메뉴 추천",
                content="매운 치킨 버거를 추천합니다.",
                score=0.9,
                metadata={"intent": "recommendation"},
            )
        ],
    )

    def fake_append(session, transcript, confidence, document_ids):
        calls.update(
            session=session,
            transcript=transcript,
            confidence=confidence,
            document_ids=document_ids,
        )
        return ConversationTurn(
            turn_id=turn_id,
            session_id=session_id,
            transcript=transcript,
            confidence=confidence,
            document_ids=document_ids,
        )

    monkeypatch.setattr(tool_module, "append_turn", fake_append)
    args = TranscribeAndRetrieveArgs(
        session_id=session_id,
        audio_base64=base64.b64encode(b"audio").decode("ascii"),
        mime_type="audio/webm",
    )

    result = tool_module.transcribe_and_retrieve(args)

    assert result["needs_confirmation"] is True
    assert result["retrieved_documents"][0]["document_id"] == str(document_id)
    assert calls["document_ids"] == [str(document_id)]


def test_transcribe_and_retrieve_rejects_invalid_base64_before_stt(monkeypatch) -> None:
    tool_module = importlib.import_module("app.tools.kiosk.transcribe_and_retrieve")
    called = False

    def should_not_run(*_args):
        nonlocal called
        called = True

    monkeypatch.setattr(tool_module, "transcribe", should_not_run)
    args = TranscribeAndRetrieveArgs(
        session_id=uuid4(),
        audio_base64="not-base64!",
        mime_type="audio/webm",
    )

    with pytest.raises(SpeechValidationError, match="Base64"):
        tool_module.transcribe_and_retrieve(args)
    assert called is False


def test_transcribe_schema_rejects_wrong_mime_and_blank_audio() -> None:
    session_id = uuid4()
    with pytest.raises(ValidationError):
        TranscribeAndRetrieveArgs(sessionId=session_id, audioBase64="", mimeType="audio/webm")
    with pytest.raises(ValidationError):
        TranscribeAndRetrieveArgs(sessionId=session_id, audioBase64="YQ==", mimeType="video/mp4")


@pytest.mark.parametrize(
    "mime_type",
    ["audio/wav", "audio/x-wav", "audio/webm", "audio/mpeg", "audio/mp4", "audio/x-m4a"],
)
def test_transcribe_schema_accepts_frontend_audio_formats(mime_type) -> None:
    payload = TranscribeAndRetrieveArgs(
        sessionId=uuid4(), audioBase64=base64.b64encode(b"audio").decode("ascii"), mimeType=mime_type
    )

    assert payload.mime_type == mime_type
