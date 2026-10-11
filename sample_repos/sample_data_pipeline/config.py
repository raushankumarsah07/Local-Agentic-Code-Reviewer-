"""Configuration for Data Pipeline ETL."""
import os

PIPELINE_BATCH_SIZE = 500
MAX_RETRIES = 3
DEFAULT_ENCODING = "utf-8"
LOG_LEVEL = "INFO"
DB_CONNECTION_STRING = "sqlite:///pipeline.db"
