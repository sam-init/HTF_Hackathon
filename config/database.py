"""
config/database.py
------------------
Async SQLite database setup using aiosqlite.
Creates tables on startup.
"""
import aiosqlite
from config.settings import get_settings

settings = get_settings()
DB_PATH = settings.database_url.replace("sqlite:///", "")


async def get_db():
    """Async context manager – yields a DB connection."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db


async def init_db():
    """Create all tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS reviews (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_full   TEXT NOT NULL,
                pr_number   INTEGER NOT NULL,
                status      TEXT DEFAULT 'pending',
                summary     TEXT,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS review_comments (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id   INTEGER REFERENCES reviews(id),
                agent       TEXT,
                file_path   TEXT,
                line        INTEGER,
                issue       TEXT,
                suggestion  TEXT,
                severity    TEXT DEFAULT 'medium',
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS doc_jobs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_url    TEXT,
                status      TEXT DEFAULT 'pending',
                result_path TEXT,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await db.commit()
