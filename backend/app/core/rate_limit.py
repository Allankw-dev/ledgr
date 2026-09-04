from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared across main.py (registers the exception handler) and any router
# that needs to rate-limit specific endpoints via @limiter.limit(...).
# Keeping this in its own module avoids main.py <-> routers circular imports.
limiter = Limiter(key_func=get_remote_address)
