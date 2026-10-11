"""Data Transformer module."""
from utils.helpers import sanitize_numeric, normalize_text

class DataTransformer:
    def __init__(self):
        self.drop_nulls = True

    def transform_record(self, record: dict) -> dict:
        transformed = {}
        for k, v in record.items():
            if isinstance(v, (int, float)):
                transformed[k] = sanitize_numeric(v)
            elif isinstance(v, str):
                transformed[k] = normalize_text(v)
            else:
                transformed[k] = v
        transformed["is_valid"] = True
        return transformed

    def transform_batch(self, batch: list) -> list:
        return [self.transform_record(r) for r in batch if r]
