import time
from django.core.cache import cache
from django.http import JsonResponse


def rate_limit(key: str, limit: int, window: int) -> bool:
    """
    Returns True if request is allowed, False if rate limit exceeded.
    key    — unique identifier (IP or user id + endpoint group)
    limit  — max requests in window
    window — window size in seconds
    """
    cache_key = f"rl:{key}"
    now = int(time.time())
    window_start = now - window

    history: list = cache.get(cache_key, [])
    # Drop entries outside current window
    history = [ts for ts in history if ts > window_start]

    if len(history) >= limit:
        return False

    history.append(now)
    cache.set(cache_key, history, timeout=window)
    return True


def check_rate_limit(request, group: str = "api") -> JsonResponse | None:
    """
    Returns a 429 JsonResponse if limit exceeded, else None.
    group: 'auth' → 10/min, 'api' → 60/min per user
    """
    if group == "auth":
        limit, window = 10, 60
        identifier = _get_ip(request)
        key = f"auth:{identifier}"
    else:
        limit, window = 60, 60
        user = getattr(request, "user", None)
        identifier = str(user.id) if user and user.is_authenticated else _get_ip(request)
        key = f"api:{identifier}"

    if not rate_limit(key, limit, window):
        return JsonResponse(
            {"status": "error", "message": "Rate limit exceeded. Try again later."},
            status=429,
        )
    return None


def _get_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")
