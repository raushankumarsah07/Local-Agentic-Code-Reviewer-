"""
Local LLM Client for llama.cpp (llama-server) using OpenAI-compatible chat API.
Implements connection retry, timeout handling, and custom error diagnostics.
Never logs full source code at INFO level.
"""

import abc
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


# --- Custom LLM Exceptions ---

class LLMError(Exception):
    """Base exception for all local LLM operations."""
    pass


class LLMUnavailableError(LLMError):
    """Raised when local llama-server is unreachable, offline, or refuses connections."""
    def __init__(self, base_url: str, start_cmd: str):
        message = (
            f"Local LLM server is unreachable at '{base_url}'. "
            f"Please ensure llama-server is running locally.\n"
            f"Exact start command:\n  {start_cmd}"
        )
        super().__init__(message)
        self.base_url = base_url
        self.start_cmd = start_cmd


class LLMTimeoutError(LLMError):
    """Raised when local LLM generation exceeds configured timeout window."""
    def __init__(self, timeout_sec: int):
        message = f"Local LLM generation timed out after {timeout_sec} seconds."
        super().__init__(message)
        self.timeout_sec = timeout_sec


class LLMInvalidResponseError(LLMError):
    """Raised when llama-server returns an unparseable response, 4xx/5xx HTTP error, or malformed body."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


# --- Response Container ---

@dataclass
class LLMResponse:
    """Metadata-rich container for LLM generation response."""
    content: str
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    tokens_per_second: Optional[float]
    model_name: str


# --- Abstract Base Client ---

class LLMClient(abc.ABC):
    """Abstract interface for local language model clients."""

    @abc.abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        response_schema: Optional[Dict[str, Any]] = None,
        schema: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """Send chat completion request to model and return generation with metadata."""
        pass

    @abc.abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Perform diagnostic health check on model server."""
        pass


# --- Llama.cpp (llama-server) Client Implementation ---

