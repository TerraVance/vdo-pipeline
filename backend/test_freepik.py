import asyncio
import httpx
from app.core.config import get_settings

async def test():
    settings = get_settings()
    headers = {"x-freepik-api-key": settings.freepik_api_key, "Content-Type": "application/json"}
    
    payload1 = {
        "prompt": "A test landscape",
        "aspect_ratio": "widescreen_16_9"
    }
    
    payload2 = {
        "prompt": "A test landscape",
        "image": {"size": "widescreen_16_9"}
    }

    async with httpx.AsyncClient(timeout=90) as client:
        # Submit both
        res1 = await client.post("https://api.freepik.com/v1/ai/mystic", headers=headers, json=payload1)
        res2 = await client.post("https://api.freepik.com/v1/ai/mystic", headers=headers, json=payload2)
        
        t1 = res1.json()["data"]["task_id"]
        t2 = res2.json()["data"]["task_id"]
        
        for _ in range(24):
            await asyncio.sleep(5)
            poll1 = await client.get(f"https://api.freepik.com/v1/ai/mystic/{t1}", headers=headers)
            poll2 = await client.get(f"https://api.freepik.com/v1/ai/mystic/{t2}", headers=headers)
            
            d1 = poll1.json().get("data", {})
            d2 = poll2.json().get("data", {})
            
            if d1.get("status") == "COMPLETED" and d2.get("status") == "COMPLETED":
                url1 = d1["generated"][0]
                url2 = d2["generated"][0]
                print(f"Payload 1 (top-level aspect_ratio) URL: {url1}")
                print(f"Payload 2 (image.size) URL: {url2}")
                break

if __name__ == "__main__":
    asyncio.run(test())
