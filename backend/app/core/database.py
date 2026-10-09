from typing import Optional
from supabase import create_client, Client, ClientOptions
from app.core.config import get_settings

_client: Optional[Client] = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        settings = get_settings()
        _client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,  # Service role bypasses RLS for backend operations
            options=ClientOptions(
                postgrest_client_timeout=10,   # 10s — fail fast on DB connectivity issues
                storage_client_timeout=30,     # 30s — file uploads need more time
            ),
        )
    return _client
