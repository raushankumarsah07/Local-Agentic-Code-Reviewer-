# Command Injection (OS Command Execution) Vulnerabilities

## 1. Overview and Threat Profile
* **Classification**: CWE-78 (Improper Neutralization of Special Elements used in an OS Command), OWASP Top 10 A03:2021 (Injection).
* **Severity**: Critical.
* **Risk Summary**: Command injection occurs when untrusted user input is passed directly to an operating system shell (such as `/bin/sh`, `bash`, or `cmd.exe`) without proper neutralization or argument separation. An attacker who controls any part of the command string can append shell metacharacters (e.g., `;`, `&`, `|`, `` ` ``, `$()`) to execute arbitrary shell commands with the privileges of the web application process.

---

## 2. Common Vulnerable Patterns in Python

### A. `subprocess` with `shell=True`
Passing `shell=True` to functions like `subprocess.run`, `subprocess.Popen`, or `subprocess.check_output` spawns a full subshell that interprets shell metacharacters.

```python
import subprocess

# VULNERABLE: Direct command interpolation with shell=True
def ping_host(host_ip: str):
    # If host_ip is '8.8.8.8; cat /etc/passwd' or '8.8.8.8 && rm -rf /'
    cmd = f"ping -c 1 {host_ip}"
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)
```

### B. `os.system()` and `os.popen()`
Functions in the legacy `os` module automatically execute through the system shell and are inherently prone to command injection.

```python
import os

# VULNERABLE: Direct call to system shell
def backup_directory(dirname: str):
    os.system(f"tar -czf backup.tar.gz {dirname}")
```

---

## 3. Secure Remediation Patterns

### A. Avoid Shell Spawning: Use `shell=False` and Argument Lists
Instead of passing a formatted string to a shell, pass a list of arguments directly to the operating system binary with `shell=False` (which is the default). When arguments are passed as an array, the OS invokes the executable directly via `execve()`, preventing metacharacters from being interpreted as shell commands.

```python
import subprocess

# SECURE: Argument list without shell interpretation
def ping_host_secure(host_ip: str):
    # The OS treats host_ip strictly as a single argument value, not shell syntax
    result = subprocess.run(
        ["ping", "-c", "1", host_ip],
        shell=False,
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
    return result.stdout
```

### B. Use Native Python Standard Library Alternatives
Whenever possible, perform file, process, and system operations using Python's standard library rather than invoking external shell utilities.

```python
import shutil
import tarfile
from pathlib import Path

# SECURE: Native archive creation without shell tools
def backup_directory_secure(source_dir: Path, output_file: Path):
    with tarfile.open(output_file, "w:gz") as tar:
        tar.add(source_dir, arcname=source_dir.name)
```

### C. Strict Input Validation (Allowlisting)
If external binaries must be called, enforce strict format validation on input variables using regular expressions or allowlists before execution.

```python
import re
import ipaddress

def validate_ip(host_ip: str) -> str:
    # Strictly validate that the input is a valid IPv4 or IPv6 address
    try:
        ipaddress.ip_address(host_ip.strip())
        return host_ip.strip()
    except ValueError:
        raise ValueError("Invalid IP address format.")
```

---

## 4. Remediation Checklist
1. **Never Use `shell=True` with Dynamic Input**: Omit the `shell=True` argument and provide arguments as a list: `["command", "arg1", "arg2"]`.
2. **Avoid `os.system` and `os.popen`**: Migrate all usages to `subprocess.run(..., check=True)`.
3. **Set Process Timeouts**: Always specify a `timeout` parameter to prevent denial-of-service hangs.
4. **Drop Unnecessary Privileges**: Run the application process under an unprivileged system user account (e.g., non-root user in Docker containers).
