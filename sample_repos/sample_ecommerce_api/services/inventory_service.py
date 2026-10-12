"""
Inventory management service handling atomic reservations and restocks.
"""

from typing import Dict, List
from models.entities import Product, OrderItem


class InventoryService:
    """Manages catalog warehouse stock and active cart reservations."""

    def __init__(self):
        self._inventory: Dict[str, Product] = {
            "prod_001": Product("prod_001", "MacBook Pro M3", "LAP-001", 1999.00, 15),
            "prod_002": Product("prod_002", "Wireless Mechanical Keyboard", "ACC-002", 129.50, 40),
            "prod_003": Product("prod_003", "Ergonomic Monitor Arm", "ACC-003", 79.99, 25),
        }
        self._reservations: Dict[str, List[OrderItem]] = {}

    def get_product(self, product_id: str) -> Product:
        product = self._inventory.get(product_id)
        if not product:
            raise KeyError(f"Product {product_id} not found in inventory.")
        return product

    def reserve_stock(self, order_id: str, items: List[OrderItem]) -> bool:
        """Atomically verify and decrement inventory for pending order."""
        # 1. Verify availability for all items first
        for item in items:
            product = self.get_product(item.product_id)
            if not product.has_sufficient_stock(item.quantity):
                return False

        # 2. Decrement quantities
        for item in items:
            product = self.get_product(item.product_id)
            product.stock_quantity -= item.quantity

        self._reservations[order_id] = items
        return True

    def release_reservation(self, order_id: str) -> None:
        """Roll back reserved stock if payment fails or expires."""
        items = self._reservations.pop(order_id, None)
        if not items:
            return
        for item in items:
            product = self._inventory.get(item.product_id)
            if product:
                product.stock_quantity += item.quantity
