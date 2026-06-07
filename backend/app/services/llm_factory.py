"""LLM provider factory — switchable via MAIN_LLM_PROVIDER / FAST_LLM_PROVIDER env vars.

Supported providers: 'google', 'openai'.
"""

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import settings


def get_llm(fast: bool = False) -> BaseChatModel:
    """Return a LangChain chat model based on env config.

    Args:
        fast: If True, use the fast/cheap model (FAST_LLM_PROVIDER / FAST_LLM_MODEL).
              If False, use the main model (MAIN_LLM_PROVIDER / MAIN_LLM_MODEL).

    Raises:
        ValueError: If provider is unknown.
    """
    provider = settings.fast_llm_provider if fast else settings.main_llm_provider
    model = settings.fast_llm_model if fast else settings.main_llm_model
    temperature = settings.temperature

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            google_api_key=settings.google_api_key or None,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=settings.openai_api_key or None,
        )

    raise ValueError(f"Unknown LLM provider: {provider!r}. Expected 'google' or 'openai'.")


def get_fast_llm() -> BaseChatModel:
    """Convenience wrapper — returns the fast/cheap LLM."""
    return get_llm(fast=True)
