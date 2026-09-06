from fastapi import APIRouter, Depends, HTTPException, status

from src.dependencies import get_current_user
from src.services.database import get_database_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("")
def list_sessions(user: dict = Depends(get_current_user)):
    """
    Returns all chat sessions for the logged-in user.
    Frontend uses this to render the sidebar session list.
    """

    db = get_database_service()
    sessions = db.get_user_sessions(str(user["user_id"]))

    return {
        "sessions": [
            {
                "session_id": s["session_id"],
                "title": s["title"] or "Untitled",
                "started_at": s["started_at"],
                "ended_at": s["ended_at"],
                "is_active": s["is_active"],
            }
            for s in sessions
        ]
    }



@router.get("/{session_id}/messages")
def get_session_messages( session_id: str, user: dict = Depends(get_current_user)):
    """
    Returns all messages for a specific session.
    Frontend uses this when user clicks a session in the sidebar.
    """

    db = get_database_service()
    messages = db.get_session_messages(session_id, str(user["user_id"]))

    if messages is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return {
        "session_id": session_id,
        "messages": [
            {
                "id": m["id"],
                "role": m["role"],
                "content": m["content"],
                "timestamp": m["message_timestamp"],
            }
            for m in messages
        ],
    }


@router.delete("/{session_id}")
def delete_session(
    session_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete a session and all its messages (CASCADE handles messages)."""
    db = get_database_service()

    session = db.get_session_messages(session_id, str(user["user_id"]))
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    db._client.table("chat_sessions").delete().eq(
        "session_id", session_id
    ).execute()

    return {"detail": "Session deleted"}