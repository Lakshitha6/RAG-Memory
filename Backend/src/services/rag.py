from functools import lru_cache

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda, RunnableGenerator

from src.services.embeddings import get_embedding_service
from src.services.llm import get_llm_service


RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a helpful assistant answering questions about the student handbook.\n"
     "Use only the provided context to answer. If the answer is not in the context, "
     "say you don't have that information.\n\n"
     "User preferences: {preferences}\n\n"
     "Context:\n{context}"),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{question}"),
])


def _format_docs(docs: list[str]) -> str:
    return "\n\n".join(docs)


class RAGService:
    """ Full RAG pipeline """

    def __init__(self, k: int = 4):
        self._embedding_service = get_embedding_service()
        self._llm_service = get_llm_service()
        self._k = k
        self._stream_chain = self._build_stream_chain()

    def _retrieve(self, question: str) -> str:
        docs = self._embedding_service.search(question, k=self._k)
        return _format_docs(docs)


    def _stream_llm(self, messages_iter):
        for messages in messages_iter:
            for chunk in self._llm_service.stream(messages):
                yield chunk

    def _build_stream_chain(self):
        return (
            RunnableLambda(lambda inp: {
                "context": self._retrieve(inp["question"]),
                "question": inp["question"],
                "chat_history": inp.get("chat_history", []),
                "preferences": inp.get("preferences", ""),
            })
            | RAG_PROMPT
            | RunnableGenerator(self._stream_llm)
        )

    # For Normal testing
    def stream(self, question: str, chat_history=None, preferences: str =""):
        """ Synchronous streaming of RAG response """

        yield from self._stream_chain.stream(
            {
                "question": question,
                "chat_history": chat_history or [],
                "preferences": preferences,
            }
        )

    # For fastapi endpoint
    async def astream( self, question: str, chat_history=None, preferences: str = "",):
        docs = await self._embedding_service.asearch(question, k=self._k)
        context = _format_docs(docs)
        messages = RAG_PROMPT.invoke({
            "context": context,
            "question": question,
            "chat_history": chat_history or [],
            "preferences": preferences,
        })
        async for chunk in self._llm_service.astream(messages):
            yield chunk


@lru_cache(maxsize=1)
def get_rag_service() -> RAGService:
    return RAGService()