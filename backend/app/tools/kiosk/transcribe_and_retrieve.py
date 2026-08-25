"""Validate audio, transcribe it, retrieve evidence, and append a query log."""

import base64
import binascii

from app.rag.conversation_store import append_turn
from app.rag.rag_retriever import retrieve_knowledge
from app.schemas.kiosk_rag import TranscribeAndRetrieveArgs, TranscriptResult
from app.services.speech_service import SpeechValidationError, transcribe


def transcribe_and_retrieve(args: TranscribeAndRetrieveArgs) -> dict:
    try:
        audio = base64.b64decode(args.audio_base64, validate=True)
    except (binascii.Error, ValueError) as error:
        raise SpeechValidationError("유효한 Base64 음성이 아닙니다.") from error

    transcript = transcribe(audio, args.mime_type, args.transcript_override)
    documents = retrieve_knowledge(transcript.text, limit=3)
    turn = append_turn(
        str(args.session_id),
        transcript.text,
        transcript.confidence,
        [str(document.document_id) for document in documents],
    )
    result = TranscriptResult(
        turn_id=turn.turn_id,
        transcript=transcript.text,
        confidence=transcript.confidence,
        retrieved_documents=documents,
        needs_confirmation=transcript.confidence < 0.70,
    )
    return result.model_dump(mode="json", by_alias=False)
