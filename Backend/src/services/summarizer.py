import json
import logging
import asyncio

from src.services.database import get_database_service
from src.services.embeddings import get_embedding_service
from src.services.llm import get_llm_service

logger = logging.getLogger(__name__)

DATABASE = get_database_service()

SUMMARIZE_EVERY_N = 4  # trigger after every 10 new messages

SUMMARIZER_PROMPT = """You are analyzing a user's chat history with a student handbook assistant.

Chat history:
{history}

Extract and return ONLY a JSON object with these exact keys:
{{
  "summary": "2-3 sentence summary of what the user was trying to accomplish",
  "preferred_language": "en or si or ta (detect from user messages)",
  "response_detail_level": "concise or detailed (judge from their questions)",
  "common_queries": ["topic1", "topic2", "topic3"]
}}

Return only the JSON. No explanation, no markdown fences."""


async def maybe_summarize(user_id: str) -> None:
    """
    Called after each assistant response. Checks if N new messages
    have accumulated since the last summarization, and if so, runs
    the summarizer in the background.
    """
    
    count = DATABASE.get_unsummarized_count(user_id)

    if count < SUMMARIZE_EVERY_N:
        return

    logger.info("Summarizing %d new messages for user %s", count, user_id)
    await _run_summarizer(user_id)


async def _run_summarizer(user_id: str) -> None:
    """
    Run the summarizer on the user's chat history and update the database.
    """

    try:
        prefs = DATABASE.get_preferences(user_id) or {}
        since = prefs["updated_at"] if prefs else "1970-01-01T00:00:00Z"

        raw_messages = DATABASE.get_messages_since(user_id, since)
        if not raw_messages:
            return

        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in raw_messages
        )

        llm = get_llm_service()
        response = await llm.ainvoke(SUMMARIZER_PROMPT.format(history=history_text))

        # Strip markdown fences if LLM wraps in ```json
        raw = response.strip().removeprefix("```json").removesuffix("```").strip()
        extracted = json.loads(raw)

        embedding_service = get_embedding_service() 
        loop = asyncio.get_event_loop()
        preference_vec = await loop.run_in_executor(
            None,
            embedding_service._embedding_model.embed_query,
            extracted["summary"]
        )  # get embedding for summary


        DATABASE.upsert_preferences(
            user_id=user_id,
            language=extracted.get("preferred_language", "en"),
            detail_level=extracted.get("response_detail_level", "concise"),
            common_queries=extracted.get("common_queries", []),
            summary=extracted.get("summary", ""),
            preference_vec=preference_vec,
        )
        logger.info("Preferences updated for user %s", user_id)

    except Exception as e:
        logger.error("Summarizer failed for user %s: %s", user_id, e)