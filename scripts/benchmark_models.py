#!/usr/bin/env python3
"""
scripts/benchmark_models.py

Local LLM Benchmark Script for Phase 8.
Evaluates local llama.cpp models on explaining code findings.

Measures:
- Latency (response time in seconds)
- Generation speed (tokens per second)
- Valid JSON rate before retry (schema conformance)
- Exports results to CSV and Markdown table
- Leaves empty column for manual 1-5 quality rating
- Instructs developer on how to restart llama-server with a different model.
"""

import argparse
import asyncio
import csv
import datetime
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root and backend to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT))

import httpx
from app.config import get_settings
from app.db.models import Finding
from app.db.session import SessionLocal
from app.llm.client import LlamaCppClient
from app.llm.prompts import build_explanation_prompt, strip_thinking_tags
from app.llm.schemas import FindingExplanation

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("model_benchmark")


def export_sample_findings(output_path: Path, limit: int = 10) -> List[Dict[str, Any]]:
    """Export sample findings from SQLite DB into a JSON benchmark set."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    session = SessionLocal()
    try:
        db_findings = session.query(Finding).limit(limit).all()
        sample_list = []
        for f in db_findings:
            sample_list.append({
                "id": f.id,
                "project_id": f.project_id,
                "type": f.type,
                "severity": f.severity,
                "title": f.title,
                "file": f.file,
                "start_line": f.start_line,
                "end_line": f.end_line,
                "source_tool": f.source_tool,
                "evidence_snippet": f.evidence_snippet or "",
            })
        
        # If DB had no findings, create standard diverse test fixtures
        if not sample_list:
            logger.info("No findings in database; generating 10 diverse benchmark test fixtures...")
            sample_list = [
                {
                    "id": 101,
                    "project_id": "fixture_proj",
                    "type": "complexity",
                    "severity": "Medium",
                    "title": "High Cyclomatic Complexity in calculate_total (CC=14)",
                    "file": "calculator.py",
                    "start_line": 45,
                    "end_line": 95,
                    "source_tool": "mccabe",
                    "evidence_snippet": "def calculate_total(items, discount, tax, currency):\n    # 14 branches\n    pass",
                },
                {
                    "id": 102,
                    "project_id": "fixture_proj",
                    "type": "security",
                    "severity": "Critical",
                    "title": "Use of dangerous eval() with untrusted user input",
                    "file": "eval_util.py",
                    "start_line": 12,
                    "end_line": 15,
                    "source_tool": "ast_security",
                    "evidence_snippet": "def run_expression(expr):\n    return eval(expr)",
                },
                {
                    "id": 103,
                    "project_id": "fixture_proj",
                    "type": "security",
                    "severity": "High",
                    "title": "Potential SQL injection via raw string formatting",
                    "file": "db_query.py",
                    "start_line": 28,
                    "end_line": 30,
                    "source_tool": "ast_security",
                    "evidence_snippet": "query = f'SELECT * FROM users WHERE user_id = {user_id}'\ncursor.execute(query)",
                },
                {
                    "id": 104,
                    "project_id": "fixture_proj",
                    "type": "dead_code",
                    "severity": "Low",
                    "title": "Unreachable candidate function unused_formatter",
                    "file": "formatters.py",
                    "start_line": 5,
                    "end_line": 15,
                    "source_tool": "vulture",
                    "evidence_snippet": "def unused_formatter(data):\n    return f'Formatted: {data}'",
                },
                {
                    "id": 105,
                    "project_id": "fixture_proj",
                    "type": "cycle",
                    "severity": "High",
                    "title": "Circular module dependency detected: auth -> session -> auth",
                    "file": "auth.py",
                    "start_line": 1,
                    "end_line": 10,
                    "source_tool": "tarjan",
                    "evidence_snippet": "import session\n\ndef login():\n    session.start()",
                },
                {
                    "id": 106,
                    "project_id": "fixture_proj",
                    "type": "coupling",
                    "severity": "Medium",
                    "title": "God Module detected with high fan-out (out-degree=18)",
                    "file": "monolith_helper.py",
                    "start_line": 1,
                    "end_line": 120,
                    "source_tool": "coupling_analyzer",
                    "evidence_snippet": "# Module imports 18 internal and external modules",
                },
                {
                    "id": 107,
                    "project_id": "fixture_proj",
                    "type": "security",
                    "severity": "Critical",
                    "title": "subprocess invoked with shell=True",
                    "file": "runner.py",
                    "start_line": 18,
                    "end_line": 22,
                    "source_tool": "ast_security",
                    "evidence_snippet": "cmd = f'ping {host}'\nsubprocess.run(cmd, shell=True)",
                },
                {
                    "id": 108,
                    "project_id": "fixture_proj",
                    "type": "complexity",
                    "severity": "Low",
                    "title": "Function exceeds recommended line limit (length=62 lines)",
                    "file": "parser.py",
                    "start_line": 80,
                    "end_line": 142,
                    "source_tool": "length_analyzer",
                    "evidence_snippet": "def parse_raw_packet(stream):\n    # 62 lines of procedural steps\n    pass",
                },
                {
                    "id": 109,
                    "project_id": "fixture_proj",
                    "type": "security",
                    "severity": "High",
                    "title": "Hardcoded secret or authentication token detected",
                    "file": "client.py",
                    "start_line": 8,
                    "end_line": 10,
                    "source_tool": "ast_security",
                    "evidence_snippet": "API_SECRET = 'ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456'",
                },
                {
                    "id": 110,
                    "project_id": "fixture_proj",
                    "type": "dead_code",
                    "severity": "Low",
                    "title": "Unused class helper InternalBufferCache",
                    "file": "cache.py",
                    "start_line": 40,
                    "end_line": 70,
                    "source_tool": "reachability",
                    "evidence_snippet": "class InternalBufferCache:\n    pass",
                },
            ]

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(sample_list, f, indent=2)
        logger.info("Exported %d sample findings to %s", len(sample_list), output_path)
        return sample_list
    finally:
        session.close()


async def detect_model_name(base_url: str) -> str:
    """Detect the currently loaded model on llama-server via /v1/models."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{base_url.rstrip('/')}/models")
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data and len(data["data"]) > 0:
                    model_id = data["data"][0].get("id")
                    if model_id:
                        return model_id
    except Exception:
        pass
    return "unknown_model"


