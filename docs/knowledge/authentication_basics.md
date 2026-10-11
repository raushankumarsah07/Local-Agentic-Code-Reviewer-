# Authentication and Credential Verification Basics

## 1. Overview and Threat Profile
* **Classification**: CWE-287 (Improper Authentication), CWE-307 (Improper Restriction of Excessive Authentication Attempts), OWASP Top 10 A07:2021 (Identification and Authentication Failures).
* **Severity**: High to Critical.
* **Risk Summary**: Flawed authentication mechanisms allow attackers to compromise user accounts, impersonate administrators, and access protected resources. Core vulnerabilities include storing unhashed passwords, using obsolete cryptographic hash algorithms (MD5, SHA1), exposing endpoints to timing attacks via non-constant-time comparisons, and omitting rate limiting on login handlers.

---

## 2. Common Vulnerable Patterns in Python

### A. Plaintext or Weak Hashing (MD5, SHA-1, SHA-256 without Salt/Work Factor)
```python
import hashlib

# VULNERABLE: MD5 / SHA-1 are cryptographically broken for passwords
# SHA-256 alone is too fast (permits billions of guesses per second with GPUs)
def hash_password_bad(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()
```

### B. Timing Attack in Token / Secret Verification
Using standard Python string equality (`==`) aborts at the first non-matching byte, leaking information about token prefix correctness through execution time variance.

```python
# VULNERABLE: Vulnerable to timing attack
def verify_api_token(user_provided_token: str, actual_token: str) -> bool:
    return user_provided_token == actual_token
```

### C. Hardcoded or Long-Lived JWT Secrets
```python
import jwt

# VULNERABLE: Hardcoded weak secret and no expiration check
def create_token(user_id: int) -> str:
    return jwt.encode({"sub": user_id}, "secret", algorithm="HS256")
```

---

## 3. Secure Remediation Patterns

### A. Modern Adaptive Password Hashing (`argon2-cffi` or `bcrypt`)
Always hash user passwords using a slow, memory-hard adaptive hashing algorithm with an automatically generated salt. Argon2id is the current OWASP recommendation, followed by bcrypt.

```python
# SECURE: Password hashing with bcrypt
import bcrypt

def hash_password_secure(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    hashed_bytes = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed_bytes.decode("utf-8")

def verify_password_secure(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
```

### B. Constant-Time Comparison with `hmac.compare_digest()`
When comparing secret tokens, HMAC signatures, or authorization headers, always use Python's built-in constant-time comparison helper.

```python
import hmac

# SECURE: Constant-time comparison immune to timing side-channels
def verify_api_token_secure(user_token: str, secret_token: str) -> bool:
    return hmac.compare_digest(user_token.encode("utf-8"), secret_token.encode("utf-8"))
```

### C. Secure JSON Web Tokens (JWT) Management
Ensure JWTs have short lifetimes (`exp` claim), validate all required claims, use strong secrets, and reject the `none` algorithm.

```python
import datetime
import jwt

SECRET_KEY = "configured_environment_secret_key"

# SECURE: Enforce expiration and required claims
def generate_access_token(user_id: str, expires_minutes: int = 15) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=expires_minutes),
        "iat": datetime.datetime.now(datetime.timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def decode_access_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=["HS256"], options={"require": ["exp", "sub"]})
```

---

## 4. Remediation Checklist
1. **Always Use Argon2id or bcrypt**: Never roll custom hashing logic or use single-pass hashes like MD5, SHA-1, or plain SHA-256.
2. **Employ `hmac.compare_digest`**: Protect all token and signature checks from timing attacks.
3. **Enforce Rate Limiting & Account Lockout**: Defend authentication endpoints against automated credential stuffing and brute force attacks.
4. **Use HttpOnly, Secure, SameSite Cookies**: If using session cookies, prevent XSS leakage and CSRF attacks by setting proper cookie security flags.
