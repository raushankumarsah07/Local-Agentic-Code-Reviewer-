"""
Order orchestrator coordinating inventory, payments, and fulfillment events.
"""

from typing import Dict, List
from models.entities import Order, OrderItem
from services.inventory_service import InventoryService
from services.payment_gateway import PaymentGatewayService
from services.notification_service import NotificationService
from utils.validators import validate_order_item_quantities


class OrderProcessor:
    """End-to-end checkout pipeline executor."""

    def __init__(
        self,
        inventory_svc: InventoryService,
        payment_svc: PaymentGatewayService,
        notify_svc: NotificationService,
    ):
        self.inventory = inventory_svc
        self.payment = payment_svc
        self.notify = notify_svc
        self._orders: Dict[str, Order] = {}

    def place_order(
        self,
        customer_id: str,
        customer_email: str,
        items: List[OrderItem],
        idempotency_key: str,
    ) -> Order:
        """Execute atomic order checkout."""
        if not validate_order_item_quantities(items):
            raise ValueError("Invalid item list or cart limit exceeded.")

        order = Order(customer_id=customer_id, items=items)
        order.calculate_total()

        # Step 1: Inventory Reservation
        reserved = self.inventory.reserve_stock(order.id, items)
        if not reserved:
            order.status = "OUT_OF_STOCK"
            self.notify.send_cancellation_alert(customer_email, order.id, "Insufficient stock")
            return order

        # Step 2: Payment Execution
        try:
            payment_txn = self.payment.charge(
                order_id=order.id,
                amount=order.total_amount,
                idempotency_key=idempotency_key,
            )
            order.status = "PAID"
            self._orders[order.id] = order
            self.notify.send_order_confirmation(customer_email, order)
        except Exception as e:
            # Roll back reserved inventory on payment failure
            self.inventory.release_reservation(order.id)
            order.status = "PAYMENT_FAILED"
            self.notify.send_cancellation_alert(customer_email, order.id, str(e))

        return order
