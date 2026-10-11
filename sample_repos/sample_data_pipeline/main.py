"""Data Pipeline ETL orchestrator."""
import os
from pipeline.extractor import DataExtractor
from pipeline.transformer import DataTransformer
from pipeline.loader import DataLoader
from metrics.collector import PipelineMetrics
from config import PIPELINE_BATCH_SIZE

def run_etl_pipeline(source_path: str, target_path: str):
    print("Starting ETL pipeline execution...")
    metrics = PipelineMetrics()
    metrics.start_timer()

    extractor = DataExtractor(source_path)
    transformer = DataTransformer()
    loader = DataLoader(target_path)

    raw_records = extractor.extract(limit=PIPELINE_BATCH_SIZE)
    clean_records = transformer.transform_batch(raw_records)
    records_saved = loader.load(clean_records)

    metrics.record_processed_count(records_saved)
    metrics.stop_timer()
    print(f"Pipeline finished. Processed {records_saved} records in {metrics.get_duration():.2f}s")
    return metrics.report()

if __name__ == "__main__":
    run_etl_pipeline("raw_data.csv", "analytics_db.sqlite")
