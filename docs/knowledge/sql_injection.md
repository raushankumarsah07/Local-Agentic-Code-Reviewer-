# SQL Injection (SQLi) Vulnerabilities and Prevention

## 1. Overview and Threat Profile
* **Classification**: CWE-89 (Improper Neutralization of Special Elements used in an SQL Command), OWASP Top 10 A03:2021 (Injection).
* **Severity**: High to Critical.
* **Risk Summary**: SQL Injection occurs when untrusted user input is directly concatenated, formatted, or interpolated into SQL command strings rather than passed through parameterized query mechanisms. Attackers can manipulate query syntax to bypass authentication, extract confidential data, modify database records, or execute administrative commands (e.g., `DROP TABLE`, `xp_cmdshell`).

---

## 2. Common Vulnerable Patterns in Python

### A. Python f-Strings and Direct String Formatting
```python
# VULNERABLE: Direct f-string interpolation of raw user input
def get_user_by_username(cursor, username: str):
    query = f"SELECT id, username, email FROM users WHERE username = '{username}'"
    cursor.execute(query)
    return cursor.fetchall()

# Attack payload: username = "admin' OR '1'='1"
# Evaluates to: SELECT id, username, email FROM users WHERE username = 'admin' OR '1'='1'
```

### B. Old-Style `%` Formatting and `.format()`
```python
# VULNERABLE: String concatenation or format()
def search_products(cursor, term: str):
    query = "SELECT * FROM products WHERE description LIKE '%" + term + "%'"
    cursor.execute(query)
    return cursor.fetchall()
```

### C. Raw String Queries in ORM Raw SQL Clauses
```python
# VULNERABLE: Passing untrusted string directly into ORM raw text
from sqlalchemy import text

def filter_accounts(session, status: str):
    # text() without bound parameters is directly vulnerable
    query = text(f"SELECT * FROM accounts WHERE status = '{status}'")
    return session.execute(query).fetchall()
```

---

## 3. Secure Remediation Patterns

### A. Parameterized Queries (Prepared Statements)
Database drivers support parameter substitution placeholders (`?` for SQLite, `%s` for psycopg2/MySQL, `:param` for Oracle/SQLAlchemy). The driver sends the query template and values separately to the database engine, rendering injection syntactically impossible.

```python
# SECURE: Parameterized query using sqlite3 placeholder '?'
def get_user_by_username_secure(cursor, username: str):
    query = "SELECT id, username, email FROM users WHERE username = ?"
    cursor.execute(query, (username,))  # Parameters passed as tuple
    return cursor.fetchall()
```

```python
# SECURE: Parameterized query in PostgreSQL (psycopg2 / asyncpg)
def get_order_by_id_secure(cursor, order_id: str):
    query = "SELECT id, customer, total FROM orders WHERE id = %s"
    cursor.execute(query, (order_id,))
    return cursor.fetchone()
```

### B. SQLAlchemy ORM and Bound Parameters
When using SQLAlchemy or other ORMs, rely on model filters or explicitly bound parameter dictionaries.

```python
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.models import User

# SECURE Option 1: ORM query abstractions
def find_user(session: Session, username: str):
    return session.query(User).filter(User.username == username).first()

# SECURE Option 2: Parameterized raw SQL with bound params
def search_accounts(session: Session, status: str):
    stmt = text("SELECT * FROM accounts WHERE status = :status")
    return session.execute(stmt, {"status": status}).fetchall()
```

---

## 4. Remediation Checklist
1. **Never Concatenate SQL**: Never use `+`, `%`, `.format()`, or f-strings to assemble SQL statements with variable data.
2. **Use Bound Parameters**: Always pass variables as the second argument to `cursor.execute(query, params)`.
3. **Principle of Least Privilege**: Ensure the database user utilized by the application has only the minimal required permissions (e.g., read/write to specific tables, no schema alteration rights).
4. **Input Validation**: Validate and sanitize input types (e.g., ensure integer IDs are parsed as `int` before querying).
