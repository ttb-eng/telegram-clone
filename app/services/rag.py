import os
import uuid
import logging
from typing import List

# 国内 HuggingFace 镜像，否则无法下载模型
if "HF_ENDPOINT" not in os.environ:
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import chromadb
from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger(__name__)

_chroma_client = None
_collection = None
_embedding_model = None


def _get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        logger.info("Loading embedding model (first time may download ~80MB)...")
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Embedding model loaded.")
    return _embedding_model


def _get_chroma_collection():
    global _chroma_client, _collection
    if _collection is None:
        os.makedirs(settings.chroma_db_path, exist_ok=True,)
        _chroma_client = chromadb.PersistentClient(path=settings.chroma_db_path)
        _collection = _chroma_client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"ChromaDB collection ready at {settings.chroma_db_path}")
    return _collection


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def embed_chunks(chunks: List[str]) -> List[List[float]]:
    model = _get_embedding_model()
    embeddings = model.encode(chunks, normalize_embeddings=True)
    return embeddings.tolist()


async def store_document(
    user_id: uuid.UUID, filename: str, text: str, doc_id: uuid.UUID
) -> int:
    chunks = chunk_text(text)
    if not chunks:
        return 0

    embeddings = embed_chunks(chunks)
    collection = _get_chroma_collection()

    chunk_ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "user_id": str(user_id),
            "document_id": str(doc_id),
            "filename": filename,
            "chunk_index": i,
        }
        for i in range(len(chunks))
    ]

    collection.add(
        ids=chunk_ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    logger.info(f"Stored document {doc_id}: {filename}, {len(chunks)} chunks")
    return len(chunks)


async def search_similar(
    query: str, user_id: uuid.UUID, top_k: int = 5
) -> List[dict]:
    model = _get_embedding_model()
    query_embedding = model.encode([query], normalize_embeddings=True).tolist()

    collection = _get_chroma_collection()
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
        where={"user_id": str(user_id)},
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    if results["ids"] and results["ids"][0]:
        for i in range(len(results["ids"][0])):
            distance = results["distances"][0][i]
            if distance < 0.8:

                chunks.append({
                    "id": results["ids"][0][i],
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i],
                })

    return chunks


async def delete_document(doc_id: uuid.UUID) -> None:
    collection = _get_chroma_collection()
    collection.delete(where={"document_id": str(doc_id)})
    logger.info(f"Deleted document {doc_id} from ChromaDB")
