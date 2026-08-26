from uuid import uuid4

from clients import kiosk_client


def test_update_order_cart_uses_patch_and_adds_session_id(monkeypatch) -> None:
    session_id = str(uuid4())
    captured = {}

    def fake_request(method, path, json=None):
        captured.update(method=method, path=path, json=json)
        return {"status": "active", "items": []}

    monkeypatch.setattr(kiosk_client, "request", fake_request)

    result = kiosk_client.update_order_cart(
        session_id,
        {
            "operation": "remove",
            "cartItemId": str(uuid4()),
            "orderType": "takeout",
        },
    )

    assert captured["method"] == "PATCH"
    assert captured["path"] == f"/api/kiosk/sessions/{session_id}/cart"
    assert captured["json"]["sessionId"] == session_id
    assert result["status"] == "active"
