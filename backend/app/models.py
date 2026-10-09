import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .config import settings
from .db import Base


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(300))
    source: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64), unique=True)   # idempotent re-ingestion
    num_pages: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    page_start: Mapped[int] = mapped_column(Integer)
    page_end: Mapped[int] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)
    word_count: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embed_dim))
    # Generated full-text column -> keyword half of hybrid retrieval
    tsv = mapped_column(TSVECTOR, Computed("to_tsvector('english', content)", persisted=True))
    document: Mapped[Document] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_chunks_embedding_hnsw", "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class BotVersion(Base):
    """A versioned bot config. The eval harness compares these against each other."""
    __tablename__ = "bot_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    model: Mapped[str] = mapped_column(String(100))
    system_prompt: Mapped[str] = mapped_column(Text)
    top_k: Mapped[int] = mapped_column(Integer, default=5)
    min_similarity: Mapped[float] = mapped_column(Float, default=0.55)   # retrieval confidence gate
    temperature: Mapped[float] = mapped_column(Float, default=0.1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bot_version_id: Mapped[int] = mapped_column(ForeignKey("bot_versions.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20), default="web")      # web | eval
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Message(Base):
    """Every bot turn is fully traced so it can be scored later."""
    __tablename__ = "messages"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))                         # user | assistant
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(30))                # answered | not_found | out_of_scope | clarify | error
    retrieved: Mapped[list | None] = mapped_column(JSONB)                 # [{chunk_id, rank, similarity, rrf}]
    cited_chunk_ids: Mapped[list | None] = mapped_column(JSONB)
    trace: Mapped[dict | None] = mapped_column(JSONB)                     # latency, tokens, gate, invalid citations
    # client-side timestamp: user + assistant rows share one transaction, so now() would tie
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ----------------------------- Evaluation -----------------------------

class TestSuite(Base):
    __tablename__ = "test_suites"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    cases: Mapped[list["TestCase"]] = relationship(back_populates="suite", cascade="all, delete-orphan",
                                                   order_by="TestCase.id")


class TestCase(Base):
    __tablename__ = "test_cases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    suite_id: Mapped[int] = mapped_column(ForeignKey("test_suites.id", ondelete="CASCADE"), index=True)
    case_key: Mapped[str] = mapped_column(String(40))
    category: Mapped[str] = mapped_column(String(30))          # in_scope | not_in_kb | out_of_scope | ambiguous | adversarial | multilingual
    question: Mapped[str] = mapped_column(Text)
    expected_statuses: Mapped[list] = mapped_column(JSONB)     # acceptable bot statuses
    expected_behavior: Mapped[str] = mapped_column(Text, default="")   # plain-language note for the judge
    must_include: Mapped[list] = mapped_column(JSONB, default=list)    # "a|b" = either term
    must_not_include: Mapped[list] = mapped_column(JSONB, default=list)
    suite: Mapped[TestSuite] = relationship(back_populates="cases")


class EvalRun(Base):
    __tablename__ = "eval_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    suite_id: Mapped[int] = mapped_column(ForeignKey("test_suites.id"), index=True)
    bot_version_id: Mapped[int] = mapped_column(ForeignKey("bot_versions.id"), index=True)
    judge_model: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="queued")   # queued | running | done | failed
    total: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bot: Mapped[BotVersion] = relationship()
    suite: Mapped[TestSuite] = relationship()


class EvalResult(Base):
    __tablename__ = "eval_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("eval_runs.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(30))
    answer: Mapped[str] = mapped_column(Text)
    context: Mapped[list] = mapped_column(JSONB, default=list)          # excerpts the bot actually saw
    trace: Mapped[dict] = mapped_column(JSONB, default=dict)
    checks: Mapped[dict] = mapped_column(JSONB, default=dict)           # deterministic checks
    judge: Mapped[dict | None] = mapped_column(JSONB)                   # LLM-judge scores + rationale
    passed: Mapped[bool] = mapped_column(default=False)
    needs_review: Mapped[bool] = mapped_column(default=False)
    review_reasons: Mapped[list] = mapped_column(JSONB, default=list)
    case: Mapped[TestCase] = relationship()
    label: Mapped["HumanLabel | None"] = relationship(back_populates="result", uselist=False, cascade="all, delete-orphan")


class HumanLabel(Base):
    __tablename__ = "human_labels"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("eval_results.id", ondelete="CASCADE"), unique=True)
    passed: Mapped[bool] = mapped_column()
    hallucination: Mapped[bool] = mapped_column(default=False)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    result: Mapped[EvalResult] = relationship(back_populates="label")
