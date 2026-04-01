"""Serialized DB writer — all SQLite writes go through a single-thread queue.

Equivalent to Java's BlockingQueue + single consumer pattern.
Eliminates SQLite 'database is locked' errors from concurrent thread writes.
"""

import queue
import threading
import logging

logger = logging.getLogger(__name__)


class DBWriteQueue:
    """Drop-in replacement for Session write operations.

    Presents the same API as SQLAlchemy Session (add/flush/commit/rollback)
    but serializes all writes through a single background thread.

    Usage:
        writer = DBWriteQueue(session_factory)
        writer.add(some_model_instance)
        writer.flush()      # blocks until flush completes
        writer.commit()      # blocks until commit completes
        writer.close()       # shuts down the writer thread
    """

    def __init__(self, db_factory):
        self._q: queue.Queue = queue.Queue()
        self._db_factory = db_factory
        self._session = None
        self._thread = threading.Thread(
            target=self._writer_loop, daemon=True, name="db-writer"
        )
        self._thread.start()

    def _writer_loop(self):
        """Consumer loop — runs on the dedicated writer thread."""
        self._session = self._db_factory()
        logger.info("DBWriteQueue: writer thread started")

        while True:
            item = self._q.get()
            if item is None:
                # Poison pill — shut down
                break

            op, payload, done_event, result_box = item
            try:
                if op == "add":
                    self._session.add(payload)
                elif op == "flush":
                    self._session.flush()
                elif op == "commit":
                    self._session.flush()
                    self._session.commit()
                elif op == "rollback":
                    self._session.rollback()

                if result_box is not None:
                    result_box["ok"] = True

            except Exception as e:
                logger.error("DBWriteQueue %s failed: %s", op, e, exc_info=True)
                try:
                    self._session.rollback()
                except Exception:
                    pass
                if result_box is not None:
                    result_box["ok"] = False
                    result_box["err"] = e
            finally:
                if done_event:
                    done_event.set()

        # Cleanup
        try:
            self._session.close()
        except Exception:
            pass
        logger.info("DBWriteQueue: writer thread stopped")

    # ── Public API (called from any thread) ──────────────────────

    def add(self, instance):
        """Non-blocking: enqueue an add operation."""
        self._q.put(("add", instance, None, None))

    def flush(self, timeout: float = 120):
        """Blocking: flush pending writes and wait for completion."""
        ev = threading.Event()
        r: dict = {}
        self._q.put(("flush", None, ev, r))
        ev.wait(timeout=timeout)
        if not r.get("ok"):
            raise r.get("err", RuntimeError("DBWriteQueue flush timeout"))

    def commit(self, timeout: float = 120):
        """Blocking: commit and wait for completion."""
        ev = threading.Event()
        r: dict = {}
        self._q.put(("commit", None, ev, r))
        ev.wait(timeout=timeout)
        if not r.get("ok"):
            raise r.get("err", RuntimeError("DBWriteQueue commit timeout"))

    def rollback(self, timeout: float = 30):
        """Blocking: rollback and wait."""
        ev = threading.Event()
        r: dict = {}
        self._q.put(("rollback", None, ev, r))
        ev.wait(timeout=timeout)

    def close(self):
        """Shut down the writer thread. Blocks until it exits."""
        self._q.put(None)  # poison pill
        self._thread.join(timeout=30)

    @property
    def pending(self) -> int:
        """Number of pending operations in the queue."""
        return self._q.qsize()
