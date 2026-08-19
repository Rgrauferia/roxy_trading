"""Simple LLM provider abstraction.

Supports multiple providers through environment configuration. Secrets are loaded
securely from environment variables, an optional key file path, or the OS keyring
when available.

Configuration (environment variables):
- `ROXY_TRADING_LLM_PROVIDER`: 'openai' or 'anthropic'.
- OpenAI is product-scoped and only reads `ROXY_TRADING_OPENAI_*`; it never
  falls back to a Study or generic `OPENAI_API_KEY`.
- `ANTHROPIC_API_KEY`: legacy optional provider key.
- `LLM_KEY_FILE`: optional file path containing the API key (used if the env var
  is not set). This file should have restrictive permissions.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger("llm_provider")

try:
    import keyring
except Exception:
    keyring = None


def _get_secret(env_var: str, file_env_var: str, keyring_name: str) -> Optional[str]:
    # 1) direct env var
    v = os.getenv(env_var)
    if v:
        return v

    # 2) file containing key (path provided in file_env_var)
    path = os.getenv(file_env_var)
    if path:
        try:
            st = os.stat(path)
            # warn if file is world-readable
            if st.st_mode & 0o077:
                logger.warning("Secret file %s has permissive permissions (consider chmod 600)", path)
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            logger.exception("Failed to read secret file %s: %s", path, e)

    # 3) OS keyring (optional)
    if keyring is not None:
        try:
            v = keyring.get_password("roxy_llm", keyring_name)
            if v:
                return v
        except Exception:
            logger.exception("keyring lookup failed")

    return None


def _choose_provider() -> str:
    configured = os.getenv("ROXY_TRADING_LLM_PROVIDER")
    if configured:
        return configured.lower()

    # Trading OpenAI credentials are intentionally isolated from generic/Study keys.
    if os.getenv("ROXY_TRADING_OPENAI_API_KEY"):
        return "openai"
    if _get_secret("ANTHROPIC_API_KEY", "LLM_KEY_FILE", "anthropic"):
        return "anthropic"
    return "none"


def generate_reply(
    query: str,
    user: Optional[str] = None,
    *,
    context: Optional[dict] = None,
    requested_depth: Optional[str] = None,
    confirmed: bool = False,
) -> str:
    q = (query or "").strip()
    if not q:
        return ""

    provider = _choose_provider()

    if provider == "openai":
        try:
            from roxy_trader.openai_brain import RoxyTradingOpenAIBrain

            answer = RoxyTradingOpenAIBrain().answer(
                q,
                market_context=context,
                requested_depth=requested_depth,
                confirmed=confirmed,
            )
            return answer.text
        except Exception:
            logger.exception("Roxy Trading OpenAI call failed")
            return ""

    if provider == "anthropic":
        api_key = _get_secret("ANTHROPIC_API_KEY", "LLM_KEY_FILE", "anthropic")
        if not api_key:
            logger.warning("Anthropic provider selected but no API key found")
            return ""
        try:
            # Attempt to use the official Anthropic client if available.
            try:
                from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT

                client = Anthropic(api_key=api_key)
                model = os.getenv("ANTHROPIC_MODEL", "claude-2").strip()
                prompt = f"{HUMAN_PROMPT}{q}{AI_PROMPT}"
                resp = client.completions.create(model=model, prompt=prompt, max_tokens_to_sample=512)
                text = getattr(resp, "completion", resp.get("completion", "")).strip()
                return text
            except Exception:
                # Try alternate import style
                from anthropic import Client, HUMAN_PROMPT, AI_PROMPT

                client = Client(api_key=api_key)
                model = os.getenv("ANTHROPIC_MODEL", "claude-2")
                prompt = f"{HUMAN_PROMPT}{q}{AI_PROMPT}"
                resp = client.create_completion(model=model, prompt=prompt, max_tokens_to_sample=512)
                text = resp.get("completion", "").strip()
                return text
        except Exception as e:
            logger.exception("Anthropic call failed: %s", e)
            return f"(llm error) {e}"

    logger.debug("No LLM provider configured")
    return ""
