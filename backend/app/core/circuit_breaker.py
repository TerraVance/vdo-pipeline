"""
Thread-safe Circuit Breaker implementation.

States:
  CLOSED    — Normal operation. Requests pass through.
  OPEN      — Provider is failing. Requests fail-fast for `cooldown` seconds.
  HALF_OPEN — Cooldown elapsed. One probe request is allowed to test recovery.
              Success  → CLOSED
              Failure  → OPEN (cooldown resets)

Usage:
    from app.core.circuit_breaker import gemini_image_breaker

    if not gemini_image_breaker.allow_request():
        raise RuntimeError("Gemini image circuit is OPEN — skipping call")
    try:
        result = call_gemini(...)
        gemini_image_breaker.record_success()
    except Exception as e:
        gemini_image_breaker.record_failure()
        raise
"""

import threading
import time
from enum import Enum
from app.core.logging import logger


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """
    Thread-safe circuit breaker for external provider calls.

    Args:
        name: Human-readable identifier used in log messages.
        failure_threshold: Number of consecutive failures to trip the breaker.
        cooldown: Seconds to stay OPEN before moving to HALF_OPEN.
    """

    def __init__(self, name: str, failure_threshold: int = 3, cooldown: int = 300) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown = cooldown

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: float = 0.0
        self._lock = threading.Lock()

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._state

    def allow_request(self) -> bool:
        """
        Returns True if the circuit allows the request to proceed.
        Transitions OPEN → HALF_OPEN when cooldown has elapsed.
        """
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._opened_at >= self.cooldown:
                    self._state = CircuitState.HALF_OPEN
                    logger.info(
                        f"[CircuitBreaker:{self.name}] OPEN → HALF_OPEN — "
                        f"sending probe request after {self.cooldown}s cooldown"
                    )
                    return True  # allow the probe
                return False  # still cooling down

            # HALF_OPEN — allow the probe (only one at a time; lock held)
            return True

    def record_success(self) -> None:
        """Call after a successful provider response to reset the breaker."""
        with self._lock:
            if self._state != CircuitState.CLOSED:
                logger.info(f"[CircuitBreaker:{self.name}] {self._state} → CLOSED — provider recovered")
            self._state = CircuitState.CLOSED
            self._failure_count = 0

    def record_failure(self) -> None:
        """Call after a provider error to increment failure count and potentially open the circuit."""
        with self._lock:
            self._failure_count += 1

            if self._state == CircuitState.HALF_OPEN or self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                logger.warning(
                    f"[CircuitBreaker:{self.name}] Circuit OPENED — "
                    f"{self._failure_count} failure(s). "
                    f"Will retry in {self.cooldown}s"
                )
            else:
                logger.debug(
                    f"[CircuitBreaker:{self.name}] Failure {self._failure_count}/{self.failure_threshold}"
                )

    def reset(self) -> None:
        """Manually force the breaker back to CLOSED (e.g. from an admin endpoint)."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._opened_at = 0.0
            logger.info(f"[CircuitBreaker:{self.name}] Manually reset to CLOSED")

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(name={self.name!r}, state={self._state.value}, "
            f"failures={self._failure_count}/{self.failure_threshold})"
        )


# ── Pre-wired breakers for each AI provider ───────────────────────────────────
# Import these directly wherever needed:
#   from app.core.circuit_breaker import gemini_image_breaker

# Gemini image generation: 3 failures → open for 1 hour (quota cycles are long)
gemini_image_breaker = CircuitBreaker(
    name="gemini_image",
    failure_threshold=3,
    cooldown=3600,
)

# Gemini text generation: 5 failures → open for 5 minutes (text models recover faster)
gemini_text_breaker = CircuitBreaker(
    name="gemini_text",
    failure_threshold=5,
    cooldown=300,
)

# Freepik: 4 failures → open for 2 minutes (usually recovers quickly)
freepik_breaker = CircuitBreaker(
    name="freepik",
    failure_threshold=4,
    cooldown=120,
)
