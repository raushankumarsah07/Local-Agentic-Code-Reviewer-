"""Data Extractor module."""
import csv
import os

class DataExtractor:
    def __init__(self, source_path: str):
        self.source_path = source_path

    def extract(self, limit: int = 1000) -> list:
        records = []
        if not os.path.exists(self.source_path):
            return [{"id": i, "val": i * 1.5, "status": "raw"} for i in range(min(10, limit))]
        with open(self.source_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader):
                if idx >= limit:
                    break
                records.append(row)
        return records
