"""Approved source documents for the kiosk knowledge collection.

User transcripts never enter this collection. The same source/chunk keys are
also represented in ``backend/db/seed.sql`` so SQL bootstrap and embedding
ingestion remain deterministic.
"""

from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5


KIOSK_COLLECTION = "kiosk_menu"
EMBEDDING_PROVIDER = "ollama"
DEFAULT_EMBEDDING_MODEL = "embeddinggemma"
EMBEDDING_DIMENSION = 768


@dataclass(frozen=True)
class KnowledgeDocument:
    title: str
    content: str
    source: str
    chunk_index: int
    metadata: dict[str, Any]

    @property
    def document_id(self) -> UUID:
        return uuid5(NAMESPACE_URL, f"{KIOSK_COLLECTION}:{self.source}:{self.chunk_index}")


def _metadata(
    document_type: str,
    *,
    menu_id: str | None,
    category: str,
    available: bool,
    allergens: list[str],
    intent: str,
) -> dict[str, Any]:
    return {
        "type": document_type,
        "menu_id": menu_id,
        "category": category,
        "available": available,
        "allergens": allergens,
        "intent": intent,
        "updated_at": "2026-08-25",
    }


KIOSK_KNOWLEDGE_DOCUMENTS: tuple[KnowledgeDocument, ...] = (
    KnowledgeDocument(
        title="불고기 버거",
        content="불고기 버거는 달콤한 불고기 소스와 소고기 패티, 양상추, 피클로 구성된 단품 메뉴입니다. 가격은 6,500원이며 세트 변경이 가능합니다.",
        source="menu_bulgogi",
        chunk_index=0,
        metadata=_metadata(
            "menu",
            menu_id="burger_bulgogi",
            category="burger",
            available=True,
            allergens=["밀", "대두", "계란"],
            intent="menu_lookup",
        ),
    ),
    KnowledgeDocument(
        title="매운 치킨 버거",
        content="매운 치킨 버거는 매콤한 소스와 바삭한 치킨 패티로 만든 든든한 메뉴입니다. 단품은 7,000원이며 세트, 치즈 추가, 제로 콜라 변경이 가능합니다.",
        source="menu_spicy_chicken",
        chunk_index=0,
        metadata=_metadata(
            "menu",
            menu_id="burger_spicy_chicken",
            category="burger",
            available=True,
            allergens=["밀", "대두", "계란", "우유"],
            intent="menu_lookup",
        ),
    ),
    KnowledgeDocument(
        title="새우 버거",
        content="새우 버거는 현재 품절입니다. 새우 알레르겐을 포함하며 대체 메뉴로 클래식 비프 버거를 안내할 수 있습니다.",
        source="menu_shrimp",
        chunk_index=0,
        metadata=_metadata(
            "menu",
            menu_id="burger_shrimp",
            category="burger",
            available=False,
            allergens=["새우", "밀", "대두", "계란", "우유"],
            intent="availability",
        ),
    ),
    KnowledgeDocument(
        title="버거 세트 옵션 규칙",
        content="버거는 세트로 변경할 수 있습니다. 기본 세트는 감자튀김과 음료로 구성되며 사이즈업과 허용된 음료 변경은 카탈로그 옵션을 확인해야 합니다.",
        source="option_set",
        chunk_index=0,
        metadata=_metadata("option", menu_id=None, category="policy", available=True, allergens=[], intent="option_rule"),
    ),
    KnowledgeDocument(
        title="알레르기 안내",
        content="알레르기 정보는 안내용입니다. 고객이 알레르기를 말하면 카탈로그의 알레르겐을 확인하고 교차오염 가능성이 있으므로 매장 성분표 확인을 함께 안내합니다.",
        source="allergy_notice",
        chunk_index=0,
        metadata=_metadata("allergen", menu_id=None, category="policy", available=True, allergens=[], intent="allergy_notice"),
    ),
    KnowledgeDocument(
        title="품절 메뉴 안내 규칙",
        content="품절 메뉴는 검색 결과에서 숨기지 않습니다. 현재 판매 불가 상태와 함께 카탈로그에 등록된 대체 메뉴를 고객에게 안내합니다.",
        source="sold_out",
        chunk_index=0,
        metadata=_metadata("availability", menu_id=None, category="policy", available=True, allergens=[], intent="sold_out_policy"),
    ),
    KnowledgeDocument(
        title="매운 메뉴 추천",
        content="매운맛과 든든한 구성을 원하는 고객에게는 매운 치킨 버거 세트를 추천할 수 있습니다. 주문 전 현재 판매 여부와 옵션은 카탈로그에서 다시 확인합니다.",
        source="recommendation_spicy",
        chunk_index=0,
        metadata=_metadata(
            "recommendation",
            menu_id="burger_spicy_chicken",
            category="burger",
            available=True,
            allergens=["밀", "대두", "계란", "우유"],
            intent="recommendation",
        ),
    ),
    KnowledgeDocument(
        title="매장 주문 정책",
        content="매장 식사와 포장을 선택할 수 있으며 주문 완료 전에는 장바구니를 변경할 수 있습니다. 주문 완료 뒤에는 결제 대기 상태로 전환됩니다.",
        source="store_policy",
        chunk_index=0,
        metadata=_metadata("policy", menu_id=None, category="policy", available=True, allergens=[], intent="store_policy"),
    ),
)
