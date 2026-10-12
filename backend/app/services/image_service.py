from __future__ import annotations
from abc import ABC, abstractmethod
import asyncio
import base64
import random
import httpx
import time
from app.core.config import get_settings
from app.core.logging import logger
from app.core.circuit_breaker import gemini_image_breaker, freepik_breaker


# ── Aspect ratio → pixel dimension lookup (used by Freepik) ──────────────────
# Freepik requires explicit width/height; Gemini takes a ratio string directly.
ASPECT_TO_PIXELS: dict[str, tuple[int, int]] = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1":  (1080, 1080),
    "4:3":  (1440, 1080),
    "3:4":  (1080, 1440),
}

# Fallback if an unsupported ratio is passed
_DEFAULT_PIXELS = (1920, 1080)

# Finish reasons that indicate the model will never produce an image for this prompt
_TERMINAL_FINISH_REASONS = {"SAFETY", "RECITATION", "PROHIBITED_CONTENT", "SPII"}

# Freepik task statuses that indicate permanent failure
_FREEPIK_FATAL_STATUSES = {"FAILED", "ERROR", "CANCELLED"}


class ImageProvider(ABC):
    """Common interface for all image generation providers."""

    @abstractmethod
    async def generate(self, prompt: str, count: int = 4, aspect_ratio: str = "16:9") -> list[str]:
        """Generate images and return a list of public URLs or base64 data-URIs."""
        pass


# ── Gemini Provider ──────────────────────────────────────────────────────────
# Uses GEMINI_API_KEY. The model_name parameter selects the specific model.
#
# IMPORTANT: Gemini image models use generate_content() with
# response_modalities=['IMAGE'], NOT generate_images().
# The generate_images() API returns 404 for these models.

