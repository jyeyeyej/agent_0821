"""Backend A contracts for STT, RAG retrieval, and catalog lookup."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


AudioMimeType = Literal[
    "audio/aac",
    "audio/flac",
    "audio/m4a",
    "audio/mp4",
    "audio/mpeg",
    "audio/ogg",
    "audio/wav",
    "audio/webm",
    "audio/x-m4a",
    "audio/x-wav",
]


class KioskRagModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)


class TranscribeAndRetrieveArgs(KioskRagModel):
    session_id: UUID = Field(alias="sessionId")
    audio_base64: str = Field(min_length=1, max_length=15_000_000, alias="audioBase64")
    mime_type: AudioMimeType = Field(alias="mimeType")
    transcript_override: str | None = Field(default=None, min_length=1, max_length=1000, alias="transcriptOverride")

    @field_validator("audio_base64", "transcript_override")
    @classmethod
    def reject_blank_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("빈 문자열은 입력할 수 없습니다.")
        return value


class SearchMenuCatalogArgs(KioskRagModel):
    query: str = Field(min_length=1, max_length=300)
    category: str | None = Field(default=None, min_length=1, max_length=50)
    allergens_to_avoid: list[str] = Field(default_factory=list, max_length=10, alias="allergensToAvoid")
    limit: int = Field(default=5, ge=1, le=5)

    @field_validator("query", "category")
    @classmethod
    def strip_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("빈 문자열은 입력할 수 없습니다.")
        return cleaned

    @field_validator("allergens_to_avoid")
    @classmethod
    def normalize_allergens(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = value.strip()
            if not cleaned:
                raise ValueError("빈 알레르겐은 입력할 수 없습니다.")
            key = cleaned.casefold()
            if key not in seen:
                normalized.append(cleaned)
                seen.add(key)
        return normalized


class RetrievedDocument(KioskRagModel):
    document_id: UUID = Field(alias="documentId")
    title: str
    content: str
    score: float = Field(ge=-1.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationTurn(KioskRagModel):
    turn_id: UUID = Field(alias="turnId")
    session_id: UUID = Field(alias="sessionId")
    transcript: str
    confidence: float = Field(ge=0.0, le=1.0)
    document_ids: list[UUID] = Field(default_factory=list, alias="documentIds")
    created_at: datetime | None = Field(default=None, alias="createdAt")


class TranscriptResult(KioskRagModel):
    turn_id: UUID = Field(alias="turnId")
    transcript: str
    confidence: float = Field(ge=0.0, le=1.0)
    retrieved_documents: list[RetrievedDocument] = Field(default_factory=list, alias="retrievedDocuments")
    needs_confirmation: bool = Field(alias="needsConfirmation")


class MenuCatalogItem(KioskRagModel):
    menu_id: str = Field(alias="menuId")
    name: str
    category: str
    price: int = Field(ge=0)
    description: str
    available: bool
    allergens: list[str] = Field(default_factory=list)
    available_options: dict[str, Any] = Field(default_factory=dict, alias="availableOptions")
    alternative_menu_id: str | None = Field(default=None, alias="alternativeMenuId")


class MenuCatalogResult(KioskRagModel):
    query: str
    items: list[MenuCatalogItem] = Field(default_factory=list)
    matched_count: int = Field(ge=0, alias="matchedCount")
