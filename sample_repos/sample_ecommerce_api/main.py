"""
ApexCommerce Microservice Main Application Entrypoint.
"""

from services.inventory_service import InventoryService
from services.payment_gateway import PaymentGatewayService
from services.notification_service import NotificationService
from services.order_processor import OrderProcessor
from api.checkout import handle_checkout
from api.products import list_catalog


def build_application_context():
    """Wire up dependencies and services."""
    inventory_svc = InventoryService()
    payment_svc = PaymentGatewayService()
    notify_svc = NotificationService()
    processor = OrderProcessor(inventory_svc, payment_svc, notify_svc)
    return {
        "inventory": inventory_svc,
        "payment": payment_svc,
        "notify": notify_svc,
        "processor": processor,
    }


def main():
    ctx = build_application_context()
    print("Catalog products:")
    catalog = list_catalog(ctx["inventory"])
    for item in catalog:
        print(f" - {item['name']} (${item['price']})")

    print("\nExecuting sample checkout...")
    res = handle_checkout(
        processor=ctx["processor"],
        customer_id="cust_8821",
        email="shopper@example.com",
        cart_items=[
            {"product_id": "prod_001", "quantity": 1, "unit_price": 1999.00},
            {"product_id": "prod_002", "quantity": 2, "unit_price": 129.50},
        ],
        idempotency_key="checkout_nonce_481029",
    )
    print(f"Checkout Result: {res}")


if __name__ == "__main__":
    main()
