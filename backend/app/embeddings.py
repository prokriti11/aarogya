"""Local ONNX embeddings (no API quota, runs on free CPU hosts)."""
import asyncio
from functools import lru_cache

from fastembed import TextEmbedding

from .config import settings


@lru_cache(maxsize=1)
def _model() -> TextEmbedding:
    return TextEmbedding(settings.embed_model, cache_dir=settings.embed_cache_dir)


def embed_passages(texts: list[str]) -> list[list[float]]:
    return [v.tolist() for v in _model().passage_embed(texts, batch_size=32)]


async def embed_query(text: str) -> list[float]:
    return await asyncio.to_thread(lambda: next(iter(_model().query_embed(text))).tolist())
