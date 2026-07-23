"""
Database module — SQLAlchemy ORM models and session management.

Tables:
  - promoters:        Stores promoter identity (name + IC number).
  - submissions:      Every uploaded image is recorded here with OCR results.
  - valid_usernames:  Only first-seen usernames land here. The UNIQUE constraint
                      on `username` is the core anti-duplicate mechanism.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, Column, Integer, String, Text,
    DateTime, ForeignKey, CheckConstraint, Index, Float, Boolean, Table, text
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

from config import DATABASE_URL

# ──────────────────────────────────────────────
# Engine & Session
# ──────────────────────────────────────────────
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite + FastAPI
    echo=False,  # Set True for SQL debug logging
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ──────────────────────────────────────────────
# ORM Models
# ──────────────────────────────────────────────

# Many-to-many: which events each promoter is assigned to
promoter_events = Table(
    "promoter_events",
    Base.metadata,
    Column("promoter_id", Integer, ForeignKey("promoters.id"), primary_key=True),
    Column("event_id", Integer, ForeignKey("events.id"), primary_key=True),
)


class Event(Base):
    """A campaign event / activation location, managed from the dashboard."""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    active = Column(Boolean, nullable=False, default=True)  # open events show on the phone
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Promoter(Base):
    """A promoter identified by their unique IC number."""
    __tablename__ = "promoters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    ic_number = Column(String(50), nullable=False, unique=True)
    gender = Column(String(10), nullable=True)
    avatar = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    submissions = relationship("Submission", back_populates="promoter", lazy="dynamic")
    valid_usernames = relationship("ValidUsername", back_populates="promoter", lazy="dynamic")
    events = relationship("Event", secondary=promoter_events, backref="promoters")

    # Index for fast IC lookups
    __table_args__ = (
        Index("idx_promoters_ic", "ic_number"),
    )


class Submission(Base):
    """
    Each uploaded screenshot creates one Submission record.
    Status is one of: 'valid', 'duplicate', 'ocr_failed'.
    """
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    promoter_id = Column(Integer, ForeignKey("promoters.id"), nullable=False)
    batch_id = Column(String(36), nullable=True, index=True)  # UUID grouping uploads from same submission
    extracted_username = Column(String(100), nullable=True)  # NULL if OCR failed or pending
    full_name = Column(String(100), nullable=True)           # Member's full name read from the screenshot
    member_id = Column(String(50), nullable=True)            # Membership number read from the screenshot
    event = Column(String(100), nullable=True, index=True)   # Activation/location this signup belongs to
    image_path = Column(String(500), nullable=False)         # Relative to uploads/
    status = Column(String(20), nullable=False, default="pending")
    ocr_raw_text = Column(Text, nullable=True)               # Full OCR output for debugging
    
    # Performance logging columns
    ocr_time = Column(Float, nullable=True)
    rule_time = Column(Float, nullable=True)
    matching_time = Column(Float, nullable=True)
    total_time = Column(Float, nullable=True)
    ocr_confidence = Column(Float, nullable=True)
    candidate_score = Column(Integer, nullable=True)
    matched_name = Column(String(100), nullable=True)
    similarity = Column(Float, nullable=True)
    llm_used = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint(
            "status IN ('valid', 'duplicate', 'ocr_failed', 'pending')",
            name="check_submission_status"
        ),
        Index("idx_submissions_promoter", "promoter_id"),
        Index("idx_submissions_status", "status"),
        Index("idx_submissions_batch", "batch_id"),
    )

    # Relationships
    promoter = relationship("Promoter", back_populates="submissions")


class ValidUsername(Base):
    """
    Only first-seen usernames are inserted here.
    The UNIQUE constraint on `username` is the database-level anti-duplicate lock:
    even concurrent inserts of the same username will result in only ONE success.
    """
    __tablename__ = "valid_usernames"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Username is NOT globally unique — different people share names (two "Siang"s).
    username = Column(String(100), nullable=False)
    member_id = Column(String(50), nullable=True)  # the authoritative unique key when present
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=False)
    promoter_id = Column(Integer, ForeignKey("promoters.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        # Member ID is unique when present (NULLs are distinct in SQLite)
        Index("idx_valid_member_id", "member_id", unique=True),
        # Fallback backstop: when OCR read no member ID, the username must be unique
        Index("idx_valid_username_noid", "username", unique=True, sqlite_where=text("member_id IS NULL")),
    )

    # Relationships
    promoter = relationship("Promoter", back_populates="valid_usernames")


# ──────────────────────────────────────────────
# Initialization & Dependency Injection
# ──────────────────────────────────────────────

def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency that provides a DB session and auto-closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