class LlamaCppClient(LLMClient):
    """
    Client for llama.cpp llama-server exposing OpenAI-compatible /v1/chat/completions endpoint.
    Supports JSON-schema structured output and enforces local-only execution.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.LLM_BASE_URL.rstrip("/")
        self.model_name = self.settings.LLM_MODEL
        self.temperature = self.settings.LLM_TEMPERATURE
        self.timeout = self.settings.LLM_TIMEOUT_SECONDS
        self.context_size = self.settings.LLM_CONTEXT_SIZE

    def get_start_command(self) -> str:
        """Return the exact CLI command to start llama-server."""
        return (
            f"llama-server -m models/{self.model_name}.gguf "
            f"--port 8080 -c {self.context_size} --n-gpu-layers 99"
        )

    def get_embedding_start_command(self) -> str:
        """Return the exact CLI command to start embedding llama-server."""
        return (
            f"llama-server -m models/{self.settings.EMBEDDING_MODEL}.gguf "
            f"--port 8081 --embedding -c 2048"
        )

    async def chat(
        self,
        messages: List[Dict[str, str]],
        response_schema: Optional[Dict[str, Any]] = None,
        schema: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """
        Invoke chat completion against {LLM_BASE_URL}/chat/completions with automatic single retry on 5xx or network errors.
        Never logs full source code at INFO level.
        """
        effective_schema = response_schema or schema
        endpoint = f"{self.base_url}/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": 1024,
        }

        # Include JSON Schema response format if structured output requested
        if effective_schema:
            payload["response_format"] = {
                "type": "json_object",
                "schema": effective_schema,
            }

        start_time = time.perf_counter()
        last_exception: Optional[Exception] = None

        # Execute with at most 1 retry for transient network glitches or 5xx server hiccups
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(endpoint, json=payload)

                    if resp.status_code >= 500 and attempt == 0:
                        logger.warning(
                            "llama-server returned status %d on attempt 1. Retrying once...",
                            resp.status_code,
                        )
                        continue

                    if resp.status_code != 200:
                        raise LLMInvalidResponseError(
                            f"llama-server error HTTP {resp.status_code}: {resp.text[:300]}",
                            status_code=resp.status_code,
                        )

                    data = resp.json()
                    choices = data.get("choices", [])
                    if not choices:
                        raise LLMInvalidResponseError("llama-server returned empty choices array in response.")

                    message = choices[0].get("message", {})
                    content = message.get("content", "")

                    elapsed_sec = time.perf_counter() - start_time
                    latency_ms = int(elapsed_sec * 1000)

                    usage = data.get("usage", {})
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)
                    total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

                    # Compute tokens per second
                    tokens_per_second = None
                    if completion_tokens > 0 and elapsed_sec > 0:
                        tokens_per_second = round(completion_tokens / elapsed_sec, 2)

                    # Non-sensitive info logging
                    logger.info(
                        "LLM chat completed: model='%s', latency=%dms, tokens=%d, tps=%s",
                        self.model_name,
                        latency_ms,
                        total_tokens,
                        tokens_per_second or "N/A",
                    )

                    return LLMResponse(
                        content=content,
                        latency_ms=latency_ms,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                        tokens_per_second=tokens_per_second,
                        model_name=self.model_name,
                    )

            except httpx.TimeoutException:
                logger.error("LLM generation timed out after %ds", self.timeout)
                raise LLMTimeoutError(self.timeout)
            except httpx.ConnectError as err:
                last_exception = err
                if attempt == 0:
                    continue
                logger.error("Cannot connect to llama-server at %s: %s", self.base_url, err)
                raise LLMUnavailableError(self.base_url, self.get_start_command())
            except httpx.RequestError as err:
                last_exception = err
                if attempt == 0:
                    continue
                logger.error("Network error talking to llama-server: %s", err)
                raise LLMUnavailableError(self.base_url, self.get_start_command())

        # If loop finished without return, raise unavailable
        raise LLMUnavailableError(self.base_url, self.get_start_command())

    async def health_check(self) -> Dict[str, Any]:
        """Check if llama-server and embedding server are responsive."""
        llm_online = False
        llm_message = "Connected to llama-server."

        try:
            # Check LLM server via /models or root health check with 2.0s timeout
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.base_url}/models")
                if resp.status_code == 200:
                    llm_online = True
                else:
                    llm_message = f"llama-server returned HTTP {resp.status_code}"
        except httpx.ConnectError:
            llm_message = f"llama-server is not running at {self.base_url}."
        except httpx.TimeoutException:
            llm_message = "llama-server health check timed out."
        except Exception as e:
            llm_message = f"Health check failed: {str(e)}"

        # Check embedding server
        emb_online = False
        try:
            emb_url = self.settings.EMBEDDING_BASE_URL.rstrip("/")
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.get(f"{emb_url}/models")
                if resp.status_code == 200:
                    emb_online = True
        except Exception:
            pass

        return {
            "status": "connected" if llm_online else "unreachable",
            "backend": self.settings.LLM_BACKEND,
            "base_url": self.base_url,
            "model_name": self.model_name,
            "context_size": self.context_size,
            "server_online": llm_online,
            "embedding_server_online": emb_online,
            "message": llm_message,
            "start_command": self.get_start_command(),
            "embedding_start_command": self.get_embedding_start_command(),
        }


# --- Ollama Native HTTP Client Implementation ---

class OllamaClient(LLMClient):
    """
    Client for Ollama local HTTP daemon exposing /api/chat with format="json".
    Supports model download verification and offline execution.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        # Fall back to OLLAMA_BASE_URL if configured, else LLM_BASE_URL (default http://127.0.0.1:11434)
        raw_url = (
            getattr(self.settings, "OLLAMA_BASE_URL", None)
            or self.settings.LLM_BASE_URL
        ).rstrip("/")
        # If url ends with /v1, strip it for Ollama native endpoints
        if raw_url.endswith("/v1"):
            raw_url = raw_url[:-3]
        self.base_url = raw_url
        self.model_name = self.settings.LLM_MODEL
        self.temperature = self.settings.LLM_TEMPERATURE
        self.timeout = self.settings.LLM_TIMEOUT_SECONDS
        self.context_size = self.settings.LLM_CONTEXT_SIZE

    def get_start_command(self) -> str:
        """Return the exact CLI command to start Ollama and ensure the model is pulled."""
        return f"ollama serve  # and in another terminal: ollama run {self.model_name}"

    def get_embedding_start_command(self) -> str:
        """Return the command to ensure the embedding model is available."""
        return f"ollama pull {self.settings.EMBEDDING_MODEL}"

    async def chat(
        self,
        messages: List[Dict[str, str]],
        response_schema: Optional[Dict[str, Any]] = None,
        schema: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """
        Invoke Ollama /api/chat endpoint with JSON format constraint and single retry.
        Never logs full source code at INFO level.
        """
        endpoint = f"{self.base_url}/api/chat"
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else self.temperature,
                "num_ctx": self.context_size,
            },
        }

        start_time = time.perf_counter()
        last_exception: Optional[Exception] = None

        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=float(self.timeout)) as client:
                    resp = await client.post(endpoint, json=payload)

                    if resp.status_code >= 500:
                        if attempt == 0:
                            logger.warning(
                                "Ollama returned HTTP %d, retrying once...",
                                resp.status_code,
                            )
                            continue

                    if resp.status_code != 200:
                        raise LLMInvalidResponseError(
                            f"Ollama error HTTP {resp.status_code}: {resp.text[:300]}",
                            status_code=resp.status_code,
                        )

                    data = resp.json()
                    message = data.get("message", {})
                    content = message.get("content", "")

                    elapsed_sec = time.perf_counter() - start_time
                    latency_ms = int(elapsed_sec * 1000)

                    prompt_tokens = data.get("prompt_eval_count", 0)
                    completion_tokens = data.get("eval_count", 0)
                    total_tokens = prompt_tokens + completion_tokens

                    # Calculate tokens per second using Ollama eval_duration if available
                    eval_duration_ns = data.get("eval_duration", 0)
                    tokens_per_second = None
                    if completion_tokens > 0:
                        if eval_duration_ns > 0:
                            tokens_per_second = round(completion_tokens / (eval_duration_ns / 1e9), 2)
                        elif elapsed_sec > 0:
                            tokens_per_second = round(completion_tokens / elapsed_sec, 2)

                    logger.info(
                        "Ollama chat completed: model='%s', latency=%dms, tokens=%d, tps=%s",
                        self.model_name,
                        latency_ms,
                        total_tokens,
                        tokens_per_second or "N/A",
                    )

                    return LLMResponse(
                        content=content,
                        latency_ms=latency_ms,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                        tokens_per_second=tokens_per_second,
                        model_name=self.model_name,
                    )

            except httpx.TimeoutException:
                logger.error("Ollama generation timed out after %ds", self.timeout)
                raise LLMTimeoutError(self.timeout)
            except httpx.ConnectError as err:
                last_exception = err
                if attempt == 0:
                    continue
                logger.error("Cannot connect to Ollama at %s: %s", self.base_url, err)
                raise LLMUnavailableError(self.base_url, self.get_start_command())
            except httpx.RequestError as err:
                last_exception = err
                if attempt == 0:
                    continue
                logger.error("Network error talking to Ollama: %s", err)
                raise LLMUnavailableError(self.base_url, self.get_start_command())

        raise LLMUnavailableError(self.base_url, self.get_start_command())

    async def health_check(self) -> Dict[str, Any]:
        """Check if Ollama service is running and configured model is pulled."""
        llm_online = False
        llm_message = "Connected to Ollama."

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code == 200:
                    llm_online = True
                    data = resp.json()
                    model_names = [m.get("name", "") for m in data.get("models", [])]
                    # Check if configured model matches
                    target_clean = self.model_name.split(":")[0].lower()
                    model_found = any(target_clean in m.lower() for m in model_names)
                    if not model_found:
                        llm_message = (
                            f"Ollama is running, but model '{self.model_name}' is not pulled. "
                            f"Run 'ollama pull {self.model_name}'"
                        )
                else:
                    llm_message = f"Ollama returned HTTP {resp.status_code}"
        except httpx.ConnectError:
            llm_message = f"Ollama is not running at {self.base_url}. Run 'ollama serve'"
        except httpx.TimeoutException:
            llm_message = "Ollama health check timed out."
        except Exception as e:
            llm_message = f"Health check failed: {str(e)}"

        return {
            "status": "connected" if llm_online else "unreachable",
            "backend": "ollama",
            "base_url": self.base_url,
            "model_name": self.model_name,
            "context_size": self.context_size,
            "server_online": llm_online,
            "embedding_server_online": llm_online,
            "message": llm_message,
            "start_command": self.get_start_command(),
            "embedding_start_command": self.get_embedding_start_command(),
        }


# --- Client Factory ---

def get_llm_client(settings: Optional[Settings] = None) -> LLMClient:
    """Factory creating the appropriate LLM client based on configured LLM_BACKEND."""
    s = settings or get_settings()
    backend = getattr(s, "LLM_BACKEND", "llama.cpp").lower()
    if backend == "ollama":
        return OllamaClient(s)
    return LlamaCppClient(s)

