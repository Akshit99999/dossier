"""Model-provider configuration for hosted and self-hosted backends."""

from __future__ import annotations

import os
from dataclasses import dataclass

from openai import OpenAI


@dataclass(frozen=True)
class ProviderConfig:
    """Resolved settings for one OpenAI-compatible model provider."""

    name: str
    model: str
    base_url: str | None
    api_key_configured: bool
    native_web_search: bool


def resolve_provider(provider: str | None = None, model: str | None = None) -> ProviderConfig:
    """Resolve provider settings from explicit values and environment variables."""

    name = (provider or os.getenv("MODEL_PROVIDER", "openai")).strip().lower()
    if name == "openai":
        return ProviderConfig(
            name=name,
            model=model or os.getenv("DOSSIER_MODEL", "gpt-5.5"),
            base_url=os.getenv("OPENAI_BASE_URL") or None,
            api_key_configured=bool(os.getenv("OPENAI_API_KEY")),
            native_web_search=True,
        )
    if name == "deepseek":
        return ProviderConfig(
            name=name,
            model=model or os.getenv("DOSSIER_MODEL", "deepseek-reasoner"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            api_key_configured=bool(os.getenv("DEEPSEEK_API_KEY")),
            native_web_search=False,
        )
    if name in {"local", "vllm"}:
        return ProviderConfig(
            name="local",
            model=model or os.getenv("DOSSIER_MODEL", "Qwen/Qwen3-8B"),
            base_url=os.getenv("LOCAL_MODEL_BASE_URL", "http://127.0.0.1:8001/v1"),
            api_key_configured=True,
            native_web_search=False,
        )
    raise ValueError(f"Unknown MODEL_PROVIDER '{name}'. Use openai, deepseek, or local.")


def provider_api_key(config: ProviderConfig) -> str:
    if config.name == "openai":
        return os.getenv("OPENAI_API_KEY", "")
    if config.name == "deepseek":
        return os.getenv("DEEPSEEK_API_KEY", "")
    return os.getenv("LOCAL_MODEL_API_KEY", "local")


def build_client(config: ProviderConfig) -> OpenAI:
    """Build an OpenAI SDK client for any supported compatible endpoint."""

    return OpenAI(api_key=provider_api_key(config), base_url=config.base_url)
