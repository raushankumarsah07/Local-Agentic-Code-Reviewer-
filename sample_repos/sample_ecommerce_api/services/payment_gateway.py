"""
Payment processing service interfacing with mock payment gateways (Stripe/PayPal).
"""

import uuid
from typing import Dict
from config import CURRENCY_DEFAULT, PAYMENT_API_KEY
from models.entities import PaymentRecord


class PaymentGatewayService:
    """Processes charges with idempotency checks and ledger logging."""

    def __init__(self):
        self._ledger: Dict[str, PaymentRecord] = {}
        self._idempotency_cache: Dict[str, str] = {}

    def charge(
        self,
        order_id: str,
        amount: float,
        idempotency_key: str,
        currency: str = CURRENCY_DEFAULT,
    ) -> PaymentRecord:
        """Execute charge with idempotency protection."""
        if idempotency_key in self._idempotency_cache:
            txn_id = self._idempotency_cache[idempotency_key]
            return self._ledger[txn_id]

        if amount <= 0:
            raise ValueError("Charge amount must be positive.")

        # Simulate authorization through merchant API
        txn_id = f"txn_{uuid.uuid4().hex[:12]}"
        record = PaymentRecord(
            transaction_id=txn_id,
            order_id=order_id,
            amount=amount,
            currency=currency,
            status="SUCCESS",
            idempotency_key=idempotency_key,
        )

        self._ledger[txn_id] = record
        self._idempotency_cache[idempotency_key] = txn_id
        return record

    def refund(self, transaction_id: str) -> PaymentRecord:
        record = self._ledger.get(transaction_id)
        if not record:
            raise KeyError(f"Transaction {transaction_id} not found.")
        record.status = "REFUNDED"
        return record
