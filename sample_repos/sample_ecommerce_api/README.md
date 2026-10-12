# E-Commerce Order & Payment Microservice

A modular backend microservice demonstrating enterprise-grade order management, distributed payments, inventory reservation, and webhook event processing.

## Architecture Highlights
- **Layered Clean Architecture**: API route controllers, domain service managers, and data entities.
- **Inventory Concurrency**: Atomic reservation and rollback on transaction failure.
- **Payment Gateway**: Gateway abstraction with idempotency tokens and webhook verification.
