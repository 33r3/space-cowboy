"""Engine and sessions. SPACE_COWBOY_DB is a SQLAlchemy URL: SQLite while
developing (the default, data/space_cowboy.db), Postgres when hosted."""
import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

DEFAULT_URL = 'sqlite:///' + os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'space_cowboy.db')


def make_engine(url: str | None = None):
    url = url or os.environ.get('SPACE_COWBOY_DB', DEFAULT_URL)
    engine = create_engine(url)
    if engine.dialect.name == 'sqlite':
        @event.listens_for(engine, 'connect')
        def _sqlite_pragmas(conn, _):
            cur = conn.cursor()
            cur.execute('PRAGMA foreign_keys=ON')
            cur.execute('PRAGMA journal_mode=WAL')
            cur.close()
    return engine


def make_sessionmaker(engine):
    return sessionmaker(engine, expire_on_commit=False)
