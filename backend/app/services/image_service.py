from abc import ABC, abstractmethod
import base64
import httpx
import asyncio
import time
from app.core.config import get_settings


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

# ── Quota exhaustion tracker ─────────────────────────────────────────────────
# When Gemini returns 429 RESOURCE_EXHAUSTED, we record the timestamp so that
# subsequent requests skip Gemini entirely and go straight to Freepik.
# This avoids wasting 5-10s per request on a provider that's guaranteed to fail.
_gemini_image_quota_exhausted_until: float = 0.0


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
        global _gemini_image_quota_exhausted_until
        from google import genai
        from google.genai import types

        # ── Check if Gemini is quota-exhausted ────────────────────────
        if time.time() < _gemini_image_quota_exhausted_until:
            remaining = int(_gemini_image_quota_exhausted_until - time.time())
            raise RuntimeError(
                f"Gemini image quota exhausted. Resets in {remaining // 3600}h {(remaining % 3600) // 60}m. "
                f"Routing to Freepik fallback."
            )

        settings = get_settings()
        client = genai.Client(api_key=settings.gemini_api_key)

        try:
            results = []
            for i in range(min(count, 4)):
                # Gemini image models use generate_content with IMAGE modality
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                    ),
                )

                # Extract image from response parts
                if (response.candidates
                        and response.candidates[0].content
                        and response.candidates[0].content.parts):
                    for part in response.candidates[0].content.parts:
                        if part.inline_data and part.inline_data.mime_type and "image" in part.inline_data.mime_type:
                            mime = part.inline_data.mime_type
                            img_data = part.inline_data.data
                            # SDK may return raw bytes or base64 string
                            if isinstance(img_data, bytes):
                                b64 = base64.b64encode(img_data).decode()
                            else:
                                b64 = img_data
                            results.append(f"data:{mime};base64,{b64}")
                            break  # one image per call

                # Small delay between calls to avoid rate limiting
                if i < count - 1:
                    await asyncio.sleep(1)

            if not results:
                raise RuntimeError(f"Gemini {self.model_name} returned no image data in {count} attempts")
            return results

        except Exception as e:
            error_str = str(e)

            # Detect quota exhaustion and record cooldown
            if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str:
                # Parse retry delay if available, default to 1 hour
                cooldown_seconds = 3600
                if "retryDelay" in error_str:
                    try:
                        import re
                        match = re.search(r'"retryDelay":\s*"(\d+)s"', error_str)
                        if match:
                            cooldown_seconds = int(match.group(1))
                    except Exception:
                        pass
                elif "retry in" in error_str.lower():
                    try:
                        import re
                        match = re.search(r'retry in (\d+)h(\d+)m', error_str.lower())
                        if match:
                            cooldown_seconds = int(match.group(1)) * 3600 + int(match.group(2)) * 60
                    except Exception:
                        pass

                _gemini_image_quota_exhausted_until = time.time() + cooldown_seconds
                hours = cooldown_seconds // 3600
                mins = (cooldown_seconds % 3600) // 60
                print(f"[GeminiImageProvider] Quota exhausted. Cooldown set for {hours}h {mins}m.")

            print(f"[GeminiImageProvider] Failed ({e}). Routing to Freepik Mystic fallback...")
            fallback_provider = FreepikMysticProvider(style="photo")
            return await fallback_provider.generate(prompt, count, aspect_ratio)


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

    aspect_ratio is translated to pixel dimensions via ASPECT_TO_PIXELS.
    Returns public image URLs directly (Freepik hosts them).
    """

    def __init__(self, style: str = "photo"):
        self.style = style  # "photo" | "digital-art"

    async def generate(self, prompt: str, count: int = 4, aspect_ratio: str = "16:9") -> list[str]:
        settings = get_settings()
        headers = {
            "x-freepik-api-key": settings.freepik_api_key,
            "Content-Type": "application/json",
        }

        # Translate aspect ratio string → pixel dimensions for Freepik
        width, height = ASPECT_TO_PIXELS.get(aspect_ratio, _DEFAULT_PIXELS)

        async with httpx.AsyncClient(timeout=90) as client:
            # Step 1: Submit the job
            submit = await client.post(
                "https://api.freepik.com/v1/ai/mystic",
                headers=headers,
                json={
                    "prompt": prompt,
                    "image": {"size": {"width": width, "height": height}},
                    "styling": {"style": self.style},
                },
            )
            submit.raise_for_status()
            task_id = submit.json()["data"]["task_id"]

            # Step 2: Poll until COMPLETED (max 24 × 5s = 120s)
            for _ in range(24):
                await asyncio.sleep(5)
                poll = await client.get(
                    f"https://api.freepik.com/v1/ai/mystic/{task_id}",
                    headers={"x-freepik-api-key": settings.freepik_api_key},
                )
                poll.raise_for_status()
                data = poll.json().get("data", {})
                status = data.get("status")

                if status == "COMPLETED":
                    generated = data.get("generated", [])
                    # generated is a list of URL strings e.g. ["https://cdn-magnific.freepik.com/..."]
                    return [url for url in generated if isinstance(url, str) and url]
                elif status in ("FAILED", "ERROR"):
                    raise RuntimeError(
                        f"Freepik Mystic generation failed: status={status}, task={task_id}"
                    )

        raise TimeoutError(
            f"Freepik Mystic timed out after 120s (task={task_id})"
        )


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
