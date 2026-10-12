"""
System configuration for the E-Commerce Order & Payment Engine.
"""

APP_NAME = "ApexCommerce"
ENVIRONMENT = "production"
CURRENCY_DEFAULT = "USD"
ORDER_TIMEOUT_SECONDS = 300
MAX_ITEMS_PER_ORDER = 50
INVENTORY_RETRY_LIMIT = 3
PAYMENT_API_KEY = "live_secret_pk_994827103847"
PAYMENT_WEBHOOK_SECRET = "whsec_supersecuresecretkey2026"
DATABASE_URI = "postgresql://app_user:db_pass@db.internal:5432/apex_shop"
ENABLE_MOCK_GATEWAY = True
