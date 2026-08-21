from typing import Any

from core.api_client import request


def run_menu_recommendation(payload: dict[str, Any]):
    return request("POST", "/api/agents/menu-recommendation", json=payload)


def run_learning_assistant(payload: dict[str, Any]):
    return request("POST", "/api/agents/learning-assistant", json=payload)
