"""검증된 주문 변경만 PostgreSQL 장바구니에 반영하는 Tool."""

from app.repositories.kiosk_order_repository import update_cart
from app.schemas.kiosk_order import CartUpdateArgs


def update_order_cart(args: CartUpdateArgs) -> dict:
    return update_cart(args)