class GeminiImageProvider(ImageProvider):
    """
    Google Gemini API → Image generation via generate_content.
    Requires: GEMINI_API_KEY

    Available models (pass via model_name):
      - "gemini-3.1-flash-image"      → flagship image model
      - "gemini-3.1-flash-lite-image" → ~2× faster, lighter
      - "gemini-3-pro-image"          → highest quality (paid tier)

    These models use the generate_content API with response_modalities=['IMAGE'].
    Returns base64 data-URIs. The Celery worker decodes and uploads to Supabase Storage.
    """

    def __init__(self, model_name: str = "gemini-3.1-flash-image"):
        self.model_name = model_name

    async def generate(self, prompt: str, count: int = 4, aspect_ratio: str = "16:9") -> list[str]:
        from google import genai
        from google.genai import types

        # ── Circuit breaker check ─────────────────────────────────────────────
        if not gemini_image_breaker.allow_request():
            logger.warning(
                f"[GeminiImageProvider:{self.model_name}] Circuit OPEN — "
                "routing directly to Freepik fallback"
            )
            return await self._fallback(prompt, count, aspect_ratio)

        settings = get_settings()
        client = genai.Client(api_key=settings.gemini_api_key)
        results: list[str] = []

        try:
            for i in range(min(count, 4)):
                image_data = await self._generate_single(
                    client, types, prompt, aspect_ratio, image_index=i
                )
                if image_data:
                    results.append(image_data)

                # Staggered delay between calls to avoid burst rate-limiting
                if i < count - 1:
                    await asyncio.sleep(1 + random.uniform(0, 0.5))

            if not results:
                raise RuntimeError(
                    f"[GeminiImageProvider:{self.model_name}] "
                    f"No images produced after {count} attempt(s)"
                )

            gemini_image_breaker.record_success()
            return results

        except Exception as e:
            error_str = str(e)
            gemini_image_breaker.record_failure()

            if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str:
                logger.warning(
                    f"[GeminiImageProvider:{self.model_name}] Quota exhausted. "
                    "Circuit breaker will manage cooldown."
                )
            else:
                logger.error(f"[GeminiImageProvider:{self.model_name}] Error: {e}")

            logger.info(f"[GeminiImageProvider:{self.model_name}] Routing to Freepik fallback...")
            return await self._fallback(prompt, count, aspect_ratio)

    async def _generate_single(
        self,
        client,
        types,
        prompt: str,
        aspect_ratio: str,
        image_index: int,
    ) -> str | None:
        """
        Attempt to generate a single image with up to 3 retries.
        Returns a base64 data-URI on success, or None if all attempts yield empty output.
        """
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            try:
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
                    ),
                )

                # ── Validate candidate ────────────────────────────────────────
                if not response.candidates:
                    logger.warning(
                        f"[GeminiImageProvider] image[{image_index}] attempt {attempt}: "
                        "no candidates in response"
                    )
                else:
                    candidate = response.candidates[0]
                    finish_reason = str(getattr(candidate, "finish_reason", "") or "")

                    # Safety / recitation block — no point retrying
                    if finish_reason in _TERMINAL_FINISH_REASONS:
                        logger.warning(
                            f"[GeminiImageProvider] image[{image_index}] blocked: "
                            f"finish_reason={finish_reason}"
                        )
                        return None

                    # Try to extract inline image data
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if (
                                part.inline_data
                                and part.inline_data.mime_type
                                and "image" in part.inline_data.mime_type
                            ):
                                mime = part.inline_data.mime_type
                                img_data = part.inline_data.data
                                b64 = (
                                    base64.b64encode(img_data).decode()
                                    if isinstance(img_data, bytes)
                                    else img_data
                                )
                                logger.debug(
                                    f"[GeminiImageProvider] image[{image_index}] "
                                    f"generated successfully (attempt {attempt})"
                                )
                                return f"data:{mime};base64,{b64}"

                # Empty output — retry with backoff
                if attempt < max_attempts:
                    wait = min(2.0 * (2 ** (attempt - 1)), 16.0)
                    wait += random.uniform(0, 0.5)  # jitter
                    logger.warning(
                        f"[GeminiImageProvider] image[{image_index}] attempt {attempt}: "
                        f"empty output. Retrying in {wait:.1f}s..."
                    )
                    await asyncio.sleep(wait)

            except Exception as e:
                error_str = str(e)
                # Quota / auth errors — don't retry at the single-image level
                if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str or "PERMISSION_DENIED" in error_str:
                    raise  # bubble up to generate() which routes to fallback

                if attempt < max_attempts:
                    wait = min(2.0 * (2 ** (attempt - 1)), 16.0) + random.uniform(0, 0.5)
                    logger.warning(
                        f"[GeminiImageProvider] image[{image_index}] attempt {attempt} "
                        f"error ({type(e).__name__}: {e}). Retrying in {wait:.1f}s..."
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(
                        f"[GeminiImageProvider] image[{image_index}] all {max_attempts} "
                        f"attempts failed. Last error: {e}"
                    )
                    raise

        logger.warning(
            f"[GeminiImageProvider] image[{image_index}] produced no output "
            f"after {max_attempts} attempts"
        )
        return None

    async def _fallback(self, prompt: str, count: int, aspect_ratio: str) -> list[str]:
        """Route to Freepik when Gemini is unavailable."""
        return await FreepikMysticProvider(style="photo").generate(prompt, count, aspect_ratio)


# ── Freepik Providers ─────────────────────────────────────────────────────────
# Both use FREEPIK_API_KEY. The style parameter selects the visual output style.

class FreepikMysticProvider(ImageProvider):
    """
    Freepik API → AI Mystic (text-to-image) endpoint.
    Requires: FREEPIK_API_KEY

    IMPORTANT: Freepik Mystic is ASYNC — it uses a submit → poll pattern.
      1. POST /v1/ai/mystic   → returns task_id + status=CREATED
      2. GET  /v1/ai/mystic/{task_id} → poll until status=COMPLETED

    Available styles (pass via style):
      - "photo"       → Photorealistic, stock-quality output
      - "digital-art" → Illustrated / stylised / artistic output

    aspect_ratio is translated to Freepik's canonical string values.
    Returns public image URLs directly (Freepik hosts them).
    """

    def __init__(self, style: str = "photo"):
        self.style = style  # "photo" | "digital-art"

    async def generate(self, prompt: str, count: int = 4, aspect_ratio: str = "16:9") -> list[str]:
        # ── Circuit breaker check ─────────────────────────────────────────────
        if not freepik_breaker.allow_request():
            raise RuntimeError(
                "[FreepikMysticProvider] Circuit OPEN — Freepik is currently unavailable. "
                "Please retry later."
            )

        settings = get_settings()
        headers = {
            "x-freepik-api-key": settings.freepik_api_key,
            "Content-Type": "application/json",
        }

        # Translate aspect ratio string → Freepik canonical value
        aspect_map = {
            "16:9": "widescreen_16_9",
            "9:16": "social_story_9_16",
            "1:1":  "square_1_1",
            "4:3":  "classic_4_3",
            "3:4":  "traditional_3_4",
        }
        freepik_aspect = aspect_map.get(aspect_ratio, "widescreen_16_9")

        try:
            async with httpx.AsyncClient(timeout=90) as client:
                # Step 1: Submit the job
                submit = await client.post(
                    "https://api.freepik.com/v1/ai/mystic",
                    headers=headers,
                    json={
                        "prompt": prompt,
                        "aspect_ratio": freepik_aspect,
                        "styling": {"style": self.style},
                    },
                )
                submit.raise_for_status()
                task_id = submit.json()["data"]["task_id"]
                logger.info(f"[FreepikMysticProvider] Job submitted — task_id={task_id}")

                # Step 2: Poll until COMPLETED (max 24 × ~6s = ~144s)
                # Jitter avoids thundering-herd when multiple workers poll simultaneously
                for poll_num in range(24):
                    poll_wait = 5 + random.uniform(0, 2)  # 5–7s with jitter
                    await asyncio.sleep(poll_wait)

                    poll = await client.get(
                        f"https://api.freepik.com/v1/ai/mystic/{task_id}",
                        headers={"x-freepik-api-key": settings.freepik_api_key},
                    )
                    poll.raise_for_status()
                    data = poll.json().get("data", {})
                    status = data.get("status")

                    logger.debug(
                        f"[FreepikMysticProvider] task_id={task_id} poll={poll_num + 1} status={status}"
                    )

                    if status == "COMPLETED":
                        generated = data.get("generated", [])
                        urls = [url for url in generated if isinstance(url, str) and url]
                        if not urls:
                            raise RuntimeError(
                                f"[FreepikMysticProvider] Task {task_id} COMPLETED but returned no URLs"
                            )
                        freepik_breaker.record_success()
                        logger.info(
                            f"[FreepikMysticProvider] task_id={task_id} COMPLETED with {len(urls)} image(s)"
                        )
                        return urls

                    elif status in _FREEPIK_FATAL_STATUSES:
                        raise RuntimeError(
                            f"[FreepikMysticProvider] Task failed: status={status}, task_id={task_id}"
                        )
                    # else: still in progress — keep polling

            raise TimeoutError(
                f"[FreepikMysticProvider] Timed out after 24 polls (task_id={task_id})"
            )

        except Exception as e:
            freepik_breaker.record_failure()
            logger.error(f"[FreepikMysticProvider] Error: {e}")
            raise


# ── Factory ───────────────────────────────────────────────────────────────────
#
# This is the single routing point.
# Each enum value in ImageModel maps to exactly one provider instance.
# Adding a new model = add one line here.

def get_image_provider(model: str) -> ImageProvider:
    providers: dict[str, ImageProvider] = {
        # ── Gemini API (uses generate_content with IMAGE modality) ────────────
        "gemini_imagen3":      GeminiImageProvider("gemini-3.1-flash-image"),
        "gemini_imagen3_fast": GeminiImageProvider("gemini-3.1-flash-lite-image"),
        "gemini_image_pro":    GeminiImageProvider("gemini-3-pro-image"),

        # ── Freepik API (reliable, works on current plan) ─────────────────────
        "freepik_mystic_photo": FreepikMysticProvider(style="photo"),
        "freepik_mystic_art":   FreepikMysticProvider(style="digital-art"),
    }
    provider = providers.get(model)
    if not provider:
        raise ValueError(
            f"Unknown image model '{model}'. "
            f"Valid options: {list(providers.keys())}"
        )
    return provider
