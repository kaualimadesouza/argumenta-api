"""Which vendor answers, from settings. The engines never learn the answer."""

from argumenta.adapters.llm.anthropic_provider import AnthropicProvider
from argumenta.adapters.llm.provider import LlmProvider, Vendor
from argumenta.settings import Settings


def vendor_api_key(settings: Settings, vendor: Vendor) -> str:
    keys: dict[Vendor, str] = {
        "anthropic": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
        "google": settings.google_api_key,
    }
    return keys[vendor]


def build_provider(settings: Settings, vendor: Vendor, model: str, timeout: float) -> LlmProvider:
    """The two non-Claude SDKs are optional extras, so they are imported only
    when chosen: `uv sync --extra openai` (or `--extra google`)."""
    api_key = vendor_api_key(settings, vendor)
    if vendor == "openai":
        from argumenta.adapters.llm.openai_provider import OpenAiProvider

        return OpenAiProvider(api_key=api_key, model=model, timeout=timeout)
    if vendor == "google":
        from argumenta.adapters.llm.google_provider import GoogleProvider

        return GoogleProvider(api_key=api_key, model=model, timeout=timeout)
    return AnthropicProvider(api_key=api_key, model=model, timeout=timeout)
