import requests

print("Testing DELETE...")
res = requests.delete("http://localhost:8001/api/v1/chat/sessions/12345")
print("DELETE:", res.status_code, res.text)

print("Testing POST create...")
res = requests.post("http://localhost:8001/api/v1/chat/sessions", json={"title": "test"})
print("POST create:", res.status_code, res.text)

print("Testing POST message...")
res = requests.post("http://localhost:8001/api/v1/chat/sessions/12345/messages", json={
    "content": "test",
    "action": "refine_prompt",
    "model": "gemini-3.8-flash"
})
print("POST message:", res.status_code, res.text)

