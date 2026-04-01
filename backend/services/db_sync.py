"""Memory-to-file DB sync — periodically backs up in-memory SQLite to disk.

Architecture:
  Runtime: sqlite:///:memory: (fast, no lock issues)
  Every 30s + shutdown: backup memory → unrealmake.db file
  Startup: restore unrealmake.db file → memory
"""

import sqlite3
import threading
import logging
import os
import time

logger = logging.getLogger(__name__)

_PERSIST_FILE = os.path.join(os.path.dirname(__file__), "..", "unrealmake.db")
_SYNC_INTERVAL = 30  # seconds
_timer: threading.Timer | None = None
_running = False


def restore_from_file(memory_engine):
    """On startup: copy file DB → in-memory DB (if file exists)."""
    persist_path = os.path.abspath(_PERSIST_FILE)
    if not os.path.exists(persist_path):
        logger.info("No persistent DB file found, starting fresh")
        return

    try:
        file_conn = sqlite3.connect(persist_path)
        # Get the raw DBAPI connection from SQLAlchemy's pool
        raw = memory_engine.raw_connection()
        mem_conn = raw.connection
        file_conn.backup(mem_conn)
        file_conn.close()
        raw.close()
        logger.info(f"Restored in-memory DB from {persist_path}")
    except Exception as e:
        logger.error(f"Failed to restore from file DB: {e}")


def _save_to_file(memory_engine):
    """Backup in-memory DB → file DB."""
    persist_path = os.path.abspath(_PERSIST_FILE)
    try:
        raw = memory_engine.raw_connection()
        mem_conn = raw.connection
        file_conn = sqlite3.connect(persist_path)
        mem_conn.backup(file_conn)
        file_conn.close()
        raw.close()
        logger.info(f"Synced in-memory DB → {persist_path}")
    except Exception as e:
        logger.error(f"Failed to sync to file DB: {e}")


def _periodic_sync(memory_engine):
    """Timer callback — sync then schedule next."""
    global _timer
    if not _running:
        return
    _save_to_file(memory_engine)
    _timer = threading.Timer(_SYNC_INTERVAL, _periodic_sync, args=(memory_engine,))
    _timer.daemon = True
    _timer.start()


def start_sync(memory_engine):
    """Start periodic background sync."""
    global _running, _timer
    _running = True
    _timer = threading.Timer(_SYNC_INTERVAL, _periodic_sync, args=(memory_engine,))
    _timer.daemon = True
    _timer.start()
    logger.info(f"DB sync started: every {_SYNC_INTERVAL}s → {os.path.abspath(_PERSIST_FILE)}")


def stop_sync(memory_engine):
    """Stop sync and do final save."""
    global _running, _timer
    _running = False
    if _timer:
        _timer.cancel()
        _timer = None
    # Final save
    _save_to_file(memory_engine)
    logger.info("DB sync stopped, final save complete")
