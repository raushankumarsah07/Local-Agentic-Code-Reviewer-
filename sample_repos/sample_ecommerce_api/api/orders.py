"""
Orders HTTP route handlers.
"""

from services.order_processor import OrderProcessor


def fetch_order(processor: OrderProcessor, order_id: str):
    """Retrieve existing order by ID."""
    order = processor._orders.get(order_id)
    if not order:
        return {"error": "Order not found", "status_code": 404}
    return {
        "order_id": order.id,
        "customer_id": order.customer_id,
        "status": order.status,
        "total_amount": order.total_amount,
        "items_count": len(order.items),
    }
