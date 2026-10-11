# Hardcoded Secrets & Credential Management

## 1. Overview and Threat Profile
* **Classification**: CWE-798 (Use of Hard-coded Credentials), OWASP Top 10 A07:2021 (Identification and Authentication Failures).
* **Severity**: High to Critical.
* **Risk Summary**: Hardcoding secrets (API keys, database passwords, private encryption keys, OAuth tokens, JWT secret keys, cloud service credentials) directly into source code commits sensitive authentication materials into version control history. Once committed, credentials can be harvested by attackers via public repository leaks, compromised developer workstations, or CI/CD build artifact inspection.

---

## 2. Common Vulnerable Patterns in Python

### A. Direct Variable Assignment
```python
# VULNERABLE: Direct hardcoding of sensitive credentials
DATABASE_PASSWORD = "SuperSecretPassword123!"
OPENAI_API_KEY = "sk-proj-992384918239481923"
JWT_SECRET_KEY = "my_jwt_production_signing_key"
AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
```

### B. Inline Client Initialization
```python
import stripe

# VULNERABLE: Hardcoded vendor key inside controller
def process_payment(amount, token):
    stripe.api_key = "sk_live_51HzABCxyz1234567890"
    return stripe.Charge.create(amount=amount, currency="usd", source=token)
```

### C. Default Fallback to Production-Looking Values
```python
import os

# VULNERABLE: Dangerous insecure fallback string
SECRET_KEY = os.getenv("SECRET_KEY", "default-insecure-secret-key-12345")
```

---

## 3. Secure Remediation Patterns

### A. Environment Variables (`os.environ` / `python-dotenv`)
Always load secrets from runtime environment variables. In development, use a `.env` file that is strictly ignored by `.gitignore`.

```python
import os
from dotenv import load_dotenv

load_dotenv()  # Reads .env locally, no-op in production container

# SECURE: Fail fast if the required secret is not provided
API_KEY = os.environ.get("SERVICE_API_KEY")
if not API_KEY:
    raise RuntimeError("CRITICAL: SERVICE_API_KEY environment variable is missing.")
```

### B. Pydantic Settings Validation
Using `pydantic-settings` provides structured typing, automatic `.env` loading, and guarantees that credentials are never hardcoded.

```python
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings

class AppSettings(BaseSettings):
    DATABASE_URL: str
    API_KEY: SecretStr = Field(..., description="External vendor API key")
    JWT_SECRET: SecretStr = Field(..., description="Cryptographic signing key")

    class Config:
        env_file = ".env"

# SECURE: Secrets are masked in string representations (e.g., '**********')
settings = AppSettings()
```

### C. Dedicated Secret Managers in Cloud / Production
In production environments, pull credentials at runtime from managed secret stores:
* **AWS Secrets Manager / SSM Parameter Store**
* **HashiCorp Vault**
* **GCP Secret Manager**
* **Kubernetes Secrets (mounted as files or environment variables)**

---

## 4. Remediation Checklist
1. **Never Commit Secrets**: Ensure `.env`, `*.pem`, `*.key`, and `credentials.json` are listed in `.gitignore`.
2. **Rotate Exposed Credentials**: If a secret was ever committed to git history, treat it as immediately compromised. Revoke and rotate it in the vendor portal; rewriting git history does not guarantee isolation if clones exist.
3. **Pre-commit Scanning**: Integrate automated scanner tools such as `gitleaks`, `trufflehog`, or `detect-secrets` into pre-commit git hooks and CI workflows.
