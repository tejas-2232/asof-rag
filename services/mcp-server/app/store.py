from collections.abc import Iterable
from datetime import datetime
from typing import Protocol

from fastembed import TextEmbedding
from qdrant_client import QdrantClient, models

from .models import Chunk, QueryHit


class Embedder(Protocol):
    def embed(self, documents: Iterable[str]) -> Iterable[object]: ...


class QdrantStore:
    def __init__(
        self,
        url: str | None = None,
        model_name: str = "BAAI/bge-small-en-v1.5",
        *,
        client: QdrantClient | None = None,
        embedder: Embedder | None = None,
    ):
        self.client = client or QdrantClient(url=url)
        self.model_name = model_name
        self._embedder = embedder

    @property
    def embedder(self) -> Embedder:
        if self._embedder is None:
            self._embedder = TextEmbedding(model_name=self.model_name)
        return self._embedder

    def ping(self) -> bool:
        self.client.get_collections()
        return True

    def create_collection(self, name: str, chunks: list[Chunk]) -> None:
        if not chunks:
            raise ValueError("Cannot create an index without chunks")
        vectors = [list(vector) for vector in self.embedder.embed(chunk.text for chunk in chunks)]
        if not vectors:
            raise RuntimeError("Embedding model returned no vectors")
        self.client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(
                size=len(vectors[0]),
                distance=models.Distance.COSINE,
            ),
        )
        self.client.upsert(
            collection_name=name,
            wait=True,
            points=[
                models.PointStruct(
                    id=chunk.id,
                    vector=vector,
                    payload=chunk.model_dump(mode="json"),
                )
                for chunk, vector in zip(chunks, vectors, strict=True)
            ],
        )

    def query(
        self,
        collection: str,
        text: str,
        as_of: datetime,
        limit: int,
        ticker: str | None = None,
        *,
        temporal_filter: bool = True,
    ) -> list[QueryHit]:
        must: list[models.FieldCondition] = []
        if temporal_filter:
            # This predicate is sent to Qdrant, so exclusion occurs before ranking.
            must.append(
                models.FieldCondition(
                    key="filed_at_epoch",
                    range=models.Range(lte=int(as_of.timestamp())),
                )
            )
        if ticker:
            must.append(
                models.FieldCondition(
                    key="ticker",
                    match=models.MatchValue(value=ticker.strip().upper()),
                )
            )
        query_filter = models.Filter(must=must) if must else None
        vector = list(next(iter(self.embedder.embed([text]))))
        result = self.client.query_points(
            collection_name=collection,
            query=vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
        return [
            QueryHit(score=point.score, chunk=Chunk.model_validate(point.payload))
            for point in result.points
            if point.payload
        ]
