"""PDF -> cleaned pages -> section-aware chunks with page provenance -> embeddings -> Postgres."""
import hashlib
import io
import re
from dataclasses import dataclass

from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .embeddings import embed_passages
from .models import Chunk, Document

TARGET_WORDS = 280
OVERLAP_WORDS = 40
HEADING_RE = re.compile(r"^(\d+(\.\d+)*\.?\s+[A-Z][^\n]{2,80}|[A-Z][A-Z0-9 &/,\-()]{4,80})$")


@dataclass
class Para:
    text: str
    page: int
    section: str | None


def _clean(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"-\n(\w)", r"\1", text)          # de-hyphenate line breaks
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _paragraphs(reader: PdfReader) -> list[Para]:
    paras, section = [], None
    for page_no, page in enumerate(reader.pages, start=1):
        raw = _clean(page.extract_text() or "")
        buf: list[str] = []
        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                if buf:
                    paras.append(Para(" ".join(buf), page_no, section)); buf = []
                continue
            if HEADING_RE.match(line) and len(line.split()) <= 12:
                if buf:
                    paras.append(Para(" ".join(buf), page_no, section)); buf = []
                section = line.title() if line.isupper() else line
                continue
            buf.append(line)
            if line.endswith((".", ":", ";")) and len(" ".join(buf).split()) > 60:
                paras.append(Para(" ".join(buf), page_no, section)); buf = []
        if buf:
            paras.append(Para(" ".join(buf), page_no, section))
    return [p for p in paras if len(p.text.split()) >= 5]


def chunk_paragraphs(paras: list[Para]) -> list[dict]:
    """Greedy pack paragraphs to ~TARGET_WORDS; never cross a section boundary; overlap tail words."""
    chunks, cur, words = [], [], 0

    def flush():
        nonlocal cur, words
        if not cur:
            return
        text = " ".join(p.text for p in cur)
        chunks.append({
            "content": text,
            "page_start": cur[0].page,
            "page_end": cur[-1].page,
            "section": cur[0].section,
            "word_count": len(text.split()),
        })
        tail = " ".join(text.split()[-OVERLAP_WORDS:])
        cur = [Para(tail, cur[-1].page, cur[-1].section)]
        words = OVERLAP_WORDS

    for p in paras:
        n = len(p.text.split())
        if cur and (p.section != cur[-1].section):
            flush(); cur, words = [], 0
        if words + n > TARGET_WORDS and words > OVERLAP_WORDS:
            flush()
        cur.append(p); words += n
    if cur and words > OVERLAP_WORDS:
        flush()
    return chunks


async def ingest_pdf(session: AsyncSession, data: bytes, filename: str, title: str | None = None) -> dict:
    sha = hashlib.sha256(data).hexdigest()
    existing = await session.scalar(select(Document).where(Document.sha256 == sha))
    if existing:
        return {"document_id": str(existing.id), "skipped": True, "reason": "already ingested"}

    reader = PdfReader(io.BytesIO(data))
    raw_chunks = chunk_paragraphs(_paragraphs(reader))
    if not raw_chunks:
        raise ValueError("No extractable text (scanned PDF?)")

    # Prefix section title so headings contribute to the embedding
    vectors = embed_passages([f"{c['section'] or ''}\n{c['content']}" for c in raw_chunks])

    doc = Document(title=title or filename.rsplit(".", 1)[0], source=filename, sha256=sha, num_pages=len(reader.pages))
    doc.chunks = [Chunk(ordinal=i, embedding=v, **c) for i, (c, v) in enumerate(zip(raw_chunks, vectors))]
    session.add(doc)
    await session.commit()
    return {"document_id": str(doc.id), "chunks": len(raw_chunks), "pages": len(reader.pages), "skipped": False}