async def run_benchmark(
    findings_file: Path,
    base_url: str,
    override_model: Optional[str] = None,
    mock: bool = False,
) -> Dict[str, Any]:
    """Execute evaluation over sample findings and collect performance metrics."""
    settings = get_settings()

    if not findings_file.exists():
        logger.info("Sample file %s not found. Auto-generating...", findings_file)
        sample_findings = export_sample_findings(findings_file, limit=10)
    else:
        with open(findings_file, "r", encoding="utf-8") as f:
            sample_findings = json.load(f)

    if not sample_findings:
        raise ValueError(f"No findings found in {findings_file}")

    # Determine active model name
    if override_model:
        model_name = override_model
    elif mock:
        model_name = "mock-eval-model-7b"
    else:
        detected = await detect_model_name(base_url)
        model_name = detected if detected != "unknown_model" else settings.LLM_MODEL

    logger.info("Starting Benchmark for Model: %s against %s", model_name, base_url)
    logger.info("Evaluating %d findings sequentially...", len(sample_findings))

    client = LlamaCppClient(settings)
    schema = FindingExplanation.model_json_schema()

    total_time = 0.0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    valid_json_first_pass = 0
    individual_results = []

    for idx, f in enumerate(sample_findings, start=1):
        messages = build_explanation_prompt(
            finding_title=f["title"],
            finding_type=f["type"],
            severity=f["severity"],
            file_path=f["file"],
            start_line=f["start_line"],
            end_line=f["end_line"],
            code_snippet=f.get("evidence_snippet", "# code context"),
            source_tool=f.get("source_tool", "analyzer"),
            context_size=settings.LLM_CONTEXT_SIZE,
        )

        logger.info("[%d/%d] Testing finding %s: %s", idx, len(sample_findings), f["id"], f["title"][:40])

        if mock:
            # Simulated local response for offline validation
            t0 = time.perf_counter()
            await asyncio.sleep(0.05)
            latency_s = time.perf_counter() - t0
            p_toks = 180
            c_toks = 95
            is_valid = True
            tps = c_toks / latency_s if latency_s > 0 else 0.0
        else:
            t0 = time.perf_counter()
            response = await client.chat(
                messages=messages,
                schema=schema,
                temperature=settings.LLM_TEMPERATURE,
            )
            latency_s = time.perf_counter() - t0
            p_toks = response.prompt_tokens
            c_toks = response.completion_tokens
            tps = response.tokens_per_second

            # Test JSON validity on first pass without retry
            try:
                cleaned = strip_thinking_tags(response.content)
                parsed = json.loads(cleaned)
                FindingExplanation.model_validate(parsed)
                is_valid = True
            except Exception:
                is_valid = False

        if is_valid:
            valid_json_first_pass += 1

        total_time += latency_s
        total_prompt_tokens += p_toks
        total_completion_tokens += c_toks

        individual_results.append({
            "finding_id": f["id"],
            "title": f["title"],
            "latency_s": round(latency_s, 2),
            "tokens_per_sec": round(tps, 1),
            "valid_first_pass": is_valid,
        })

    n = len(sample_findings)
    avg_latency = round(total_time / n, 2)
    avg_tps = round(total_completion_tokens / total_time, 1) if total_time > 0 else 0.0
    valid_rate_pct = round((valid_json_first_pass / n) * 100.0, 1)

    benchmark_summary = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model_name": model_name,
        "base_url": base_url if not mock else "mock-server",
        "num_findings": n,
        "avg_latency_s": avg_latency,
        "tokens_per_second": avg_tps,
        "valid_json_rate_pct": valid_rate_pct,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "manual_quality_rating_1_to_5": "",  # Empty for manual human evaluation
    }

    return benchmark_summary


