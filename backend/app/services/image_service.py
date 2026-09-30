from abc import ABC, abstractmethod
import httpx
import asyncio
from app.core.config import get_settings


class ImageProvider(ABC):
    """Common interface for all image generation providers."""

    @abstractmethod
    async def generate(self, prompt: str, count: int = 4) -> list[str]:
        """Generate images and return a list of public URLs or base64 data-URIs."""
        pass


# ── Gemini Providers ─────────────────────────────────────────────────────────
# Both use GEMINI_API_KEY. The model_name parameter selects the specific endpoint.

class GeminiImageProvider(ImageProvider):
    """
    Google Gemini API → Imagen image generation.
    Requires: GEMINI_API_KEY

    Available models (pass via model_name):
      - "imagen-3.0-generate-002"      → Imagen 3 (highest quality)
      - "imagen-3.0-fast-generate-001" → Imagen 3 Fast (~2× faster)

    Returns base64 data-URIs. The Celery worker decodes and uploads to Supabase Storage.
    """

    def __init__(self, model_name: str = "gemini-3.1-flash-image"):
        self.model_name = model_name

    async def generate(self, prompt: str, count: int = 4) -> list[str]:
        from google import genai

        settings = get_settings()
        client = genai.Client(api_key=settings.gemini_api_key)

        try:
            results = []
            for _ in range(min(count, 4)):
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"],
                        aspect_ratio="16:9",
                    ),
                )
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "inline_data") and part.inline_data:
                        mime = part.inline_data.mime_type or "image/png"
                        b64 = base64.b64encode(part.inline_data.data).decode()
                        results.append(f"data:{mime};base64,{b64}")
                        break  # one image per call

            if not results:
                raise RuntimeError(f"Gemini {self.model_name} returned no image data")
            return results

        except Exception as e:
            print(f"Gemini image generation failed ({e}). Diverting route to Freepik fallback...")
            # Automatically divert to Freepik if Gemini fails (e.g. due to quota limit or missing key)
            fallback_provider = FreepikMysticProvider(style="photo")
            return await fallback_provider.generate(prompt, count)


# Note: Gemini image models use generateContent API (not generate_images).
# They return image bytes in the response parts.


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

    Returns public image URLs directly (Freepik hosts them).
    """

    def __init__(self, style: str = "photo"):
        self.style = style  # "photo" | "digital-art"

    async def generate(self, prompt: str, count: int = 4) -> list[str]:
        settings = get_settings()
        headers = {
            "x-freepik-api-key": settings.freepik_api_key,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=90) as client:
            # Step 1: Submit the job
            submit = await client.post(
                "https://api.freepik.com/v1/ai/mystic",
                headers=headers,
                json={
                    "prompt": prompt,
                    "image": {"size": {"width": 1920, "height": 1080}},
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
        # ── Gemini API ────────────────────────────────────────────────────────
        "gemini_imagen3":      GeminiImageProvider("gemini-3.1-flash-image"),
        "gemini_imagen3_fast": GeminiImageProvider("gemini-3.1-flash-lite-image"),
        "gemini_image_pro":    GeminiImageProvider("gemini-3-pro-image"),

        # ── Freepik API ───────────────────────────────────────────────────────
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
