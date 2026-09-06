# src/main.py
# import asyncio

# from src.services.rag import get_rag_service


# async def main():
#     rag = get_rag_service()
#     async for chunk in rag.astream("What is the repeat course policy?"):
#         print(chunk, end="", flush=True)


# if __name__ == "__main__":
#     asyncio.run(main())


# from src.services.rag import get_rag_service


# def main():
#     rag = get_rag_service()
#     for chunk in rag.stream("What is the repeat course policy?"):
#         print(chunk, end="", flush=True)


# if __name__ == "__main__":
#     main()


import asyncio
import logging
import json

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.dependencies import get_current_user
from src.routers.auth import router as auth_router
from src.routers.sessions import router as sessions_router
from src.services.database import get_database_service
from src.services.rag import get_rag_service
from src.utils.preference import build_preference_snippet
from src.services.summarizer import maybe_summarize

logging.basicConfig(level=logging.INFO)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(sessions_router)

class ChatRequest(BaseModel):
    question: str
    session_id: str | None = None

async def sse_generator(request: ChatRequest, user: dict):
    db = get_database_service()
    rag = get_rag_service()
    user_id =  str(user["user_id"])

    session_id = db.get_or_create_session(user_id, request.session_id)

    # Load history and preference

    chat_history = db.get_recent_messages(session_id,limit=10)
    prefs = db.get_preferences(user_id)
    preference_snippet = build_preference_snippet(prefs)

    # Save user message immediately
    db.save_message(session_id=session_id, role="user", content=request.question)

    # set session title from first question
    db.set_session_title_if_empty(session_id=session_id, question=request.question)

    yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"

    full_response = []

    try:
        async for chunk in rag.astream(
            question=request.question,
            chat_history=chat_history,
            preferences=preference_snippet
        ):
            full_response.append(chunk)
            yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

    finally:
        # save full response in database
        if full_response:
            db.save_message(session_id=session_id, role="assistant", content="".join(full_response))

        # Trigger summarizer in background
        asyncio.create_task(maybe_summarize(user_id))

        yield f"data: {json.dumps({'type': 'done'})}\n\n"


@app.post("/chat")
async def chat(request: ChatRequest, user: dict = Depends(get_current_user)):
    return StreamingResponse(
        sse_generator(request, user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok"}