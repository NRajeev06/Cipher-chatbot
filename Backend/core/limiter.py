from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from jose import jwt, JWTError
from core.config import settings

def get_user_or_ip(request: Request) -> str:
    """
    Extracts authenticated user_id from Bearer token for user-based rate limiting.
    Falls back to remote IP address for unauthenticated requests.
    """
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
            user_id = payload.get("sub")
            if user_id:
                return f"user:{user_id}"
        except (JWTError, Exception):
            pass
    return f"ip:{get_remote_address(request)}"

limiter = Limiter(key_func=get_user_or_ip)

async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """
    Returns a clean, standard 429 Too Many Requests response with Retry-After header.
    """
    retry_after = "60"
    return JSONResponse(
        status_code=429,
        content={
            "detail": "You're sending requests too quickly. Please wait a moment and try again.",
            "error": "rate_limit_exceeded"
        },
        headers={"Retry-After": retry_after}
    )
