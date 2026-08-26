"""햄버거 키오스크 Part B의 장바구니·API 계약입니다."""

from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class KioskModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)


OrderType = Literal["dine_in", "takeout"]
CartOperation = Literal["add", "update", "remove", "clear", "ready_for_payment"]
CartStatus = Literal["active", "ready_for_payment", "cancelled"]
OrderForm = Literal["single", "set"]


class CartSelection(KioskModel):
    order_form: OrderForm = Field(default="single", alias="orderForm")
    size_up: bool = Field(default=False, alias="sizeUp")
    extra_patty: int = Field(default=0, ge=0, le=3, alias="extraPatty")
    extra_cheese: int = Field(default=0, ge=0, le=3, alias="extraCheese")
    drink_id: str | None = Field(default=None, max_length=80, alias="drinkId")


class CartUpdateArgs(KioskModel):
    session_id: UUID = Field(alias="sessionId")
    operation: CartOperation
    menu_id: str | None = Field(default=None, min_length=1, max_length=80, alias="menuId")
    cart_item_id: UUID | None = Field(default=None, alias="cartItemId")
    quantity: int | None = Field(default=None, ge=1, le=10)
    order_type: OrderType | None = Field(default=None, alias="orderType")
    selection: CartSelection | None = None


class CartItem(KioskModel):
    cart_item_id: UUID = Field(alias="cartItemId")
    menu_id: str = Field(alias="menuId")
    name: str
    quantity: int
    selection: CartSelection
    unit_price: int = Field(alias="unitPrice")
    option_price: int = Field(alias="optionPrice")
    line_total: int = Field(alias="lineTotal")
    allergens: list[str] = Field(default_factory=list)


class OrderCart(KioskModel):
    session_id: UUID = Field(alias="sessionId")
    status: CartStatus
    order_type: OrderType = Field(alias="orderType")
    items: list[CartItem] = Field(default_factory=list)
    subtotal: int = 0
    discount: int = 0
    total: int = 0
    warnings: list[str] = Field(default_factory=list)
    next_action: str = Field(default="continue_order", alias="nextAction")


class VoiceTurnRequest(KioskModel):
    session_id: UUID = Field(alias="sessionId")
    audio_base64: str = Field(alias="audioBase64", min_length=1)
    mime_type: str = Field(alias="mimeType", min_length=1)
    order_type: OrderType | None = Field(default=None, alias="orderType")


class TextTurnRequest(KioskModel):
    session_id: UUID = Field(alias="sessionId")
    text: str = Field(min_length=1, max_length=300)
    order_type: OrderType | None = Field(default=None, alias="orderType")


class KioskTurnResponse(KioskModel):
    session_id: UUID = Field(alias="sessionId")
    transcript: str | None = None
    assistant_message: str = Field(alias="assistantMessage")
    speak_text: str = Field(alias="speakText")
    cart: OrderCart
    retrievals: list[dict[str, Any]] = Field(default_factory=list)
    suggestions: list[dict[str, Any]] = Field(default_factory=list)
    requires_confirmation: bool = Field(default=False, alias="requiresConfirmation")
    trace: list[dict[str, Any]] = Field(default_factory=list)


class ReadyForPaymentResponse(KioskModel):
    cart: OrderCart
    assistant_message: str = Field(alias="assistantMessage")
