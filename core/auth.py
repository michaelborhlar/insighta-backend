import jwt
from functools import wraps
from django.http import JsonResponse
from authentication.models import User
from core.tokens import decode_access_token


def _get_token_from_request(request) -> str | None:
    """Extracts Bearer token from Authorization header or cookie."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    # Fallback: cookie (web portal sends access token as HTTP-only cookie)
    return request.COOKIES.get("access_token")


def _resolve_user(request) -> tuple[User | None, str | None]:
    """Returns (user, error_message)."""
    token = _get_token_from_request(request)
    if not token:
        return None, "Authentication required"

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        return None, "Access token expired"
    except jwt.InvalidTokenError:
        return None, "Invalid token"

    try:
        user = User.objects.get(id=payload["sub"])
    except User.DoesNotExist:
        return None, "User not found"

    if not user.is_active:
        return None, "Account is disabled"

    return user, None


def require_auth(view_func):
    """Decorator: requires valid access token."""
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        user, error = _resolve_user(request)
        if error:
            return JsonResponse({"status": "error", "message": error}, status=401)
        request.user = user
        return view_func(request, *args, **kwargs)
    return wrapped


def require_admin(view_func):
    """Decorator: requires admin role."""
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        user, error = _resolve_user(request)
        if error:
            return JsonResponse({"status": "error", "message": error}, status=401)
        if user.role != "admin":
            return JsonResponse(
                {"status": "error", "message": "Admin access required"}, status=403
            )
        request.user = user
        return view_func(request, *args, **kwargs)
    return wrapped


def require_api_version(view_func):
    """Decorator: enforces X-API-Version: 1 header."""
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        version = request.headers.get("X-API-Version")
        if version != "1":
            return JsonResponse(
                {"status": "error", "message": "API version header required"},
                status=400,
            )
        return view_func(request, *args, **kwargs)
    return wrapped
