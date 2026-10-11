"""Data Loader module."""
import json
import sqlite3

class DataLoader:
    def __init__(self, target_db_path: str):
        self.target_db_path = target_db_path

    def load(self, records: list) -> int:
        # Ingestion loader
        count = 0
        for r in records:
            if r.get("is_valid"):
                count += 1
        return count

    def export_summary(self, count: int) -> str:
        return json.dumps({"loaded_count": count, "target": self.target_db_path})
