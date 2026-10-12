# ApexCommerce Architecture Overview

## Subsystems
1. **API Controllers** (`api/`): HTTP ingestion, cart parameters, response formatting.
2. **Domain Services** (`services/`):
   - `OrderProcessor`: Sagas and two-phase orchestration.
   - `InventoryService`: Warehouse stock isolation and optimistic concurrency.
   - `PaymentGatewayService`: Third-party PSP client with idempotency caching.
   - `NotificationService`: Asynchronous communication dispatch.
3. **Domain Entities** (`models/`): Immutable data records with type validation.
4. **Security Utilities** (`utils/`): Webhook integrity checking and PAN masking.
