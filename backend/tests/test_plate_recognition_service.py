import pytest

from app.services.plate_recognition_service import (
    ParkingImageValidationError,
    extract_plate,
    validate_image,
)


JPEG = b"\xff\xd8\xff" + b"parking-image" + b"\xff\xd9"
PNG = b"\x89PNG\r\n\x1a\n" + b"parking-image" + b"IEND" + b"\x00" * 8


def test_validate_supported_image_signatures() -> None:
    assert validate_image(JPEG, "image/jpeg") == "image/jpeg"
    assert validate_image(PNG, "image/png") == "image/png"


@pytest.mark.parametrize(
    ("content", "content_type"),
    [
        (b"", "image/jpeg"),
        (JPEG, "text/plain"),
        (JPEG, "image/png"),
        (b"not-an-image", "image/jpeg"),
    ],
)
def test_invalid_images_are_rejected(content: bytes, content_type: str) -> None:
    with pytest.raises(ParkingImageValidationError):
        validate_image(content, content_type)


def test_mock_ocr_returns_happy_case() -> None:
    result = extract_plate(JPEG, "image/jpeg")

    assert result.plate_number == "12가3456"
    assert result.confidence == 0.98
    assert result.provider == "mock"
