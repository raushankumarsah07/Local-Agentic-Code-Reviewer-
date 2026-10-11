# Architecture & Repository Documentation: sample_calculator

> **Generated automatically by Local Agentic Code Reviewer**  
> *Timestamp: 2026-10-11T14:07:22.245883+00:00*  

## 1. Executive Overview

- **Project Name:** `sample_calculator`
- **Total Scanned Files:** 26
- **Total Source Lines:** 795
- **Classes Identified:** 18
- **Functions & Methods:** 90
- **Identified Entry Points:** `main.py`

## 2. Architecture & Subsystem Modules

The repository is structured into the following architectural modules:

| Module / Directory | Role & Responsibility | Files | Lines | Exported Symbols |
| :--- | :--- | :--- | :--- | :--- |
| `docs` | Subsystem handling docs utilities and business components | 2 | 207 | — |
| `root` | Core root application entry & scripts | 15 | 477 | `BasicCalculator`, `BasicCalculator`, `BasicCalculator`, `ScientificCalculator` |
| `utils` | Subsystem handling utils utilities and business components | 9 | 111 | `clean_string`, `clean_string`, `clean_string`, `clean_string` |

## 3. Detailed Component Catalog

### `README.md`
- **Language:** Markdown | **Lines:** 6
- **Summary:** Source code file or configuration

### `README.md`
- **Language:** Markdown | **Lines:** 6
- **Summary:** Source code file or configuration

### `README.md`
- **Language:** Markdown | **Lines:** 6
- **Summary:** Source code file or configuration

### `calculator.py`
- **Language:** Python | **Lines:** 48
- **Summary:** Provides implementation for BasicCalculator, BasicCalculator, BasicCalculator, ScientificCalculator, ScientificCalculator, ScientificCalculator
- **Classes:** `BasicCalculator` (L10-33), `BasicCalculator` (L10-33), `BasicCalculator` (L10-33), `ScientificCalculator` (L36-48), `ScientificCalculator` (L36-48), `ScientificCalculator` (L36-48)
- **Dependencies / Imports:** `PRECISION`, `format_result`, `math`, `validate_number`

### `calculator.py`
- **Language:** Python | **Lines:** 48
- **Summary:** Provides implementation for BasicCalculator, BasicCalculator, BasicCalculator, ScientificCalculator, ScientificCalculator, ScientificCalculator
- **Classes:** `BasicCalculator` (L10-33), `BasicCalculator` (L10-33), `BasicCalculator` (L10-33), `ScientificCalculator` (L36-48), `ScientificCalculator` (L36-48), `ScientificCalculator` (L36-48)
- **Dependencies / Imports:** `PRECISION`, `format_result`, `math`, `validate_number`

### `calculator.py`
- **Language:** Python | **Lines:** 48
- **Summary:** Provides implementation for BasicCalculator, BasicCalculator, BasicCalculator, ScientificCalculator, ScientificCalculator, ScientificCalculator
- **Classes:** `BasicCalculator` (L10-33), `BasicCalculator` (L10-33), `BasicCalculator` (L10-33), `ScientificCalculator` (L36-48), `ScientificCalculator` (L36-48), `ScientificCalculator` (L36-48)
- **Dependencies / Imports:** `PRECISION`, `format_result`, `math`, `validate_number`

### `config.py`
- **Language:** Python | **Lines:** 12
- **Summary:** Source code file or configuration
- **Dependencies / Imports:** `os`

### `config.py`
- **Language:** Python | **Lines:** 12
- **Summary:** Source code file or configuration
- **Dependencies / Imports:** `os`

### `config.py`
- **Language:** Python | **Lines:** 12
- **Summary:** Source code file or configuration
- **Dependencies / Imports:** `os`

### `docs/ARCHITECTURE.md`
- **Language:** Markdown | **Lines:** 79
- **Summary:** Source code file or configuration

### `docs/ARCHITECTURE.md`
- **Language:** Markdown | **Lines:** 128
- **Summary:** Source code file or configuration

