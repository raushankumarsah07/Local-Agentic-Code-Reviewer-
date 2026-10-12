"""
Products HTTP routing and controller methods.
"""

from services.inventory_service import InventoryService


def list_catalog(inventory_svc: InventoryService):
    """Retrieve catalog products."""
    return [
        {
            "id": p.id,
            "name": p.name,
            "sku": p.sku,
            "price": p.price,
            "in_stock": p.stock_quantity > 0,
        }
        for p in inventory_svc._inventory.values()
    ]


def get_product_detail(inventory_svc: InventoryService, product_id: str):
    """Retrieve single product by identifier."""
    return inventory_svc.get_product(product_id)
