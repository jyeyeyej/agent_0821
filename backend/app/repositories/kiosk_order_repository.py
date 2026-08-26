"""PostgreSQL에 주문 세션과 장바구니를 저장하는 Part B Repository."""

from typing import Any
from uuid import UUID

from app.core.config import settings
from app.schemas.kiosk_order import CartSelection, OrderCart


class KioskDatabaseError(RuntimeError):
    pass


def _connect() -> Any:
    if not settings.database_url:
        raise KioskDatabaseError("DATABASE_URL is not configured.")
    try:
        import psycopg
        return psycopg.connect(settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1))
    except Exception as error:
        raise KioskDatabaseError("Unable to connect to kiosk database.") from error


def update_cart(args) -> dict:
    """menu_catalog/order_* 테이블을 하나의 DB 트랜잭션에서 갱신한다."""
    with _connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO order_sessions (session_id, status, order_type)
            VALUES (%s, 'active', COALESCE(%s, 'takeout'))
            ON CONFLICT (session_id) DO NOTHING
            """,
            (args.session_id, args.order_type),
        )
        cursor.execute("SELECT status FROM order_sessions WHERE session_id=%s FOR UPDATE", (args.session_id,))
        row = cursor.fetchone()
        if row is None:
            raise KioskDatabaseError("Order session was not created.")
        if row[0] != "active" and args.operation != "ready_for_payment":
            raise ValueError("결제 전 주문 확인이 완료된 장바구니는 변경할 수 없습니다.")

        if args.operation == "clear":
            cursor.execute("DELETE FROM order_cart_items WHERE session_id=%s", (args.session_id,))
        elif args.operation == "remove":
            if not args.cart_item_id:
                raise ValueError("삭제할 cart_item_id가 필요합니다.")
            cursor.execute("DELETE FROM order_cart_items WHERE session_id=%s AND item_id=%s", (args.session_id, args.cart_item_id))
        elif args.operation in ("add", "update"):
            _upsert_item(cursor, args)
        elif args.operation == "ready_for_payment":
            cursor.execute("SELECT COUNT(*) FROM order_cart_items WHERE session_id=%s", (args.session_id,))
            if cursor.fetchone()[0] == 0:
                raise ValueError("빈 장바구니는 주문 완료할 수 없습니다.")
            cursor.execute("UPDATE order_sessions SET status='ready_for_payment' WHERE session_id=%s", (args.session_id,))

        if args.order_type:
            cursor.execute("UPDATE order_sessions SET order_type=%s WHERE session_id=%s", (args.order_type, args.session_id))
        return _read_cart(cursor, args.session_id)


def get_cart(session_id: UUID) -> dict:
    with _connect() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM order_sessions WHERE session_id=%s", (session_id,))
        if cursor.fetchone() is None:
            cursor.execute("INSERT INTO order_sessions (session_id, status, order_type) VALUES (%s, 'active', 'takeout')", (session_id,))
        return _read_cart(cursor, session_id)


def _upsert_item(cursor: Any, args: Any) -> None:
    if not args.menu_id or not args.quantity or not args.selection:
        raise ValueError("메뉴, 수량, 옵션이 필요합니다.")
    cursor.execute(
        """
        SELECT menu_id, name, price, available, allergens, available_options
        FROM menu_catalog WHERE menu_id=%s FOR SHARE
        """,
        (args.menu_id,),
    )
    menu = cursor.fetchone()
    if menu is None:
        raise ValueError("존재하지 않는 메뉴입니다.")
    if not menu[3]:
        raise ValueError("현재 품절된 메뉴입니다.")
    selection = args.selection
    allowed = menu[5] or {}
    order_forms = allowed.get("order_forms", {})
    if order_forms and selection.order_form not in order_forms:
        raise ValueError("선택한 단품/세트 구성을 지원하지 않는 메뉴입니다.")
    if selection.size_up and not allowed.get("size_up"):
        raise ValueError("사이즈업이 불가능한 메뉴입니다.")
    if selection.extra_patty and not allowed.get("extra_patty"):
        raise ValueError("패티 추가가 불가능한 메뉴입니다.")
    if selection.extra_cheese and not allowed.get("extra_cheese"):
        raise ValueError("치즈 추가가 불가능한 메뉴입니다.")
    if selection.drink_id and selection.order_form != "set":
        raise ValueError("음료 변경은 세트에서만 가능합니다.")
    if selection.drink_id and selection.drink_id not in allowed.get("allowed_drinks", []):
        raise ValueError("선택할 수 없는 음료입니다.")
    option_price = _option_price(selection, allowed)
    if args.operation == "update":
        if not args.cart_item_id:
            raise ValueError("수정할 cart_item_id가 필요합니다.")
        from psycopg.types.json import Jsonb
        cursor.execute(
            """UPDATE order_cart_items SET quantity=%s, order_form=%s, selected_options=%s, unit_price=%s, option_price=%s,
               line_total=%s, allergen_snapshot=%s, updated_at=CURRENT_TIMESTAMP WHERE session_id=%s AND item_id=%s""",
            (args.quantity, selection.order_form, Jsonb(selection.model_dump(mode="json")), menu[2], option_price,
             (menu[2] + option_price) * args.quantity, menu[4] or [], args.session_id, args.cart_item_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("수정할 장바구니 항목이 없습니다.")
    else:
        from psycopg.types.json import Jsonb
        cursor.execute(
            """INSERT INTO order_cart_items
               (session_id, menu_id, quantity, order_form, selected_options, unit_price, option_price, line_total, allergen_snapshot)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (args.session_id, menu[0], args.quantity, selection.order_form, Jsonb(selection.model_dump(mode="json")), menu[2],
             option_price, (menu[2] + option_price) * args.quantity, menu[4] or []),
        )


def _option_price(selection: CartSelection, allowed: dict) -> int:
    order_forms = allowed.get("order_forms", {})
    return (
        (order_forms.get("set", 0) if selection.order_form == "set" else 0)
        + (allowed.get("size_up", 0) if selection.size_up else 0)
        + allowed.get("extra_patty", 0) * selection.extra_patty
        + allowed.get("extra_cheese", 0) * selection.extra_cheese
    )


def _read_cart(cursor: Any, session_id: UUID) -> dict:
    cursor.execute("SELECT status, order_type FROM order_sessions WHERE session_id=%s", (session_id,))
    status, order_type = cursor.fetchone()
    cursor.execute(
        """SELECT item_id, item.menu_id, menu.name, item.quantity, item.selected_options, item.unit_price,
                  item.option_price, item.line_total, item.allergen_snapshot
           FROM order_cart_items AS item
           JOIN menu_catalog AS menu ON menu.menu_id = item.menu_id
           WHERE item.session_id=%s ORDER BY item.created_at, item.item_id""", (session_id,)
    )
    items = [
        {"cart_item_id": row[0], "menu_id": row[1], "name": row[2], "quantity": row[3],
         "selection": row[4], "unit_price": row[5], "option_price": row[6],
         "line_total": row[7], "allergens": row[8] or []}
        for row in cursor.fetchall()
    ]
    subtotal = sum(item["line_total"] for item in items)
    return OrderCart(session_id=session_id, status=status, order_type=order_type, items=items,
                     subtotal=subtotal, discount=0, total=subtotal,
                     next_action="select_payment" if status == "ready_for_payment" else "continue_order").model_dump(mode="json")
