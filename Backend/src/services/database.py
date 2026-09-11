from functools import lru_cache
from mimetypes import init
from langchain_core.messages import HumanMessage, AIMessage
from supabase import create_client, Client

from src.utils.config_loader import get_env


class DatabaseService:

    """ All database operations are handled here """

    def __init__(self):
        self._client : Client = create_client(get_env("SUPABASE_URL"), get_env("SUPABASE_SERVICE_ROLE_KEY"))


    # ---------------------  User management ---------------------

    def create_user(self, name: str, email: str, password_hash: str) -> dict:
        res = (
            self._client.table("users")
            .insert({"name": name, "email": email, "password_hash": password_hash})
            .execute()
        )
        return res.data[0]

    def get_user_by_email(self, email: str) -> dict | None:
        res = (
            self._client.table("users")
            .select("user_id, name, email, password_hash")
            .eq("email", email)
            .maybe_single()
            .execute()
        )
        return res.data if res else None

    def get_user_by_id(self, user_id: str) -> dict | None:
        res = (
            self._client.table("users")
            .select("user_id, name, email")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        return res.data if res else None


    # ---------------------  Session management ---------------------

    def get_or_create_session(self, user_id: str, session_id: str | None) -> dict:
        """ Return existing active session or create a new one. """

        if session_id:
            res = (
                self._client.table("chat_sessions")
                .select("session_id")
                .eq("session_id", session_id)
                .eq("is_active", True)
                .maybe_single()
                .execute()
            )
            if res and res.data:
                return res.data["session_id"]

        res = (
            self._client.table("chat_sessions")
            .insert({"user_id": user_id, "is_active": True})
            .execute()
        )
        return res.data[0]["session_id"]


    def close_session(self, session_id: str) -> None:
        from datetime import datetime, timezone

        self._client.table("chat_sessions").update(
            {"is_active": False, "ended_at": datetime.now(timezone.utc).isoformat()}
        ).eq("session_id", session_id).execute()


    def close_expired_sessions(self, expiry_minutes: int = 600) -> None:
        self._client.rpc(
            "close_expired_sessions",
            {"expiry_minutes": expiry_minutes}
        ).execute()

    # --------------------- Message history ---------------------

    def get_recent_messages(
        self, session_id: str, limit: int = 10
    ) -> list[HumanMessage | AIMessage]:
        
        """Pull last N messages via the SQL helper function, return as LangChain objects."""

        res = self._client.rpc(
            "get_recent_messages",
            {"p_session_id": session_id, "p_limit": limit},
        ).execute()

        messages = []
        for row in res.data or []:
            if row["role"] == "user":
                messages.append(HumanMessage(content=row["content"]))
            elif row["role"] == "assistant":
                messages.append(AIMessage(content=row["content"]))

        return messages


    def save_message(self, session_id: str, role: str, content: str, metadata: dict | None = None,) -> None:

        self._client.table("chat_messages").insert(
            {
                "session_id": session_id,
                "role": role,
                "content": content,
                "metadata": metadata or {},
            }
        ).execute()


    def get_unsummarized_count(self, user_id: str) -> int:
        res = self._client.rpc(
            "unsummarized_message_count",
            {"p_user_id": user_id},
        ).execute()
        return res.data or 0


    # --------------------- User preferences ---------------------

    def get_preferences(self, user_id: str) -> dict | None:
        res = (
            self._client.table("user_preferences")
            .select("preferred_language, response_detail_level, common_queries, summary, updated_at")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        return res.data if res else None


    def upsert_preferences(
        self,
        user_id: str,
        language: str,
        detail_level: str,
        common_queries: list[str],
        summary: str,
        preference_vec: list[float],
    ) -> None:
        self._client.table("user_preferences").upsert(
            {
                "user_id": user_id,
                "preferred_language": language,
                "response_detail_level": detail_level,
                "common_queries": common_queries,
                "summary": summary,
                "preference_vec": preference_vec,
            },
            on_conflict="user_id",
        ).execute()



    # --------------------- Get history to summarize ---------------------
    
    def get_messages_since( self, user_id: str, since_timestamp: str) -> list[dict]:

        """Pull all messages across sessions after a given timestamp for summarization."""

        res = (
            self._client.table("chat_messages")
            .select("role, content, message_timestamp")
            .in_(
                "session_id",
                self._client.table("chat_sessions")
                .select("session_id")
                .eq("user_id", user_id)
                .execute()
                .data
                and [
                    r["session_id"]
                    for r in self._client.table("chat_sessions")
                    .select("session_id")
                    .eq("user_id", user_id)
                    .execute()
                    .data
                ]
                or [],
            )
            .gt("message_timestamp", since_timestamp)
            .order("message_timestamp", desc=False)
            .execute()
        )
        return res.data or []


    def set_session_title_if_empty(self, session_id: str, question: str) -> None:
        """Sets title from first question only - ignores if title already exists."""

        title = question.strip()[:20].rstrip() + ("..." if len(question) > 20 else "")
        self._client.table("chat_sessions").update(
            {"title": title}
        ).eq("session_id", session_id).is_("title", "null").execute()


    def get_user_sessions(self, user_id: str) -> list[dict]:
        """List all sessions for a user, newest first."""
        res = (
            self._client.table("chat_sessions")
            .select("session_id, title, started_at, ended_at, is_active")
            .eq("user_id", user_id)
            .order("started_at", desc=True)
            .execute()
        )
        return res.data or []


    def get_session_messages(self, session_id: str, user_id: str) -> list[dict]:
        """Get all messages for a session — verifies session belongs to user."""

        session = (
            self._client.table("chat_sessions")
            .select("session_id")
            .eq("session_id", session_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        if not session or not session.data:
            return None

        res = (
            self._client.table("chat_messages")
            .select("id, role, content, message_timestamp, metadata")
            .eq("session_id", session_id)
            .order("message_timestamp", desc=False)
            .execute()
        )
        return res.data or []

@lru_cache(maxsize=1)
def get_database_service() -> DatabaseService:
    return DatabaseService()