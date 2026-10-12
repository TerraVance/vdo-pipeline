import threading
from typing import Optional
from supabase import create_client, Client, ClientOptions
from app.core.config import get_settings
from app.core.logging import logger

_client: Optional[Client] = None
_client_lock = threading.Lock()


def get_supabase() -> Client:
    """Thread-safe singleton accessor for the Supabase service-role client."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                settings = get_settings()
                logger.info("Initializing Supabase client with service role key")
                _client = create_client(
                    settings.supabase_url,
                    settings.supabase_service_role_key,  # Service role bypasses RLS for backend operations
                    options=ClientOptions(
                        postgrest_client_timeout=20,  # 20s — resilient against transient network latency
                        storage_client_timeout=45,    # 45s — file uploads need more time
                    ),
                )
    return _client

