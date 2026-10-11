# Insecure Deserialization Vulnerabilities in Python

## 1. Overview and Threat Profile
* **Classification**: CWE-502 (Deserialization of Untrusted Data), OWASP Top 10 A08:2021 (Software and Data Integrity Failures).
* **Severity**: Critical.
* **Risk Summary**: Insecure deserialization occurs when an application deserializes untrusted, user-supplied byte streams into living objects in memory. In Python, serializers such as `pickle`, `marshal`, and `shelve` permit the serialized stream to dictate arbitrary callable execution upon reconstruction (via object state hooks like `__reduce__`). An attacker submitting a crafted payload can achieve instant Arbitrary Remote Code Execution (RCE).

---

## 2. Common Vulnerable Patterns in Python

### A. Python `pickle` on Untrusted Input
The standard Python documentation explicitly warns: *"The pickle module is not secure. Only unpickle data you trust."*

```python
import pickle
import base64

# VULNERABLE: Unpickling untrusted data from HTTP requests or sessions
def load_user_session(cookie_data: str):
    raw_bytes = base64.b64decode(cookie_data)
    # RCE: If an attacker crafted a payload with __reduce__, code executes here
    session_dict = pickle.loads(raw_bytes)
    return session_dict
```

```python
# Exploitation demonstration of how __reduce__ triggers RCE
class ExploitPayload:
    def __reduce__(self):
        import os
        return (os.system, ("cat /etc/passwd",))
# When pickle.loads() reconstructs this object, os.system() is executed immediately.
```

### B. Unsafe PyYAML Loading
Using `yaml.load()` without specifying a safe loader allows instantiation of arbitrary Python objects through YAML tags like `!!python/object/apply`.

```python
import yaml

# VULNERABLE: Deprecated unsafe YAML loader
def parse_config(user_yaml: str):
    return yaml.load(user_yaml)  # Triggers arbitrary code execution
```

---

## 3. Secure Remediation Patterns

### A. Use Safe, Format-Restricted Data Serializers (JSON, MessagePack, Protocol Buffers)
Always favor standard data-only interchange formats such as JSON, MessagePack, or Protocol Buffers. Data formats store only values, keys, and lists—they cannot encode arbitrary callable logic or instantiate arbitrary classes.

```python
import json

# SECURE: JSON is purely declarative data
def load_user_session_secure(cookie_json: str) -> dict:
    return json.loads(cookie_json)
```

### B. Safe PyYAML Loading with `yaml.safe_load()`
When parsing YAML documents, strictly enforce `safe_load()`, which restricts tags to basic types (dictionaries, lists, strings, numbers, booleans).

```python
import yaml

# SECURE: Parses YAML safely without object instantiation
def parse_config_secure(yaml_content: str) -> dict:
    return yaml.safe_load(yaml_content)
```

### C. Cryptographic HMAC Signing if Pickle is Unavoidable
If internal trusted caching or distributed tasks (e.g., Celery) require binary serialization, sign the payload using HMAC and a secret key before storage, and verify the signature prior to unpickling.

```python
import hmac
import hashlib
import pickle

SECRET_KEY = b"internal_server_cluster_hmac_secret"

def sign_and_serialize(data) -> bytes:
    payload = pickle.dumps(data)
    signature = hmac.new(SECRET_KEY, payload, hashlib.sha256).digest()
    return signature + payload

def verify_and_deserialize(blob: bytes):
    sig_len = 32  # SHA256 digest length
    expected_sig = blob[:sig_len]
    payload = blob[sig_len:]
    actual_sig = hmac.new(SECRET_KEY, payload, hashlib.sha256).digest()
    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError("Cryptographic tamper check failed! Untrusted payload rejected.")
    return pickle.loads(payload)
```

---

## 4. Remediation Checklist
1. **Never Call `pickle.loads` on External Input**: Prohibit `pickle` for cookies, web APIs, RPC payloads, or user uploads.
2. **Always Use `yaml.safe_load`**: Replace all occurrences of `yaml.load` or specify `Loader=yaml.SafeLoader`.
3. **Migrate to JSON or Pydantic**: Parse and validate request bodies using Pydantic models.
