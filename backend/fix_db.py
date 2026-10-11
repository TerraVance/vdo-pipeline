from app.core.database import get_supabase
db = get_supabase()
db.table("messages").update({"status": "FAILED"}).eq("status", "PENDING").execute()
print("Fixed PENDING messages.")
