import os
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stockpilot.db.models import Dataset


@pytest.fixture
def db():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL required: use real migrated PostgreSQL")
    engine = create_engine(url)
    with engine.connect() as connection:
        outer = connection.begin()
        with Session(
            connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as session:
            yield session
        outer.rollback()
    engine.dispose()


@pytest.fixture
def dataset(db):
    dataset = Dataset(
        name="Integration fixture",
        mode="historical",
        as_of_date=date(2023, 12, 31),
        provenance={"source": "fixture"},
    )
    db.add(dataset)
    db.flush()
    return dataset
