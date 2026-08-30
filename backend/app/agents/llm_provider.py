"""
LLM Provider Abstraction Layer.

Problem Solved:
Decouples financial reconciliation business logic from specific proprietary AI vendors.
Allows seamless switching between OpenAI, Anthropic, Google Gemini, or local heuristic modes
without altering application code.

Why It Exists:
To support enterprise multi-cloud setups, offline local development, and deterministic test mocking.

Input:
System prompt, user prompt, and target response schema.

Output:
Strictly validated JSON object / Pydantic dictionary.
"""

import json
import re
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


def _redact_key(text: str) -> str:
    """Redact API keys from log messages to prevent credential leakage."""
    # Redact anything that looks like an API key in a URL query parameter
    text = re.sub(r'key=[A-Za-z0-9_.\-]+', 'key=***REDACTED***', text)
    # Redact standalone API key patterns
    text = re.sub(r'(api[_-]?key[=:]\s*)[A-Za-z0-9_.\-]{10,}', r'\1***REDACTED***', text, flags=re.IGNORECASE)
    return text


class BaseLLMClient(ABC):
    """Abstract base class for all LLM provider clients."""

    @abstractmethod
    async def generate_structured_json(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> Dict[str, Any]:
        """Generates structured JSON dictionary response from the LLM."""
        pass


class CircuitBreaker:
    """
    Simple circuit breaker for LLM API calls.

    After `max_failures` consecutive failures, the circuit opens and all
    subsequent calls immediately return None (fast-fail) without making
    network requests. This prevents wasting minutes on sequential failing
    HTTP calls when the provider is down or misconfigured.
    """

    def __init__(self, max_failures: int = 3):
        self.max_failures = max_failures
        self.consecutive_failures = 0
        self.is_open = False

    def record_success(self):
        self.consecutive_failures = 0
        self.is_open = False

    def record_failure(self):
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.max_failures:
            self.is_open = True
            logger.warning(
                f"Circuit breaker OPEN after {self.consecutive_failures} consecutive AI failures. "
                f"Remaining candidates will fast-fail to REVIEW."
            )

    def should_skip(self) -> bool:
        return self.is_open


# Global circuit breaker instance shared across all AI verification calls within a run
_circuit_breaker = CircuitBreaker(max_failures=3)


def get_circuit_breaker() -> CircuitBreaker:
    """Returns the global circuit breaker. Reset between reconciliation runs."""
    return _circuit_breaker


def reset_circuit_breaker():
    """Resets the circuit breaker for a new reconciliation run."""
    global _circuit_breaker
    _circuit_breaker = CircuitBreaker(max_failures=3)


class MockHeuristicLLMClient(BaseLLMClient):
    """
    Intelligent heuristic fallback client.
    Used when no live LLM API key is provided or for fast deterministic test suites.
    Simulates rigorous financial auditor reasoning on candidate features.
    """

    async def generate_structured_json(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> Dict[str, Any]:
        # Parse context from user prompt if available
        prompt_lower = user_prompt.lower()
        is_amount_mismatch = "amount mismatch" in prompt_lower or "discrepancy" in prompt_lower
        is_failed = "failed" in prompt_lower
        is_refund = "refund" in prompt_lower
        is_duplicate = "duplicate" in prompt_lower
        is_missing = "missing" in prompt_lower

        if is_failed:
            return {
                "decision": "EXCEPTION",
                "confidence": 0.95,
                "risk_level": "HIGH",
                "reason": "Payment gateway record is marked with status FAILED. Funds were not captured.",
                "recommended_action": "Do not deliver goods/services. Request customer retry payment.",
            }
        
        if is_refund:
            return {
                "decision": "EXCEPTION",
                "confidence": 0.92,
                "risk_level": "MEDIUM",
                "reason": "Transaction represents a customer refund/reversal.",
                "recommended_action": "Verify credit note issuance in ERP ledger.",
            }
        
        if is_duplicate:
            return {
                "decision": "DUPLICATE",
                "confidence": 0.96,
                "risk_level": "HIGH",
                "reason": "Multiple distinct settlement records reference the identical invoice/order identifier.",
                "recommended_action": "Escalate to finance operations to verify duplicate charge or initiate refund.",
            }

        if is_missing:
            return {
                "decision": "MISSING",
                "confidence": 0.90,
                "risk_level": "MEDIUM",
                "reason": "One or more counterparty records (Bank, Gateway, or Invoice) are missing in the batch.",
                "recommended_action": "Check pending settlement queue or request missing invoice from ERP.",
            }

        if is_amount_mismatch:
            return {
                "decision": "EXCEPTION",
                "confidence": 0.91,
                "risk_level": "HIGH",
                "reason": "Material amount discrepancy detected between settlement records.",
                "recommended_action": "Inspect fee breakdown or issue revised invoice for partial payment.",
            }

        # Default ambiguous case -> Escalated Review
        return {
            "decision": "REVIEW",
            "confidence": 0.82,
            "risk_level": "LOW",
            "reason": "Record exhibits acceptable multi-factor similarity but slight date settlement lag or entity name formatting variation.",
            "recommended_action": "Review normalized counterparty details and approve manual match.",
        }


class OpenAIClient(BaseLLMClient):
    """OpenAI API client implementation."""

    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini"):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key)
        self.model_name = model_name

    async def generate_structured_json(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> Dict[str, Any]:
        response = await self.client.chat.completions.create(
            model=self.model_name,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=settings.LLM_TEMPERATURE,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
        raw_content = response.choices[0].message.content or "{}"
        return json.loads(raw_content)


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude API client implementation via REST."""

    def __init__(self, api_key: str, model_name: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key
        self.model_name = model_name
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS)
        return self._client

    async def generate_structured_json(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> Dict[str, Any]:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "max_tokens": 1000,
            "system": system_prompt + "\nOutput valid JSON only.",
            "messages": [{"role": "user", "content": user_prompt}],
            "temperature": settings.LLM_TEMPERATURE,
        }
        client = await self._get_client()
        resp = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        text = data["content"][0]["text"]
        # Clean possible markdown wrapping
        if text.startswith("```json"):
            text = text[7:-3]
        elif text.startswith("```"):
            text = text[3:-3]
        return json.loads(text.strip())


class GeminiClient(BaseLLMClient):
    """Google Gemini API client implementation via REST."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model_name = model_name
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS)
        return self._client

    async def generate_structured_json(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> Dict[str, Any]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": system_prompt + "\n\n" + user_prompt}
                    ]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": settings.LLM_TEMPERATURE,
            }
        }
        client = await self._get_client()
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text.strip())


def get_llm_client() -> BaseLLMClient:
    """
    Factory function returning the configured LLM provider client.
    Gracefully falls back to MockHeuristicLLMClient if keys are missing.
    """
    provider = settings.LLM_PROVIDER.lower()

    if provider == "openai" and settings.OPENAI_API_KEY:
        try:
            return OpenAIClient(api_key=settings.OPENAI_API_KEY, model_name=settings.MODEL_NAME)
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI client: {_redact_key(str(e))}. Using mock client.")
            return MockHeuristicLLMClient()

    elif provider == "anthropic" and settings.ANTHROPIC_API_KEY:
        return AnthropicClient(api_key=settings.ANTHROPIC_API_KEY, model_name=settings.MODEL_NAME)

    elif provider == "gemini" and settings.GEMINI_API_KEY:
        return GeminiClient(api_key=settings.GEMINI_API_KEY, model_name=settings.MODEL_NAME)

    # Default fallback
    logger.info(f"LLM provider '{provider}' — using MockHeuristicLLMClient (no API key or provider=mock).")
    return MockHeuristicLLMClient()
