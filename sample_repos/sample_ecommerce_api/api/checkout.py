"""
Checkout endpoint coordinator.
"""

from typing import List
from models.entities import OrderItem
from services.order_processor import OrderProcessor


def handle_checkout(
    processor: OrderProcessor,
    customer_id: str,
    email: str,
    cart_items: List[dict],
    idempotency_key: str,
):
    """Process incoming checkout cart payload."""
    items = [
        OrderItem(
            product_id=it["product_id"],
            quantity=it["quantity"],
            unit_price=it["unit_price"],
        )
        for it in cart_items
    ]
    order = processor.place_order(customer_id, email, items, idempotency_key)
    return {
        "order_id": order.id,
        "status": order.status,
        "total_amount": order.total_amount,
    }
