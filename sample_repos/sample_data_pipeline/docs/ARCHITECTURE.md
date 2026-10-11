# Architecture & Repository Documentation: sample_data_pipeline

> **Generated automatically by Local Agentic Code Reviewer**  
> *Timestamp: 2026-10-11T14:07:22.707327+00:00*  

## 1. Executive Overview

- **Project Name:** `sample_data_pipeline`
- **Total Scanned Files:** 29
- **Total Source Lines:** 669
- **Classes Identified:** 36
- **Functions & Methods:** 36
- **Identified Entry Points:** `main.py`

## 2. Architecture & Subsystem Modules

The repository is structured into the following architectural modules:

| Module / Directory | Role & Responsibility | Files | Lines | Exported Symbols |
| :--- | :--- | :--- | :--- | :--- |
| `docs` | Subsystem handling docs utilities and business components | 2 | 225 | — |
| `metrics` | Subsystem handling metrics utilities and business components | 6 | 102 | `PipelineMetrics`, `PipelineMetrics`, `PipelineMetrics`, `PipelineMetrics` |
| `pipeline` | Subsystem handling pipeline utilities and business components | 12 | 189 | `DataExtractor`, `DataExtractor`, `DataExtractor`, `DataExtractor` |
| `root` | Core root application entry & scripts | 6 | 108 | `run_etl_pipeline`, `run_etl_pipeline`, `run_etl_pipeline`, `run_etl_pipeline` |
| `utils` | Subsystem handling utils utilities and business components | 3 | 45 | `sanitize_numeric`, `sanitize_numeric`, `sanitize_numeric`, `normalize_text` |

## 3. Detailed Component Catalog

### `config.py`
- **Language:** Python | **Lines:** 8
- **Summary:** Source code file or configuration
- **Dependencies / Imports:** `os`

### `config.py`
- **Language:** Python | **Lines:** 8
- **Summary:** Source code file or configuration
- **Dependencies / Imports:** `os`

### `config.py`
- **Language:** Python | **Lines:** 8
- **Summary:** Source code file or configuration
- **Dependencies / Imports:** `os`

### `docs/ARCHITECTURE.md`
- **Language:** Markdown | **Lines:** 85
- **Summary:** Source code file or configuration

### `docs/ARCHITECTURE.md`
- **Language:** Markdown | **Lines:** 140
- **Summary:** Source code file or configuration

### `main.py`
- **Language:** Python | **Lines:** 28
- **Summary:** Provides implementation for run_etl_pipeline, run_etl_pipeline, run_etl_pipeline
- **Functions:** `run_etl_pipeline` (L9-25), `run_etl_pipeline` (L9-25), `run_etl_pipeline` (L9-25)
- **Dependencies / Imports:** `DataExtractor`, `DataLoader`, `DataTransformer`, `PIPELINE_BATCH_SIZE`, `PipelineMetrics`, `os`

### `main.py`
- **Language:** Python | **Lines:** 28
- **Summary:** Provides implementation for run_etl_pipeline, run_etl_pipeline, run_etl_pipeline
- **Functions:** `run_etl_pipeline` (L9-25), `run_etl_pipeline` (L9-25), `run_etl_pipeline` (L9-25)
- **Dependencies / Imports:** `DataExtractor`, `DataLoader`, `DataTransformer`, `PIPELINE_BATCH_SIZE`, `PipelineMetrics`, `os`

### `main.py`
- **Language:** Python | **Lines:** 28
- **Summary:** Provides implementation for run_etl_pipeline, run_etl_pipeline, run_etl_pipeline
- **Functions:** `run_etl_pipeline` (L9-25), `run_etl_pipeline` (L9-25), `run_etl_pipeline` (L9-25)
- **Dependencies / Imports:** `DataExtractor`, `DataLoader`, `DataTransformer`, `PIPELINE_BATCH_SIZE`, `PipelineMetrics`, `os`

