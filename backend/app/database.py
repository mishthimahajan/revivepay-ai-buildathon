from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import sessionmaker

from .config import settings


database_url = settings.database_url

# Support older PostgreSQL URL formats.
if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql://",
        1,
    )

engine_arguments = {
    "pool_pre_ping": True,
}

if database_url.startswith("sqlite"):
    engine_arguments["connect_args"] = {
        "check_same_thread": False,
    }

engine = create_engine(
    database_url,
    **engine_arguments,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


def get_db():
    database = SessionLocal()

    try:
        yield database
    finally:
        database.close()