"""
Reusable retry utilities with exponential backoff and jitter.

Usage (async):
    result = await retry_async(
        my_async_fn,
        arg1, arg2,
        max_attempts=3,
        base_delay=1.0,
        retryable_exceptions=(httpx.TimeoutException, RuntimeError),
    )

Usage (sync):
    result = retry_sync(
        my_sync_fn,
        arg1,
        max_attempts=3,
    )
"""

import asyncio
import random
import time
from typing import Any, Callable, Tuple, Type
from app.core.logging import logger


async def retry_async(
    fn: Callable,
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    non_retryable_exceptions: Tuple[Type[Exception], ...] = (),
    fn_name: str = "",
    **kwargs: Any,
) -> Any:
    """
    Retry an async callable with exponential backoff and optional jitter.

    Args:
        fn: Async callable to invoke.
        *args: Positional arguments passed to fn.
        max_attempts: Total number of attempts (including the first).
        base_delay: Initial wait in seconds before the 2nd attempt.
        max_delay: Upper bound for computed wait time.
        jitter: If True, adds ±25 % random noise to each wait to avoid thundering-herd.
        retryable_exceptions: Only retry on these exception types.
        non_retryable_exceptions: Never retry on these — raise immediately.
        fn_name: Human-readable label used in log messages.
        **kwargs: Keyword arguments passed to fn.

    Returns:
        The return value of fn on success.

    Raises:
        The last exception if all attempts fail.
    """
    label = fn_name or getattr(fn, "__name__", repr(fn))

    for attempt in range(1, max_attempts + 1):
        try:
            return await fn(*args, **kwargs)
        except non_retryable_exceptions as e:  # type: ignore[misc]
            logger.error(f"[retry_async:{label}] Non-retryable error on attempt {attempt}/{max_attempts}: {e}")
            raise
        except retryable_exceptions as e:  # type: ignore[misc]
            if attempt == max_attempts:
                logger.error(f"[retry_async:{label}] All {max_attempts} attempts failed. Last error: {e}")
                raise
            wait = min(base_delay * (2 ** (attempt - 1)), max_delay)
            if jitter:
                wait = wait * (0.75 + random.random() * 0.5)  # ±25 %
            logger.warning(
                f"[retry_async:{label}] Attempt {attempt}/{max_attempts} failed ({type(e).__name__}: {e}). "
                f"Retrying in {wait:.2f}s..."
            )
            await asyncio.sleep(wait)

    # Unreachable, but satisfies type checkers
    raise RuntimeError(f"[retry_async:{label}] Exhausted {max_attempts} attempts")


def retry_sync(
    fn: Callable,
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    non_retryable_exceptions: Tuple[Type[Exception], ...] = (),
    fn_name: str = "",
    **kwargs: Any,
) -> Any:
    """
    Synchronous version of retry_async — same semantics, uses time.sleep.
    Suitable for use inside Celery tasks.
    """
    label = fn_name or getattr(fn, "__name__", repr(fn))

    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except non_retryable_exceptions as e:  # type: ignore[misc]
            logger.error(f"[retry_sync:{label}] Non-retryable error on attempt {attempt}/{max_attempts}: {e}")
            raise
        except retryable_exceptions as e:  # type: ignore[misc]
            if attempt == max_attempts:
                logger.error(f"[retry_sync:{label}] All {max_attempts} attempts failed. Last error: {e}")
                raise
            wait = min(base_delay * (2 ** (attempt - 1)), max_delay)
            if jitter:
                wait = wait * (0.75 + random.random() * 0.5)
            logger.warning(
                f"[retry_sync:{label}] Attempt {attempt}/{max_attempts} failed ({type(e).__name__}: {e}). "
                f"Retrying in {wait:.2f}s..."
            )
            time.sleep(wait)

    raise RuntimeError(f"[retry_sync:{label}] Exhausted {max_attempts} attempts")
