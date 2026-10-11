# Local LLM Model Comparison Benchmark

Benchmarked on Phase 8 with OpenAI-compatible `llama-server` runtime.

| Timestamp | Model Name | Server URL | Samples | Avg Latency (s) | Tokens/sec | Valid JSON % | Quality Rating (1-5) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| 2026-10-11 15:14:19 | **mock-eval-model-7b** | `mock-server` | 10 | 0.05s | 1861.6 | 100.0% | *(pending)* |
| 2026-10-11 17:20:19 | **mock-eval-model-7b** | `mock-server` | 10 | 0.05s | 1861.3 | 100.0% | *(pending)* |
| 2026-10-11 17:20:48 | **mock-eval-model-7b** | `mock-server` | 10 | 0.05s | 1862.7 | 100.0% | *(pending)* |

### Instructions to Benchmark Another Model
1. **Stop the active server**: `pkill llama-server`
2. **Launch next candidate GGUF**: `llama-server -m /path/to/another_model.gguf --port 8080 -c 4096 --n-gpu-layers 99`
3. **Run benchmark**: `python scripts/benchmark_models.py`
4. Open `docs/benchmarks/model_comparison.csv` and enter your 1-5 quality rating.