def save_results(
    summary: Dict[str, Any],
    csv_path: Path,
    md_path: Path,
):
    """Append summary to CSV and update Markdown benchmark table."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Update CSV
    fieldnames = [
        "timestamp",
        "model_name",
        "base_url",
        "num_findings",
        "avg_latency_s",
        "tokens_per_second",
        "valid_json_rate_pct",
        "manual_quality_rating_1_to_5",
    ]
    file_exists = csv_path.exists() and csv_path.stat().st_size > 0

    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        writer.writerow(summary)

    logger.info("Saved benchmark row to %s", csv_path)

    # 2. Re-render Markdown comparison table from CSV
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    md_lines = [
        "# Local LLM Model Comparison Benchmark",
        "",
        "Benchmarked on Phase 8 with OpenAI-compatible `llama-server` runtime.",
        "",
        "| Timestamp | Model Name | Server URL | Samples | Avg Latency (s) | Tokens/sec | Valid JSON % | Quality Rating (1-5) |",
        "| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |",
    ]
    for r in rows:
        md_lines.append(
            f"| {r.get('timestamp')} | **{r.get('model_name')}** | `{r.get('base_url')}` | "
            f"{r.get('num_findings')} | {r.get('avg_latency_s')}s | {r.get('tokens_per_second')} | "
            f"{r.get('valid_json_rate_pct')}% | {r.get('manual_quality_rating_1_to_5') or '*(pending)*'} |"
        )

    md_lines.append("")
    md_lines.append("### Instructions to Benchmark Another Model")
    md_lines.append("1. **Stop the active server**: `pkill llama-server`")
    md_lines.append("2. **Launch next candidate GGUF**: `llama-server -m /path/to/another_model.gguf --port 8080 -c 4096 --n-gpu-layers 99`")
    md_lines.append("3. **Run benchmark**: `python scripts/benchmark_models.py`")
    md_lines.append("4. Open `docs/benchmarks/model_comparison.csv` and enter your 1-5 quality rating.")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    logger.info("Updated benchmark Markdown table at %s", md_path)


def print_switch_instructions():
    """Print developer instructions for swapping models on llama-server."""
    banner = """
================================================================================
MODEL SWITCHING INSTRUCTIONS FOR BENCHMARKING:
================================================================================
Since you run one local model at a time (laptop memory budget), follow these steps
to benchmark different candidate models:

1. Stop the current llama-server:
   pkill llama-server
   # or press Ctrl+C in the terminal running llama-server

2. Start llama-server with your next candidate model:
   llama-server -m /path/to/Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf --port 8080 -c 4096 --n-gpu-layers 99

   # Other candidates examples:
   # llama-server -m /path/to/Llama-3.2-3B-Instruct-Q4_K_M.gguf --port 8080 -c 4096
   # llama-server -m /path/to/DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf --port 8080 -c 4096

3. Re-run this benchmark script:
   python scripts/benchmark_models.py

4. Results will automatically append to:
   - docs/benchmarks/model_comparison.csv (fill in your 1-5 quality rating)
   - docs/benchmarks/model_comparison.md
================================================================================
"""
    print(banner)


def main():
    parser = argparse.ArgumentParser(description="Benchmark local LLM models on static analysis findings")
    parser.add_argument("--findings-file", default=str(PROJECT_ROOT / "docs" / "benchmarks" / "sample_findings.json"))
    parser.add_argument("--export-from-db", action="store_true", help="Export 10 findings from SQLite database")
    parser.add_argument("--base-url", default=None, help="Base URL of llama-server (default: from .env)")
    parser.add_argument("--model-name", default=None, help="Override model name label")
    parser.add_argument("--output-csv", default=str(PROJECT_ROOT / "docs" / "benchmarks" / "model_comparison.csv"))
    parser.add_argument("--output-md", default=str(PROJECT_ROOT / "docs" / "benchmarks" / "model_comparison.md"))
    parser.add_argument("--mock", action="store_true", help="Run with simulated mock responses for test verification")
    args = parser.parse_args()

    settings = get_settings()
    base_url = args.base_url or settings.LLM_BASE_URL
    findings_file = Path(args.findings_file)
    csv_path = Path(args.output_csv)
    md_path = Path(args.output_md)

    if args.export_from_db or not findings_file.exists():
        export_sample_findings(findings_file, limit=10)

    summary = asyncio.run(
        run_benchmark(
            findings_file=findings_file,
            base_url=base_url,
            override_model=args.model_name,
            mock=args.mock,
        )
    )

    save_results(summary, csv_path, md_path)

    print("\nBENCHMARK RUN COMPLETE:")
    print(f"• Model: {summary['model_name']}")
    print(f"• Samples: {summary['num_findings']}")
    print(f"• Avg Latency: {summary['avg_latency_s']}s")
    print(f"• Generation Speed: {summary['tokens_per_second']} tokens/sec")
    print(f"• Valid JSON Rate (First Pass): {summary['valid_json_rate_pct']}%")

    print_switch_instructions()


if __name__ == "__main__":
    main()
