"""Translation task queue with concurrency control.

Uses an asyncio.Queue and a semaphore to limit concurrent translations.
"""

import asyncio
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class TranslationQueue:
    def __init__(self):
        self._queue: asyncio.Queue[int] = asyncio.Queue(maxsize=settings.MAX_QUEUE_SIZE)
        self._semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_TRANSLATIONS)
        self._worker_task: asyncio.Task | None = None

    async def start(self):
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info(
            f"Translation queue started: max_concurrent={settings.MAX_CONCURRENT_TRANSLATIONS}"
        )

    async def stop(self):
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def enqueue(self, task_id: int):
        await self._queue.put(task_id)
        logger.info(f"Task {task_id} enqueued, queue size: {self._queue.qsize()}")

    async def _worker_loop(self):
        while True:
            task_id = await self._queue.get()
            asyncio.create_task(self._process_with_semaphore(task_id))

    async def _process_with_semaphore(self, task_id: int):
        async with self._semaphore:
            try:
                await self._run_translation(task_id)
            except Exception:
                logger.exception(f"Translation task {task_id} failed")

    async def _run_translation(self, task_id: int):
        from app.services.translator_worker import run_translation_task

        await run_translation_task(task_id)


translation_queue = TranslationQueue()
