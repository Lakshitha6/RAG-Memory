from functools import lru_cache

from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langchain_qdrant import QdrantVectorStore

from src.utils.config_loader import get_env, load_yaml


class EmbeddingService:
    """ A Class that wrapped with embedding model initialization and vector search ."""

    def __init__(self, collection_name: str = "student_handbook"):
        self._collection_name = collection_name
        self._embedding_model = self._build_embedding_model()
        self._vector_store = self._build_vector_store()

    def _build_embedding_model(self) -> HuggingFaceEndpointEmbeddings:
        config = load_yaml("llm.yaml")["embeddings"]
        return HuggingFaceEndpointEmbeddings(
            huggingfacehub_api_token=get_env("HF_TOKEN"),
            model=str(config["model"]),
        )

    def _build_vector_store(self) -> QdrantVectorStore:
        return QdrantVectorStore.from_existing_collection(
            collection_name=self._collection_name,
            embedding=self._embedding_model,
            url=get_env("QDRANT_URL"),
            api_key=get_env("QDRANT_API_KEY"),
            prefer_grpc=True,
            content_payload_key="text",
        )

    # Use normal testing
    def search(self, query: str, k: int = 2) -> list[str]:
        results = self._vector_store.similarity_search(query, k=k)
        return [res.page_content for res in results]
    
    # Use in fastapi endpoint
    async def asearch(self, query: str, k: int = 2) -> list[str]:
        results = await self._vector_store.asimilarity_search(query, k=k)
        return [res.page_content for res in results]


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """Retrieves the process-wide cached instance of the EmbeddingService.

    This service initializes a connection to the Qdrant vector database using 
    HuggingFace embeddings configured from `llm.yaml`. It manages connection pooling 
    and handles similarity searches.

    Returns:
        EmbeddingService: A lru-cached service instance capable of vector search.

    Example:
        ```python
        from src.services.embeddings import get_embedding_service

        # Initialize or retrieve cached service
        service = get_embedding_service()

        # Perform a vector similarity search
        results = service.search(query="what_ever_query", k=2 or any number of results need.)
        print(results)  # Returns: list[str] (page contents)
        ```
    """

    return EmbeddingService()