### `history.py`
- **Language:** Python | **Lines:** 67
- **Summary:** Provides implementation for execute_shell_export, execute_shell_export, execute_shell_export, eval_formula_expression, eval_formula_expression, eval_formula_expression, load_history_cache, load_history_cache, load_history_cache, query_user_history, query_user_history, query_user_history, complex_scientific_pipeline, complex_scientific_pipeline, complex_scientific_pipeline, unused_dead_helper, unused_dead_helper, unused_dead_helper
- **Functions:** `execute_shell_export` (L13-15), `execute_shell_export` (L13-15), `execute_shell_export` (L13-15), `eval_formula_expression` (L18-20), `eval_formula_expression` (L18-20), `eval_formula_expression` (L18-20), `load_history_cache` (L23-25), `load_history_cache` (L23-25), `load_history_cache` (L23-25), `query_user_history` (L28-31), `query_user_history` (L28-31), `query_user_history` (L28-31), `complex_scientific_pipeline` (L34-62), `complex_scientific_pipeline` (L34-62), `complex_scientific_pipeline` (L34-62), `unused_dead_helper` (L65-67), `unused_dead_helper` (L65-67), `unused_dead_helper` (L65-67)
- **Dependencies / Imports:** `pickle`, `subprocess`

### `history.py`
- **Language:** Python | **Lines:** 67
- **Summary:** Provides implementation for execute_shell_export, execute_shell_export, execute_shell_export, eval_formula_expression, eval_formula_expression, eval_formula_expression, load_history_cache, load_history_cache, load_history_cache, query_user_history, query_user_history, query_user_history, complex_scientific_pipeline, complex_scientific_pipeline, complex_scientific_pipeline, unused_dead_helper, unused_dead_helper, unused_dead_helper
- **Functions:** `execute_shell_export` (L13-15), `execute_shell_export` (L13-15), `execute_shell_export` (L13-15), `eval_formula_expression` (L18-20), `eval_formula_expression` (L18-20), `eval_formula_expression` (L18-20), `load_history_cache` (L23-25), `load_history_cache` (L23-25), `load_history_cache` (L23-25), `query_user_history` (L28-31), `query_user_history` (L28-31), `query_user_history` (L28-31), `complex_scientific_pipeline` (L34-62), `complex_scientific_pipeline` (L34-62), `complex_scientific_pipeline` (L34-62), `unused_dead_helper` (L65-67), `unused_dead_helper` (L65-67), `unused_dead_helper` (L65-67)
- **Dependencies / Imports:** `pickle`, `subprocess`

### `history.py`
- **Language:** Python | **Lines:** 67
- **Summary:** Provides implementation for execute_shell_export, execute_shell_export, execute_shell_export, eval_formula_expression, eval_formula_expression, eval_formula_expression, load_history_cache, load_history_cache, load_history_cache, query_user_history, query_user_history, query_user_history, complex_scientific_pipeline, complex_scientific_pipeline, complex_scientific_pipeline, unused_dead_helper, unused_dead_helper, unused_dead_helper
- **Functions:** `execute_shell_export` (L13-15), `execute_shell_export` (L13-15), `execute_shell_export` (L13-15), `eval_formula_expression` (L18-20), `eval_formula_expression` (L18-20), `eval_formula_expression` (L18-20), `load_history_cache` (L23-25), `load_history_cache` (L23-25), `load_history_cache` (L23-25), `query_user_history` (L28-31), `query_user_history` (L28-31), `query_user_history` (L28-31), `complex_scientific_pipeline` (L34-62), `complex_scientific_pipeline` (L34-62), `complex_scientific_pipeline` (L34-62), `unused_dead_helper` (L65-67), `unused_dead_helper` (L65-67), `unused_dead_helper` (L65-67)
- **Dependencies / Imports:** `pickle`, `subprocess`

