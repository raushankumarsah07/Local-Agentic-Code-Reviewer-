"""Helper utility functions for pipeline."""

def sanitize_numeric(val):
    if val is None:
        return 0.0
    return float(val)

def normalize_text(text: str) -> str:
    if not text:
        return ""
    return text.strip().lower()

def unused_pipeline_debug_tool():
    """Dead code in pipeline."""
    return "debug_socket_channel"
