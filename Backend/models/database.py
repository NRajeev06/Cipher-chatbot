import logging
import sys
import subprocess
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from core.config import settings

logger = logging.getLogger("cipher.database")
Base = declarative_base()

def _migrate_schema(target_engine):
    """
    Dynamically applies non-destructive schema migrations (such as adding verification columns)
    to existing tables on either PostgreSQL or SQLite.
    """
    for col_def in [
        "ALTER TABLE users ADD COLUMN api_key VARCHAR;",
        "ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE users ADD COLUMN verification_code VARCHAR;",
        "ALTER TABLE users ADD COLUMN verification_token VARCHAR;",
        "ALTER TABLE users ADD COLUMN verification_expires_at TIMESTAMP;"
    ]:
        try:
            with target_engine.begin() as conn:
                conn.execute(text(col_def))
        except Exception:
            pass

    try:
        with target_engine.begin() as conn:
            conn.execute(text("UPDATE users SET is_verified = TRUE WHERE is_verified IS NULL;"))
    except Exception:
        pass


def _diagnose_psycopg2():
    """One-time diagnostic to figure out why psycopg2 import might be failing."""
    logger.warning(f"[DIAG] Python executable: {sys.executable}")
    logger.warning(f"[DIAG] Python version: {sys.version}")
    try:
        import psycopg2
        logger.warning(f"[DIAG] psycopg2 import SUCCEEDED, version: {psycopg2.__version__}")
    except Exception as e:
        logger.warning(f"[DIAG] psycopg2 import FAILED: {type(e).__name__}: {e}")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "show", "psycopg2-binary"],
                capture_output=True, text=True, timeout=10
            )
            logger.warning(f"[DIAG] pip show psycopg2-binary:\n{result.stdout or result.stderr}")
        except Exception as e2:
            logger.warning(f"[DIAG] pip show failed: {e2}")


def get_engine():
    raw_url = (settings.DATABASE_URL or "").strip().strip('"').strip("'")
    if not raw_url:
        raw_url = "sqlite:///./cipher.db"

    # Normalize Heroku / Supabase / older postgres:// scheme to postgresql://
    if raw_url.startswith("postgres://"):
        raw_url = raw_url.replace("postgres://", "postgresql://", 1)

    # Force explicit psycopg2 dialect so there's no ambiguity about which driver SQLAlchemy picks
    if raw_url.startswith("postgresql://") and "+psycopg2" not in raw_url:
        raw_url = raw_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    db_url = raw_url

    try:
        if db_url.startswith("sqlite"):
            engine = create_engine(db_url, connect_args={"check_same_thread": False})
        else:
            # Run diagnostics BEFORE attempting connection, so we get info even if it fails
            _diagnose_psycopg2()

            connect_args = {"connect_timeout": 5}
            if "sslmode" not in db_url:
                connect_args["sslmode"] = "require"

            engine = create_engine(
                db_url,
                pool_pre_ping=True,
                pool_recycle=300,
                connect_args=connect_args
            )

        # Test connection
        with engine.connect() as conn:
            pass

        _migrate_schema(engine)
        logger.info(f"Connected to database successfully ({'sqlite' if db_url.startswith('sqlite') else 'postgresql'}).")
        return engine

    except Exception as e:
        logger.warning(f"Could not connect to database: {type(e).__name__}: {e}. Falling back to SQLite database.")
        sqlite_url = "sqlite:///./cipher.db"
        sqlite_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
        _migrate_schema(sqlite_engine)
        return sqlite_engine

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from models import entities
    Base.metadata.create_all(bind=engine)
    logger.info("All database tables verified/created successfully.")