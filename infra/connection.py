import sqlite3
import logging
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger(__name__)
DB_PATH = Path(__file__).parent.parent / "controladoria.db"

def conectar() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

@contextmanager
def Transaction():
    """
    Gerenciador de transação.
    Uso:
    with Transaction() as conn:
        repo.salvar(conn, dados)
    """
    conn = conectar()
    try:
        yield conn
        conn.commit()
        logger.debug("✅ Transação confirmada com sucesso.")
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Transação revertida devido a erro: {e}")
        raise
    finally:
        conn.close()
