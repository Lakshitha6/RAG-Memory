# from functools import lru_cache

# from langchain_huggingface import HuggingFaceEndpointEmbeddings
# from langchain_qdrant import QdrantVectorStore

# from src.utils.config_loader import get_env, load_yaml


# class EmbeddingService:
#     """ A Class that wrapped with embedding model initialization and vector search ."""

#     def __init__(self, collection_name: str = "student_handbook"):
#         self._collection_name = collection_name
#         self._embedding_model = self._build_embedding_model()
#         self._vector_store = self._build_vector_store()

#     def _build_embedding_model(self) -> HuggingFaceEndpointEmbeddings:
#         config = load_yaml("llm.yaml")["embeddings"]
#         return HuggingFaceEndpointEmbeddings(
#             huggingfacehub_api_token=get_env("HF_TOKEN"),
#             model=str(config["model"]),
#         )

#     def _build_vector_store(self) -> QdrantVectorStore:
#         return QdrantVectorStore.from_existing_collection(
#             collection_name=self._collection_name,
#             embedding=self._embedding_model,
#             url=get_env("QDRANT_URL"),
#             api_key=get_env("QDRANT_API_KEY"),
#             prefer_grpc=True,
#             content_payload_key="text",
#         )

#     # Use normal testing
#     def search(self, query: str, k: int = 2) -> list[str]:
#         results = self._vector_store.similarity_search(query, k=k)
#         return [res.page_content for res in results]
    
#     # Use in fastapi endpoint
#     async def asearch(self, query: str, k: int = 2) -> list[str]:
#         results = await self._vector_store.asimilarity_search(query, k=k)
#         return [res.page_content for res in results]


# @lru_cache(maxsize=1)
# def get_embedding_service() -> EmbeddingService:
#     """Retrieves the process-wide cached instance of the EmbeddingService.

#     This service initializes a connection to the Qdrant vector database using 
#     HuggingFace embeddings configured from `llm.yaml`. It manages connection pooling 
#     and handles similarity searches.

#     Returns:
#         EmbeddingService: A lru-cached service instance capable of vector search.

#     Example:
#         ```python
#         from src.services.embeddings import get_embedding_service

#         # Initialize or retrieve cached service
#         service = get_embedding_service()

#         # Perform a vector similarity search
#         results = service.search(query="what_ever_query", k=2 or any number of results need.)
#         print(results)  # Returns: list[str] (page contents)
#         ```
#     """

#     return EmbeddingService()


from functools import lru_cache

from langchain_huggingface import HuggingFaceEndpointEmbeddings
from qdrant_client import QdrantClient, AsyncQdrantClient, models

from src.utils.config_loader import get_env, load_yaml


class EmbeddingService:
    """Wraps embedding model initialization and hybrid parent-child vector search."""

    SPARSE_MODEL_NAME = "qdrant/bm25"

    def __init__(
        self,
        child_collection_name: str = "student_handbook_child",
        parent_collection_name: str = "student_handbook_parent",
    ):
        self._child_collection = child_collection_name
        self._parent_collection = parent_collection_name
        self._embedding_model = self._build_embedding_model()
        self._client = self._build_client()
        self._aclient = self._build_async_client()

    def _build_embedding_model(self) -> HuggingFaceEndpointEmbeddings:
        config = load_yaml("llm.yaml")["embeddings"]
        return HuggingFaceEndpointEmbeddings(
            huggingfacehub_api_token=get_env("HF_TOKEN"),
            model=str(config["model"]),
        )

    def _build_client(self) -> QdrantClient:
        return QdrantClient(
            url=get_env("QDRANT_URL"),
            api_key=get_env("QDRANT_API_KEY"),
            prefer_grpc=True,
        )

    def _build_async_client(self) -> AsyncQdrantClient:
        return AsyncQdrantClient(
            url=get_env("QDRANT_URL"),
            api_key=get_env("QDRANT_API_KEY"),
            prefer_grpc=True,
        )

    def _build_prefetch(self, dense_vec: list[float], query_text: str, k: int):
        return [
            models.Prefetch(query=dense_vec, limit=k * 2),
            models.Prefetch(
                query=models.Document(text=query_text, model=self.SPARSE_MODEL_NAME),
                using="text-sparse",
                limit=k * 2,
            ),
        ]

    @staticmethod
    def _dedup_parent_ids(points, k: int) -> list[str]:
        ordered_ids, seen = [], set()
        for r in points:
            pid = r.payload["parent_id"]
            if pid not in seen:
                seen.add(pid)
                ordered_ids.append(pid)
            if len(ordered_ids) == k:
                break
        return ordered_ids

    # Use in normal / sync contexts (CLI, tests)
    def search(self, query: str, k: int = 2) -> list[str]:
        dense_vec = self._embedding_model.embed_query(query)
        results = self._client.query_points(
            collection_name=self._child_collection,
            prefetch=self._build_prefetch(dense_vec, query, k),
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=k * 2,
            with_payload=True,
        )
        ordered_ids = self._dedup_parent_ids(results.points, k)
        parents = self._client.retrieve(
            collection_name=self._parent_collection, ids=ordered_ids, with_payload=True
        )
        parent_map = {p.id: p.payload for p in parents}
        return [parent_map[pid]["text"] for pid in ordered_ids]

    # Use in fastapi endpoint
    async def asearch(self, query: str, k: int = 2) -> list[str]:
        dense_vec = await self._embedding_model.aembed_query(query)
        results = await self._aclient.query_points(
            collection_name=self._child_collection,
            prefetch=self._build_prefetch(dense_vec, query, k),
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=k * 2,
            with_payload=True,
        )
        ordered_ids = self._dedup_parent_ids(results.points, k)
        parents = await self._aclient.retrieve(
            collection_name=self._parent_collection, ids=ordered_ids, with_payload=True
        )
        parent_map = {p.id: p.payload for p in parents}
        return [parent_map[pid]["text"] for pid in ordered_ids]


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """Retrieves the process-wide cached instance of the EmbeddingService."""
    return EmbeddingService()