from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from stockpilot.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionFactory = sessionmaker(engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with SessionFactory() as session:
        yield session
