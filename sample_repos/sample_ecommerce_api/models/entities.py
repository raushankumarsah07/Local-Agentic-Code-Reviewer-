"""
Domain entity models representing catalog, order, and payment entities.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
import uuid


@dataclass
class Product:
    """Store catalog item with inventory counts."""
    id: str
    name: str
    sku: str
    price: float
    stock_quantity: int
    is_active: bool = True

    def has_sufficient_stock(self, requested: int) -> bool:
        """Check if stock level satisfies requested amount."""
        return self.is_active and self.stock_quantity >= requested


@dataclass
class Customer:
    """Registered customer entity."""
    id: str
    email: str
    full_name: str
    tier: str = "standard"


@dataclass
class OrderItem:
    """Line item in a customer order."""
    product_id: str
    quantity: int
    unit_price: float

    @property
    def subtotal(self) -> float:
        return round(self.quantity * self.unit_price, 2)


@dataclass
class Order:
    """Customer order containing line items and fulfillment status."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    customer_id: str = ""
    items: List[OrderItem] = field(default_factory=list)
    status: str = "PENDING"  # PENDING, PAID, SHIPPED, CANCELLED
    total_amount: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)

    def calculate_total(self) -> float:
        self.total_amount = round(sum(item.subtotal for item in self.items), 2)
        return self.total_amount


@dataclass
class PaymentRecord:
    """Financial transaction ledger record."""
    transaction_id: str
    order_id: str
    amount: float
    currency: str
    status: str  # SUCCESS, FAILED, REFUNDED
    idempotency_key: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
