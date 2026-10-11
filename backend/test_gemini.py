import asyncio
from app.services.image_service import GeminiImageProvider

async def test():
    provider = GeminiImageProvider("gemini-3.1-flash-image")
    try:
        res = await provider.generate("A test image", 1, "16:9")
        print("Success:", len(res))
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
