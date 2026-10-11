# Cyclomatic Complexity & Long Function Guidance

## 1. Overview and Metric Definitions
* **Cyclomatic Complexity (McCabe Complexity, $V(G)$)**: Measures the number of linearly independent paths through a program's source code. Each branching construct (`if`, `elif`, `for`, `while`, `except`, `with`, boolean `and`/`or`) adds an independent control flow path.
* **Risk Summary**: Functions with high cyclomatic complexity or excessive length (Lines of Code / LOC) exhibit high cognitive load, elevated defect density, poor test coverage (as every independent path requires its own test case), and difficult maintainability.

---

## 2. Industry Standard Complexity Thresholds

| Cyclomatic Complexity ($V(G)$) | Evaluation | Architectural Recommendation |
| :--- | :--- | :--- |
| **1 – 5** | Low Risk | Simple, easy to understand and unit test. Excellent quality. |
| **6 – 10** | Moderate Risk | Moderate complexity; acceptable for non-critical routines. Ensure thorough test coverage. |
| **11 – 20** | High Risk | Complex logic with many branches. Candidate for decomposition and refactoring. |
| **> 20** | Very High / Untestable | Untenable complexity. Refactoring into smaller functions is mandatory. |

---

## 3. Practical Refactoring Patterns

### A. Guard Clauses and Early Returns (Reduce Nesting Depth)
Deeply nested `if-else` blocks multiply cognitive burden (the "arrow anti-pattern"). Replace nested blocks with early exit guard clauses.

```python
# ANTIPATTERN: Deeply nested pyramid of conditions
def process_order_complex(order):
    if order is not None:
        if order.is_active:
            if order.items:
                if order.payment_verified:
                    return ship_order(order)
                else:
                    return "Payment failed"
            else:
                return "Empty order"
        else:
            return "Order inactive"
    return "Invalid order"
```

```python
# REFACTORED: Guard clauses with early returns (Flat, readable, low complexity)
def process_order_clean(order):
    if order is None:
        return "Invalid order"
    if not order.is_active:
        return "Order inactive"
    if not order.items:
        return "Empty order"
    if not order.payment_verified:
        return "Payment failed"

    return ship_order(order)
```

### B. Replace Massive `if/elif` Chains with Dictionary Dispatch (Strategy Pattern)
Functions with 15+ `elif` branches handling commands or types can be replaced by dictionary lookup tables.

```python
# REFACTORED: Dispatch table pattern
COMMAND_HANDLERS = {
    "CREATE": handle_create,
    "UPDATE": handle_update,
    "DELETE": handle_delete,
    "ARCHIVE": handle_archive,
}

def execute_command_clean(command_type: str, payload: dict):
    handler = COMMAND_HANDLERS.get(command_type)
    if not handler:
        raise ValueError(f"Unknown command: {command_type}")
    return handler(payload)
```

### C. Extract Method / Helper Decomposition
Break monolithic functions (>50 LOC) into focused, single-purpose helper functions named after what they achieve.

```python
# REFACTORED: Composed method pattern
def process_invoice(invoice_data: dict) -> dict:
    validated = validate_invoice_structure(invoice_data)
    totals = calculate_line_item_totals(validated)
    tax = compute_regional_tax(totals, validated["region"])
    return persist_and_send_invoice(totals, tax, validated["customer_id"])
```

---

## 4. Complexity Remediation Checklist
1. **Target Complexity $\le 10$**: Aim for cyclomatic complexity under 10 for all core business functions.
2. **Cap Function Length**: Keep functions under 50 lines of code wherever possible.
3. **Flatten Control Flow**: Use guard clauses to keep maximum indentation depth $\le 3$ levels.
4. **Isolate Side Effects**: Separate pure calculation/decision logic from I/O and database operations.
