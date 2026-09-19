"""Small bounded thread pool for fire-and-forget work.

Sending an SMS or email can take seconds. Doing it inside a request handler
ties up one of the server's worker threads (and, for the M-Pesa callback,
makes Safaricom wait, which triggers retries). Submitting it here returns
immediately; failures are logged, never raised into the request.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from app.core.config import settings

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=settings.background_workers, thread_name_prefix="ledgr-bg")


def submit(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    def _run() -> None:
        try:
            fn(*args, **kwargs)
        except Exception:  # noqa: BLE001 — background work must never crash the pool
            logger.exception("Background task %s failed", getattr(fn, "__name__", fn))

    _executor.submit(_run)


def shutdown() -> None:
    # Let queued notifications finish on a clean shutdown.
    _executor.shutdown(wait=True, cancel_futures=False)
