# Python Architecture & Coding Best Practices

## 1. Overview and Core Philosophy
Writing reliable, maintainable, and high-performance Python requires adhering to idiomatic patterns ("The Zen of Python", PEP 20), robust resource management, explicit exception handling, and strict type safety.

---

## 2. Common Antipatterns and Robust Solutions

### A. Mutable Default Arguments
In Python, default parameter values are evaluated once at function definition time, not every time the function is called. Mutating a default argument causes unintended state retention across invocations.

```python
# VULNERABLE / BUGGY: Shared mutable list across calls
def append_item(item: str, items: list = []):
    items.append(item)
    return items

# Calling append_item("A") -> ["A"]
# Calling append_item("B") -> ["A", "B"] (Unexpected bug!)
```

```python
# ROBUST / IDIOMATIC: Sentinel None default value
from typing import List, Optional

def append_item_safe(item: str, items: Optional[List[str]] = None) -> List[str]:
    if items is None:
        items = []
    items.append(item)
    return items
```

### B. Bare `except:` Clauses and Silent Failure
Catching all exceptions with a bare `except:` or swallowing them silently hides syntax bugs, `KeyboardInterrupt`, `SystemExit`, and critical memory/network failures.

```python
# ANTIPATTERN: Swallowing errors silently
try:
    process_transaction()
except:
    pass  # Debugging impossible; data corruption concealed
```

```python
# ROBUST: Catch specific exceptions and log with stack trace
import logging

logger = logging.getLogger(__name__)

try:
    process_transaction()
except (ValueError, ConnectionError) as err:
    logger.exception("Transaction processing failed: %s", err)
    raise
```

### C. Resource Management with Context Managers (`with`)
Failing to close file handles, database connections, or HTTP sessions causes file descriptor exhaustion and memory leaks. Always wrap I/O resources in `with` statements.

```python
# ANTIPATTERN: Unclosed file handle
def read_data(filepath):
    f = open(filepath, "r")
    data = f.read()
    # If an exception occurs here, f is never closed
    f.close()
    return data
```

```python
# ROBUST: Automatic guaranteed closure via context manager
def read_data_safe(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()
```

---

## 3. Architecture and Code Hygiene

### A. Type Annotations and Data Validation
* Annotate function signatures with explicit type hints (`typing` module / PEP 484).
* Use `pydantic` or `dataclasses` for domain models and data transfer objects (DTOs) rather than loose nested dictionaries.

### B. Modular Packaging and Clean Boundaries
* Keep modules focused on a single responsibility (SRP).
* Avoid deep circular dependencies; use dependency injection or service abstractions to decouple layers.
* Keep functions small, testable, and deterministic.

---

## 4. Best Practices Checklist
1. **Never use mutable default arguments** (`[]`, `{}`).
2. **Never use bare `except:`**; catch specific expected exceptions and log them.
3. **Always use context managers (`with`)** for file, database, and network resources.
4. **Enforce formatting & linting**: Use `ruff`, `black`, `flake8`, and `mypy` in CI pipelines.
