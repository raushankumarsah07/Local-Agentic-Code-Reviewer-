"""
Notification dispatch service for customer receipts and alert notifications.
"""

from models.entities import Order


class NotificationService:
    """Dispatches order updates via email and webhook triggers."""

    def send_order_confirmation(self, customer_email: str, order: Order) -> bool:
        print(f"Receipt dispatched to {customer_email}: Order #{order.id} for ${order.total_amount:.2f}")
        return True

    def send_cancellation_alert(self, customer_email: str, order_id: str, reason: str) -> bool:
        print(f"Cancellation alert sent to {customer_email}: Order #{order_id}. Reason: {reason}")
        return True
