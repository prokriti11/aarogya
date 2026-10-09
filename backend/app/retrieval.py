"""Hybrid retrieval: pgvector cosine + Postgres full-text, fused with Reciprocal Rank Fusion."""
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .embeddings import embed_query

RRF_K = 60
CANDIDATES = 20

HYBRID_SQL = text(f"""
WITH vec AS (
    SELECT id, 1 - (embedding <=> CAST(:qvec AS vector)) AS sim,
           row_number() OVER (ORDER BY embedding <=> CAST(:qvec AS vector)) AS r
    FROM chunks
    ORDER BY embedding <=> CAST(:qvec AS vector)
    LIMIT {CANDIDATES}
),
kw AS (
    SELECT c.id, row_number() OVER (ORDER BY ts_rank_cd(c.tsv, q) DESC) AS r
    FROM chunks c, websearch_to_tsquery('english', :q) q
    WHERE c.tsv @@ q
    ORDER BY ts_rank_cd(c.tsv, q) DESC
    LIMIT {CANDIDATES}
)
SELECT c.id, c.content, c.page_start, c.page_end, c.section, d.title,
       vec.sim AS similarity,
       COALESCE(1.0 / ({RRF_K} + vec.r), 0) + COALESCE(1.0 / ({RRF_K} + kw.r), 0) AS rrf
FROM chunks c
JOIN documents d ON d.id = c.document_id
LEFT JOIN vec ON vec.id = c.id
LEFT JOIN kw  ON kw.id  = c.id
WHERE vec.id IS NOT NULL OR kw.id IS NOT NULL
ORDER BY rrf DESC
LIMIT :k
""")


@dataclass
class Hit:
    chunk_id: str
    content: str
    title: str
    section: str | None
    page_start: int
    page_end: int
    similarity: float | None
    rrf: float


async def retrieve(session: AsyncSession, query: str, k: int) -> tuple[list[Hit], float]:
    """Returns fused top-k hits and the best raw cosine similarity (used as the confidence gate)."""
    qvec = await embed_query(query)
    rows = (await session.execute(HYBRID_SQL, {"qvec": str(qvec), "q": query, "k": k})).mappings().all()
    hits = [Hit(str(r["id"]), r["content"], r["title"], r["section"], r["page_start"], r["page_end"],
                float(r["similarity"]) if r["similarity"] is not None else None, float(r["rrf"])) for r in rows]
    top_sim = max((h.similarity for h in hits if h.similarity is not None), default=0.0)
    return hits, top_sim
