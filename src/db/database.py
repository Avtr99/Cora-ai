import sqlite3
import os
import re
import logging


from ..config import get_settings

logger = logging.getLogger(__name__)

_MIGRATION_FILENAME_RE = re.compile(r"^\d{3}_[a-zA-Z0-9_]+\.sql$")

def get_db_path() -> str:
    db_path = get_settings().DATABASE_URL
    if db_path.startswith("sqlite:///"):
        # Strip sqlite:/// prefix
        db_path = db_path[10:]
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    return db_path

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    # Configure SQLite for concurrency and performance
    # WAL (Write-Ahead Logging) is critical for concurrent reads/writes
    conn.execute("PRAGMA journal_mode=WAL;")
    # Wait up to 5000ms if db is locked
    conn.execute("PRAGMA busy_timeout=5000;")
    # Safe with WAL, improves performance
    conn.execute("PRAGMA synchronous=NORMAL;")
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys=ON;")
    
    return conn

def run_migrations():
    """Runs pending .sql migrations from the migrations directory."""
    conn = get_connection()
    try:
        # Ensure migrations table exists
        conn.execute('''
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Get applied migrations
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM schema_migrations")
        applied = {row['version'] for row in cursor.fetchall()}
        
        migrations_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "migrations")
        if not os.path.exists(migrations_dir):
            logger.warning(f"Migrations directory not found at {migrations_dir}")
            return
            
        # Get available migrations, sorted by filename
        migration_files = sorted([f for f in os.listdir(migrations_dir) if f.endswith(".sql")])
        
        for file in migration_files:
            if not _MIGRATION_FILENAME_RE.match(file):
                logger.error(f"Ignoring migration with invalid filename: {file}")
                continue
            if file not in applied:
                logger.info(f"Applying migration {file}...")
                with open(os.path.join(migrations_dir, file), 'r') as f:
                    script = f.read()
                    
                # Run the migration
                cursor.executescript(script)
                # Record it
                cursor.execute("INSERT INTO schema_migrations (version) VALUES (?)", (file,))
                conn.commit()
                logger.info(f"Successfully applied {file}.")
                
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
