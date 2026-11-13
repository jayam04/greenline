import asyncio
import datetime
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class SnapshotBackgroundWorker:
    """
    In-process asynchronous background worker for event-driven snapshot recalculations.
    Uses asyncio.Queue for non-blocking ingestion, per-user asyncio.Lock to serialize
    recalculations, and debouncing via pending_jobs dictionary.
    """

    def __init__(self):
        self.queue: asyncio.Queue[int] = asyncio.Queue()
        self.pending_jobs: Dict[int, datetime.date] = {}
        self.user_locks: Dict[int, asyncio.Lock] = {}
        self.worker_task: Optional[asyncio.Task] = None
        self.running: bool = False

    def get_user_lock(self, user_id: int) -> asyncio.Lock:
        if user_id not in self.user_locks:
            self.user_locks[user_id] = asyncio.Lock()
        return self.user_locks[user_id]

    async def enqueue_recalculate(
        self,
        user_id: int,
        start_date: Optional[datetime.date] = None,
        reason: str = "trade_event"
    ) -> bool:
        """
        Enqueues a recalculation job in < 2ms.
        Debounces multiple incoming triggers for the same user_id using min(existing, new) start_date.
        """
        if not self.running:
            self.start()

        effective_start = start_date or datetime.date(2000, 1, 1)

        if user_id in self.pending_jobs:
            self.pending_jobs[user_id] = min(self.pending_jobs[user_id], effective_start)
        else:
            self.pending_jobs[user_id] = effective_start
            await self.queue.put(user_id)

        logger.debug(f"[BackgroundWorker] Enqueued recalculation for user_id={user_id}, start_date={effective_start}, reason={reason}")
        return True

    async def _worker_loop(self):
        """Sequential job consumption with per-user lock."""
        try:
            from ..db.database import AsyncSessionLocal
            from .snapshot_engine import recalculate_past_snapshots
        except (ImportError, ValueError):
            from app.db.database import AsyncSessionLocal
            from app.services.snapshot_engine import recalculate_past_snapshots

        while self.running:
            try:
                user_id = await self.queue.get()
                start_date = self.pending_jobs.pop(user_id, None)
                if start_date is None:
                    self.queue.task_done()
                    continue

                lock = self.get_user_lock(user_id)
                async with lock:
                    async with AsyncSessionLocal() as session:
                        try:
                            await recalculate_past_snapshots(session, start_date=start_date, user_id=user_id)
                            # Invalidate L1 cache for this user
                            try:
                                from ..api.routers.snapshots import invalidate_user_cache
                                invalidate_user_cache(user_id)
                            except Exception:
                                try:
                                    from app.api.routers.snapshots import invalidate_user_cache
                                    invalidate_user_cache(user_id)
                                except Exception:
                                    pass
                        except Exception as e:
                            logger.error(f"[BackgroundWorker] Error recalculating for user_id={user_id}: {e}")

                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[BackgroundWorker] Unexpected error in worker loop: {e}")
                await asyncio.sleep(0.05)

    def start(self):
        """Starts the background worker task."""
        if not self.running:
            self.running = True
            self.worker_task = asyncio.create_task(self._worker_loop())
            logger.info("[BackgroundWorker] Background snapshot recalculation worker started.")

    async def stop(self):
        """Gracefully cancels and awaits the background worker task."""
        if self.running:
            self.running = False
            if self.worker_task and not self.worker_task.done():
                self.worker_task.cancel()
                try:
                    await self.worker_task
                except asyncio.CancelledError:
                    pass
            logger.info("[BackgroundWorker] Background snapshot recalculation worker stopped.")


background_worker = SnapshotBackgroundWorker()
