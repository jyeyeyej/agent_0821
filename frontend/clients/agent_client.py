from typing import Any

from core.api_client import request


def run_menu_recommendation(payload: dict[str, Any]):
    return request("POST", "/api/menu/recommend", json=payload)


def run_learning_assistant(payload: dict[str, Any]):
    return request("POST", "/api/learning/assist", json=payload)