### `metrics/__init__.py`
- **Language:** Python | **Lines:** 3
- **Summary:** Source code file or configuration
- **Dependencies / Imports:** `PipelineMetrics`

### `metrics/__init__.py`
- **Language:** Python | **Lines:** 3
- **Summary:** Source code file or configuration
- **Dependencies / Imports:** `PipelineMetrics`

### `metrics/__init__.py`
- **Language:** Python | **Lines:** 3
- **Summary:** Source code file or configuration
- **Dependencies / Imports:** `PipelineMetrics`

### `metrics/collector.py`
- **Language:** Python | **Lines:** 31
- **Summary:** Provides implementation for PipelineMetrics, PipelineMetrics, PipelineMetrics
- **Classes:** `PipelineMetrics` (L4-31), `PipelineMetrics` (L4-31), `PipelineMetrics` (L4-31)
- **Dependencies / Imports:** `time`

### `metrics/collector.py`
- **Language:** Python | **Lines:** 31
- **Summary:** Provides implementation for PipelineMetrics, PipelineMetrics, PipelineMetrics
- **Classes:** `PipelineMetrics` (L4-31), `PipelineMetrics` (L4-31), `PipelineMetrics` (L4-31)
- **Dependencies / Imports:** `time`

### `metrics/collector.py`
- **Language:** Python | **Lines:** 31
- **Summary:** Provides implementation for PipelineMetrics, PipelineMetrics, PipelineMetrics
- **Classes:** `PipelineMetrics` (L4-31), `PipelineMetrics` (L4-31), `PipelineMetrics` (L4-31)
- **Dependencies / Imports:** `time`

### `pipeline/__init__.py`
- **Language:** Python | **Lines:** 5
- **Summary:** Source code file or configuration
- **Dependencies / Imports:** `DataExtractor`, `DataLoader`, `DataTransformer`

### `pipeline/__init__.py`
- **Language:** Python | **Lines:** 5
- **Summary:** Source code file or configuration
- **Dependencies / Imports:** `DataExtractor`, `DataLoader`, `DataTransformer`

### `pipeline/__init__.py`
- **Language:** Python | **Lines:** 5
- **Summary:** Source code file or configuration
- **Dependencies / Imports:** `DataExtractor`, `DataLoader`, `DataTransformer`

### `pipeline/extractor.py`
- **Language:** Python | **Lines:** 19
- **Summary:** Provides implementation for DataExtractor, DataExtractor, DataExtractor
- **Classes:** `DataExtractor` (L5-19), `DataExtractor` (L5-19), `DataExtractor` (L5-19)
- **Dependencies / Imports:** `csv`, `os`

### `pipeline/extractor.py`
- **Language:** Python | **Lines:** 19
- **Summary:** Provides implementation for DataExtractor, DataExtractor, DataExtractor
- **Classes:** `DataExtractor` (L5-19), `DataExtractor` (L5-19), `DataExtractor` (L5-19)
- **Dependencies / Imports:** `csv`, `os`

### `pipeline/extractor.py`
- **Language:** Python | **Lines:** 19
- **Summary:** Provides implementation for DataExtractor, DataExtractor, DataExtractor
- **Classes:** `DataExtractor` (L5-19), `DataExtractor` (L5-19), `DataExtractor` (L5-19)
- **Dependencies / Imports:** `csv`, `os`

### `pipeline/loader.py`
- **Language:** Python | **Lines:** 18
- **Summary:** Provides implementation for DataLoader, DataLoader, DataLoader
- **Classes:** `DataLoader` (L5-18), `DataLoader` (L5-18), `DataLoader` (L5-18)
- **Dependencies / Imports:** `json`, `sqlite3`

### `pipeline/loader.py`
- **Language:** Python | **Lines:** 18
- **Summary:** Provides implementation for DataLoader, DataLoader, DataLoader
- **Classes:** `DataLoader` (L5-18), `DataLoader` (L5-18), `DataLoader` (L5-18)
- **Dependencies / Imports:** `json`, `sqlite3`

