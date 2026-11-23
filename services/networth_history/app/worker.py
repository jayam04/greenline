import asyncio
import datetime
import logging
from typing import Dict, Optional

from app.db.database import AsyncSessionLocal
from app.services import cache_service

logger = logging.getLogger(__name__)


class NetworthHistoryWorker:
    """Coalesce per-user recalculations and refresh daily snapshots asynchronously."""

    def __init__(self):
        self.queue: asyncio.Queue[int] = asyncio.Queue()
        self.pending: Dict[int, Optional[datetime.date]] = {}
        self.locks: Dict[int, asyncio.Lock] = {}
        self.task: Optional[asyncio.Task] = None
        self.running = False

    async def enqueue_recalculate(self, user_id: int, start_date=None, reason="financial_change"):
        if user_id in self.pending:
            pending_date = self.pending[user_id]
            self.pending[user_id] = None if start_date is None or pending_date is None else min(pending_date, start_date)
        else:
            self.pending[user_id] = start_date
            await self.queue.put(user_id)
        logger.info("Queued net-worth recalculation user=%s date=%s reason=%s", user_id, start_date, reason)
        return True

    async def _run(self):
        while self.running:
            user_id = await self.queue.get()
            start_date = self.pending.pop(user_id, None)
            try:
                try:
                    await self.rebuild_user(
                        user_id, start_date=start_date, full_rebuild=start_date is None
                    )
                except Exception:
                    logger.exception("Net-worth recalculation failed for user=%s", user_id)
            finally:
                self.queue.task_done()

    async def rebuild_user(self, user_id: int, start_date=None, full_rebuild=False):
        from .history import rebuild_user_history
        from app.api.routers.snapshots import invalidate_user_cache

        lock = self.locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            async with AsyncSessionLocal() as db:
                count = await rebuild_user_history(
                    db, user_id, start_date=start_date, full_rebuild=full_rebuild
                )
                invalidate_user_cache(user_id)
                await cache_service.invalidate_user_snapshot_cache(user_id)
                return count

    async def rebuild_all_users(self):
        from app.db.models import User
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            user_ids = (await db.execute(select(User.user_id).order_by(User.user_id))).scalars().all()
        count = 0
        for user_id in user_ids:
            count += await self.rebuild_user(user_id, full_rebuild=True)
        return len(user_ids), count

    def start(self):
        if not self.running:
            self.running = True
            self.task = asyncio.create_task(self._run())

    async def stop(self):
        self.running = False
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass


history_worker = NetworthHistoryWorker()
