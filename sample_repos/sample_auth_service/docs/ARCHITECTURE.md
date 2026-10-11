# Architecture & Repository Documentation: sample_auth_service

> **Generated automatically by Local Agentic Code Reviewer**  
> *Timestamp: 2026-10-11T14:07:22.495758+00:00*  

## 1. Executive Overview

- **Project Name:** `sample_auth_service`
- **Total Scanned Files:** 26
- **Total Source Lines:** 630
- **Classes Identified:** 18
- **Functions & Methods:** 63
- **Identified Entry Points:** `main.py`

## 2. Architecture & Subsystem Modules

The repository is structured into the following architectural modules:

| Module / Directory | Role & Responsibility | Files | Lines | Exported Symbols |
| :--- | :--- | :--- | :--- | :--- |
| `docs` | Subsystem handling docs utilities and business components | 2 | 210 | — |
| `root` | Core root application entry & scripts | 6 | 93 | `initialize_app`, `initialize_app`, `initialize_app`, `main` |
| `services` | Subsystem handling services utilities and business components | 9 | 219 | `AuthService`, `AuthService`, `AuthService`, `AuthService` |
| `utils` | Subsystem handling utils utilities and business components | 9 | 108 | `hash_password`, `hash_password`, `hash_password`, `verify_password` |

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
- **Language:** Markdown | **Lines:** 80
- **Summary:** Source code file or configuration

### `docs/ARCHITECTURE.md`
- **Language:** Markdown | **Lines:** 130
- **Summary:** Source code file or configuration

### `main.py`
- **Language:** Python | **Lines:** 23
- **Summary:** Provides implementation for initialize_app, initialize_app, initialize_app, main, main, main
- **Functions:** `initialize_app` (L10-14), `initialize_app` (L10-14), `initialize_app` (L10-14), `main` (L16-20), `main` (L16-20), `main` (L16-20)
- **Dependencies / Imports:** `AuthService`, `TokenService`, `hash_password`, `os`, `sys`, `verify_password`

### `main.py`
- **Language:** Python | **Lines:** 23
- **Summary:** Provides implementation for initialize_app, initialize_app, initialize_app, main, main, main
- **Functions:** `initialize_app` (L10-14), `initialize_app` (L10-14), `initialize_app` (L10-14), `main` (L16-20), `main` (L16-20), `main` (L16-20)
- **Dependencies / Imports:** `AuthService`, `TokenService`, `hash_password`, `os`, `sys`, `verify_password`

### `main.py`
- **Language:** Python | **Lines:** 23
- **Summary:** Provides implementation for initialize_app, initialize_app, initialize_app, main, main, main
- **Functions:** `initialize_app` (L10-14), `initialize_app` (L10-14), `initialize_app` (L10-14), `main` (L16-20), `main` (L16-20), `main` (L16-20)
- **Dependencies / Imports:** `AuthService`, `TokenService`, `hash_password`, `os`, `sys`, `verify_password`

### `services/__init__.py`
- **Language:** Python | **Lines:** 4
- **Summary:** Source code file or configuration
- **Dependencies / Imports:** `AuthService`, `TokenService`

### `services/__init__.py`
- **Language:** Python | **Lines:** 4
- **Summary:** Source code file or configuration
- **Dependencies / Imports:** `AuthService`, `TokenService`

### `services/__init__.py`
- **Language:** Python | **Lines:** 4
- **Summary:** Source code file or configuration
- **Dependencies / Imports:** `AuthService`, `TokenService`

### `services/auth_service.py`
- **Language:** Python | **Lines:** 37
- **Summary:** Provides implementation for AuthService, AuthService, AuthService
- **Classes:** `AuthService` (L6-37), `AuthService` (L6-37), `AuthService` (L6-37)
- **Dependencies / Imports:** `hash_password`, `time`, `validate_email`, `validate_password_strength`, `verify_password`

### `services/auth_service.py`
- **Language:** Python | **Lines:** 37
- **Summary:** Provides implementation for AuthService, AuthService, AuthService
- **Classes:** `AuthService` (L6-37), `AuthService` (L6-37), `AuthService` (L6-37)
- **Dependencies / Imports:** `hash_password`, `time`, `validate_email`, `validate_password_strength`, `verify_password`

### `services/auth_service.py`
- **Language:** Python | **Lines:** 37
- **Summary:** Provides implementation for AuthService, AuthService, AuthService
- **Classes:** `AuthService` (L6-37), `AuthService` (L6-37), `AuthService` (L6-37)
- **Dependencies / Imports:** `hash_password`, `time`, `validate_email`, `validate_password_strength`, `verify_password`

### `services/token_service.py`
- **Language:** Python | **Lines:** 32
- **Summary:** Provides implementation for TokenService, TokenService, TokenService
- **Classes:** `TokenService` (L7-32), `TokenService` (L7-32), `TokenService` (L7-32)
- **Dependencies / Imports:** `ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_ALGORITHM`, `JWT_SECRET_KEY`, `base64`, `json`, `time`

