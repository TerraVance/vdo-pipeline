from app.core.database import get_supabase
db = get_supabase()
messages = db.table("messages").select("*").order("created_at", desc=True).limit(5).execute()
for m in messages.data:
    print(f"Role: {m['role']}, Status: {m['status']}, Content: {m['content']}")