### `main.py`
- **Language:** Python | **Lines:** 26
- **Summary:** Provides implementation for run, run, run
- **Functions:** `run` (L11-22), `run` (L11-22), `run` (L11-22)
- **Dependencies / Imports:** `APP_CONFIG`, `BasicCalculator`, `ScientificCalculator`, `format_result`, `sys`

### `main.py`
- **Language:** Python | **Lines:** 26
- **Summary:** Provides implementation for run, run, run
- **Functions:** `run` (L11-22), `run` (L11-22), `run` (L11-22)
- **Dependencies / Imports:** `APP_CONFIG`, `BasicCalculator`, `ScientificCalculator`, `format_result`, `sys`

### `main.py`
- **Language:** Python | **Lines:** 26
- **Summary:** Provides implementation for run, run, run
- **Functions:** `run` (L11-22), `run` (L11-22), `run` (L11-22)
- **Dependencies / Imports:** `APP_CONFIG`, `BasicCalculator`, `ScientificCalculator`, `format_result`, `sys`

### `utils/__init__.py`
- **Language:** Python | **Lines:** 8
- **Summary:** Source code file or configuration
- **Dependencies / Imports:** `clean_string`, `format_result`, `validate_number`

### `utils/__init__.py`
- **Language:** Python | **Lines:** 8
- **Summary:** Source code file or configuration
- **Dependencies / Imports:** `clean_string`, `format_result`, `validate_number`

### `utils/__init__.py`
- **Language:** Python | **Lines:** 8
- **Summary:** Source code file or configuration
- **Dependencies / Imports:** `clean_string`, `format_result`, `validate_number`

### `utils/formatters.py`
- **Language:** Python | **Lines:** 10
- **Summary:** Provides implementation for clean_string, clean_string, clean_string
- **Functions:** `clean_string` (L8-10), `clean_string` (L8-10), `clean_string` (L8-10)
- **Dependencies / Imports:** `re`

### `utils/formatters.py`
- **Language:** Python | **Lines:** 10
- **Summary:** Provides implementation for clean_string, clean_string, clean_string
- **Functions:** `clean_string` (L8-10), `clean_string` (L8-10), `clean_string` (L8-10)
- **Dependencies / Imports:** `re`

### `utils/formatters.py`
- **Language:** Python | **Lines:** 10
- **Summary:** Provides implementation for clean_string, clean_string, clean_string
- **Functions:** `clean_string` (L8-10), `clean_string` (L8-10), `clean_string` (L8-10)
- **Dependencies / Imports:** `re`

### `utils/helpers.py`
- **Language:** Python | **Lines:** 19
- **Summary:** Provides implementation for validate_number, validate_number, validate_number, format_result, format_result, format_result
- **Functions:** `validate_number` (L9-14), `validate_number` (L9-14), `validate_number` (L9-14), `format_result` (L17-19), `format_result` (L17-19), `format_result` (L17-19)
- **Dependencies / Imports:** `Union`, `clean_string`

### `utils/helpers.py`
- **Language:** Python | **Lines:** 19
- **Summary:** Provides implementation for validate_number, validate_number, validate_number, format_result, format_result, format_result
- **Functions:** `validate_number` (L9-14), `validate_number` (L9-14), `validate_number` (L9-14), `format_result` (L17-19), `format_result` (L17-19), `format_result` (L17-19)
- **Dependencies / Imports:** `Union`, `clean_string`

### `utils/helpers.py`
- **Language:** Python | **Lines:** 19
- **Summary:** Provides implementation for validate_number, validate_number, validate_number, format_result, format_result, format_result
- **Functions:** `validate_number` (L9-14), `validate_number` (L9-14), `validate_number` (L9-14), `format_result` (L17-19), `format_result` (L17-19), `format_result` (L17-19)
- **Dependencies / Imports:** `Union`, `clean_string`

## 4. Code Quality & Security Posture

- **Total Static Findings:** 21
  - **Critical:** 3
  - **High:** 11
  - **Low:** 4
  - **Medium:** 3

---
*Report compiled deterministically via AST extraction and LangGraph agent workflow.*