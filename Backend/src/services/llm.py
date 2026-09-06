from functools import lru_cache
import logging
from typing import Iterator, AsyncIterator

from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.runnables import RunnableWithFallbacks

from src.utils.config_loader import get_env, load_yaml

logger = logging.getLogger(__name__)


class LLMService:
    """Wraps a primary LLM (Gemini) with automatic fallback to a secondary LLM (Groq)."""

    def __init__(self, config_path: str = "llm.yaml"):
        config = load_yaml(config_path)["providers"]
        self._primary_config = config["primary"]
        self._fallback_config = config["fallback"]

        self._primary_llm = self._build_primary(self._primary_config)
        self._fallback_llm = self._build_fallback(self._fallback_config)

    def _build_primary(self, cfg: dict) -> ChatGoogleGenerativeAI:
        return ChatGoogleGenerativeAI(
            model=str(cfg["model"]),
            api_key=get_env(cfg["api_key_env"]),
            timeout=cfg.get("timeout"),
            max_retries=cfg.get("retries", 1),
        )

    def _build_fallback(self, cfg: dict) -> ChatGroq:
        return ChatGroq(
            api_key=get_env(cfg["api_key_env"]),
            model=str(cfg["model"]),
            temperature=0.0,
            timeout=cfg.get("timeout"),
            max_retries=cfg.get("retries", 1),
        )

    def _extract_text(self, chunk) -> str:
        """Normalize chunk content across Gemini (list of dicts) and Groq (plain string)."""
        content = chunk.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                block.get("text", "") 
                for block in content 
                if isinstance(block, dict) and block.get("type") == "text"
            )
        return ""

    # Streaming + Not Asynchronous -> Normal testing
    def stream(self, prompt, **kwargs) -> Iterator:
        try:
            for chunk in self._primary_llm.stream(prompt, **kwargs):
                yield self._extract_text(chunk)
        except Exception as e:
            logger.warning("Primary stream failed [%s: %s] — falling back", type(e).__name__, e)
            for chunk in self._fallback_llm.stream(prompt, **kwargs):
                yield self._extract_text(chunk)


    # Streaming +  Asynchronous -> Fast-api
    async def astream(self, prompt, **kwargs) -> AsyncIterator:
        try:
            async for chunk in self._primary_llm.astream(prompt, **kwargs):
                yield self._extract_text(chunk)
        except Exception as e:
            logger.warning(
                "Primary stream failed [%s: %s] - restarting with fallback",
                type(e).__name__, e,
            )
            async for chunk in self._fallback_llm.astream(prompt, **kwargs):
                yield self._extract_text(chunk)


    # Non-streaming + Non-async → CLI debug, summarizer
    def invoke(self, prompt, **kwargs):
        try:
            result = self._primary_llm.invoke(prompt, **kwargs)
            return self._extract_text(result)
        except Exception as e:
            logger.warning("Primary invoke failed [%s: %s] — falling back", type(e).__name__, e)
            result = self._fallback_llm.invoke(prompt, **kwargs)
            return self._extract_text(result)

    # Non-streaming + Async → summarizer (called via asyncio.create_task)
    async def ainvoke(self, prompt, **kwargs):
        try:
            result = await self._primary_llm.ainvoke(prompt, **kwargs)
            return self._extract_text(result)
        except Exception as e:
            logger.warning("Primary ainvoke failed [%s: %s] — falling back", type(e).__name__, e)
            result = await self._fallback_llm.ainvoke(prompt, **kwargs)
            return self._extract_text(result)

@lru_cache(maxsize=1)
def get_llm_service() -> LLMService:
    """Returns a lru-cached LLMService instance."""
    return LLMService()