### `pipeline/loader.py`
- **Language:** Python | **Lines:** 18
- **Summary:** Provides implementation for DataLoader, DataLoader, DataLoader
- **Classes:** `DataLoader` (L5-18), `DataLoader` (L5-18), `DataLoader` (L5-18)
- **Dependencies / Imports:** `json`, `sqlite3`

### `pipeline/transformer.py`
- **Language:** Python | **Lines:** 21
- **Summary:** Provides implementation for DataTransformer, DataTransformer, DataTransformer
- **Classes:** `DataTransformer` (L4-21), `DataTransformer` (L4-21), `DataTransformer` (L4-21)
- **Dependencies / Imports:** `normalize_text`, `sanitize_numeric`

### `pipeline/transformer.py`
- **Language:** Python | **Lines:** 21
- **Summary:** Provides implementation for DataTransformer, DataTransformer, DataTransformer
- **Classes:** `DataTransformer` (L4-21), `DataTransformer` (L4-21), `DataTransformer` (L4-21)
- **Dependencies / Imports:** `normalize_text`, `sanitize_numeric`

### `pipeline/transformer.py`
- **Language:** Python | **Lines:** 21
- **Summary:** Provides implementation for DataTransformer, DataTransformer, DataTransformer
- **Classes:** `DataTransformer` (L4-21), `DataTransformer` (L4-21), `DataTransformer` (L4-21)
- **Dependencies / Imports:** `normalize_text`, `sanitize_numeric`

### `utils/helpers.py`
- **Language:** Python | **Lines:** 15
- **Summary:** Provides implementation for sanitize_numeric, sanitize_numeric, sanitize_numeric, normalize_text, normalize_text, normalize_text, unused_pipeline_debug_tool, unused_pipeline_debug_tool, unused_pipeline_debug_tool
- **Functions:** `sanitize_numeric` (L3-6), `sanitize_numeric` (L3-6), `sanitize_numeric` (L3-6), `normalize_text` (L8-11), `normalize_text` (L8-11), `normalize_text` (L8-11), `unused_pipeline_debug_tool` (L13-15), `unused_pipeline_debug_tool` (L13-15), `unused_pipeline_debug_tool` (L13-15)

### `utils/helpers.py`
- **Language:** Python | **Lines:** 15
- **Summary:** Provides implementation for sanitize_numeric, sanitize_numeric, sanitize_numeric, normalize_text, normalize_text, normalize_text, unused_pipeline_debug_tool, unused_pipeline_debug_tool, unused_pipeline_debug_tool
- **Functions:** `sanitize_numeric` (L3-6), `sanitize_numeric` (L3-6), `sanitize_numeric` (L3-6), `normalize_text` (L8-11), `normalize_text` (L8-11), `normalize_text` (L8-11), `unused_pipeline_debug_tool` (L13-15), `unused_pipeline_debug_tool` (L13-15), `unused_pipeline_debug_tool` (L13-15)

### `utils/helpers.py`
- **Language:** Python | **Lines:** 15
- **Summary:** Provides implementation for sanitize_numeric, sanitize_numeric, sanitize_numeric, normalize_text, normalize_text, normalize_text, unused_pipeline_debug_tool, unused_pipeline_debug_tool, unused_pipeline_debug_tool
- **Functions:** `sanitize_numeric` (L3-6), `sanitize_numeric` (L3-6), `sanitize_numeric` (L3-6), `normalize_text` (L8-11), `normalize_text` (L8-11), `normalize_text` (L8-11), `unused_pipeline_debug_tool` (L13-15), `unused_pipeline_debug_tool` (L13-15), `unused_pipeline_debug_tool` (L13-15)

## 4. Code Quality & Security Posture

- **Total Static Findings:** 9
  - **Low:** 7
  - **Medium:** 2

---
*Report compiled deterministically via AST extraction and LangGraph agent workflow.*