### `services/token_service.py`
- **Language:** Python | **Lines:** 32
- **Summary:** Provides implementation for TokenService, TokenService, TokenService
- **Classes:** `TokenService` (L7-32), `TokenService` (L7-32), `TokenService` (L7-32)
- **Dependencies / Imports:** `ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_ALGORITHM`, `JWT_SECRET_KEY`, `base64`, `json`, `time`

### `services/token_service.py`
- **Language:** Python | **Lines:** 32
- **Summary:** Provides implementation for TokenService, TokenService, TokenService
- **Classes:** `TokenService` (L7-32), `TokenService` (L7-32), `TokenService` (L7-32)
- **Dependencies / Imports:** `ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_ALGORITHM`, `JWT_SECRET_KEY`, `base64`, `json`, `time`

### `utils/__init__.py`
- **Language:** Python | **Lines:** 4
- **Summary:** Source code file or configuration
- **Dependencies / Imports:** `hash_password`, `validate_email`, `validate_password_strength`, `verify_password`

### `utils/__init__.py`
- **Language:** Python | **Lines:** 4
- **Summary:** Source code file or configuration
- **Dependencies / Imports:** `hash_password`, `validate_email`, `validate_password_strength`, `verify_password`

### `utils/__init__.py`
- **Language:** Python | **Lines:** 4
- **Summary:** Source code file or configuration
- **Dependencies / Imports:** `hash_password`, `validate_email`, `validate_password_strength`, `verify_password`

### `utils/crypto.py`
- **Language:** Python | **Lines:** 17
- **Summary:** Provides implementation for hash_password, hash_password, hash_password, verify_password, verify_password, verify_password, unused_crypto_helper, unused_crypto_helper, unused_crypto_helper
- **Functions:** `hash_password` (L6-9), `hash_password` (L6-9), `hash_password` (L6-9), `verify_password` (L11-13), `verify_password` (L11-13), `verify_password` (L11-13), `unused_crypto_helper` (L15-17), `unused_crypto_helper` (L15-17), `unused_crypto_helper` (L15-17)
- **Dependencies / Imports:** `base64`, `hashlib`, `hmac`

### `utils/crypto.py`
- **Language:** Python | **Lines:** 17
- **Summary:** Provides implementation for hash_password, hash_password, hash_password, verify_password, verify_password, verify_password, unused_crypto_helper, unused_crypto_helper, unused_crypto_helper
- **Functions:** `hash_password` (L6-9), `hash_password` (L6-9), `hash_password` (L6-9), `verify_password` (L11-13), `verify_password` (L11-13), `verify_password` (L11-13), `unused_crypto_helper` (L15-17), `unused_crypto_helper` (L15-17), `unused_crypto_helper` (L15-17)
- **Dependencies / Imports:** `base64`, `hashlib`, `hmac`

### `utils/crypto.py`
- **Language:** Python | **Lines:** 17
- **Summary:** Provides implementation for hash_password, hash_password, hash_password, verify_password, verify_password, verify_password, unused_crypto_helper, unused_crypto_helper, unused_crypto_helper
- **Functions:** `hash_password` (L6-9), `hash_password` (L6-9), `hash_password` (L6-9), `verify_password` (L11-13), `verify_password` (L11-13), `verify_password` (L11-13), `unused_crypto_helper` (L15-17), `unused_crypto_helper` (L15-17), `unused_crypto_helper` (L15-17)
- **Dependencies / Imports:** `base64`, `hashlib`, `hmac`

### `utils/validators.py`
- **Language:** Python | **Lines:** 15
- **Summary:** Provides implementation for validate_email, validate_email, validate_email, validate_password_strength, validate_password_strength, validate_password_strength
- **Functions:** `validate_email` (L4-7), `validate_email` (L4-7), `validate_email` (L4-7), `validate_password_strength` (L9-15), `validate_password_strength` (L9-15), `validate_password_strength` (L9-15)
- **Dependencies / Imports:** `re`

### `utils/validators.py`
- **Language:** Python | **Lines:** 15
- **Summary:** Provides implementation for validate_email, validate_email, validate_email, validate_password_strength, validate_password_strength, validate_password_strength
- **Functions:** `validate_email` (L4-7), `validate_email` (L4-7), `validate_email` (L4-7), `validate_password_strength` (L9-15), `validate_password_strength` (L9-15), `validate_password_strength` (L9-15)
- **Dependencies / Imports:** `re`

### `utils/validators.py`
- **Language:** Python | **Lines:** 15
- **Summary:** Provides implementation for validate_email, validate_email, validate_email, validate_password_strength, validate_password_strength, validate_password_strength
- **Functions:** `validate_email` (L4-7), `validate_email` (L4-7), `validate_email` (L4-7), `validate_password_strength` (L9-15), `validate_password_strength` (L9-15), `validate_password_strength` (L9-15)
- **Dependencies / Imports:** `re`

## 4. Code Quality & Security Posture

- **Total Static Findings:** 10
  - **High:** 1
  - **Low:** 6
  - **Medium:** 3

---
*Report compiled deterministically via AST extraction and LangGraph agent workflow.*