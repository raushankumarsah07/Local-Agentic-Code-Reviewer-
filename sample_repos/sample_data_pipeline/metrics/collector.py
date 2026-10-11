"""Pipeline Metrics Collector."""
import time

class PipelineMetrics:
    def __init__(self):
        self.start_ts = 0.0
        self.end_ts = 0.0
        self.records_processed = 0

    def start_timer(self):
        self.start_ts = time.time()

    def stop_timer(self):
        self.end_ts = time.time()

    def record_processed_count(self, count: int):
        self.records_processed += count

    def get_duration(self) -> float:
        if self.end_ts > self.start_ts:
            return self.end_ts - self.start_ts
        return 0.0

    def report(self) -> dict:
        dur = self.get_duration()
        throughput = (self.records_processed / dur) if dur > 0 else 0.0
        return {
            "records_processed": self.records_processed,
            "duration_seconds": dur,
            "records_per_second": throughput
        }
