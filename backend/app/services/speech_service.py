"""Speech synthesis plus kiosk STT without retaining raw customer audio.

Stage 01 Router의 `/api/media/tts` Endpoint가 MP3 음성을 생성할 때 사용합니다.
"""

from dataclasses import dataclass
import os

from app.core.config import settings
from app.providers.openai_media import openai_media_provider


ALLOWED_KIOSK_AUDIO_MIME_TYPES = {"audio/webm", "audio/wav", "audio/mpeg"}
DEFAULT_MAX_AUDIO_SIZE_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class SpeechTranscript:
    text: str
    confidence: float
    provider: str


class SpeechValidationError(ValueError):
    """Raised before any STT provider call for unsafe audio input."""


def create_speech(text: str, voice: str | None, instructions: str) -> bytes:
    return openai_media_provider.create_speech(text, voice, instructions)


def transcribe(audio: bytes, mime_type: str, transcript_override: str | None = None) -> SpeechTranscript:
    if mime_type not in ALLOWED_KIOSK_AUDIO_MIME_TYPES:
        raise SpeechValidationError("지원하지 않는 음성 MIME 형식입니다.")
    if not audio:
        raise SpeechValidationError("빈 음성은 처리할 수 없습니다.")

    max_size = int(os.getenv("KIOSK_MAX_AUDIO_SIZE_BYTES", str(DEFAULT_MAX_AUDIO_SIZE_BYTES)))
    if len(audio) > max_size:
        raise SpeechValidationError("음성 파일이 허용된 최대 크기를 초과했습니다.")

    environment = os.getenv("APP_ENV", "development").lower()
    if transcript_override is not None:
        if environment not in {"development", "dev", "local", "test", "testing"}:
            raise SpeechValidationError("transcript_override는 개발 환경에서만 사용할 수 있습니다.")
        return SpeechTranscript(text=transcript_override.strip(), confidence=1.0, provider="override")

    mode = os.getenv("KIOSK_STT_MODE", "mock").lower()
    if mode == "mock":
        text = os.getenv("KIOSK_MOCK_TRANSCRIPT", "불고기 버거 세트 하나 주세요").strip()
        confidence = float(os.getenv("KIOSK_MOCK_STT_CONFIDENCE", "0.95"))
        if not text:
            raise SpeechValidationError("Mock STT transcript가 비어 있습니다.")
        if not 0.0 <= confidence <= 1.0:
            raise SpeechValidationError("Mock STT confidence는 0과 1 사이여야 합니다.")
        return SpeechTranscript(text=text, confidence=confidence, provider="mock")

    if mode != "openai":
        raise SpeechValidationError("지원하지 않는 KIOSK_STT_MODE입니다.")
    if not settings.openai_api_key:
        raise SpeechValidationError("OpenAI STT를 사용하려면 OPENAI_API_KEY가 필요합니다.")

    from openai import OpenAI

    extension = {"audio/webm": "webm", "audio/wav": "wav", "audio/mpeg": "mp3"}[mime_type]
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.audio.transcriptions.create(
        model=os.getenv("OPENAI_STT_MODEL", "gpt-4o-mini-transcribe"),
        file=(f"kiosk-audio.{extension}", audio, mime_type),
    )
    text = response.text.strip()
    if not text:
        raise SpeechValidationError("음성에서 텍스트를 인식하지 못했습니다.")
    return SpeechTranscript(text=text, confidence=1.0, provider="openai")
