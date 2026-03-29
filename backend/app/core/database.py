from sqlmodel import SQLModel, create_engine, Session
from typing import Generator
from app.core.config import settings

# connect_args only needed for SQLite. For Postgres, it's not required.
# pool_pre_ping=True ensures stale connections from Supabase are recycled.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)


def create_db_and_tables() -> None:
    """Create all tables. Called once at startup."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a DB session per request.
    Automatically commits on success, rolls back on exception,
    and always closes the session.
    """
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise