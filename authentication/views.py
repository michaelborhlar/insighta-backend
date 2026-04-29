import json
import hashlib
import base64
import requests
from datetime import datetime, timezone

from django.conf import settings
from django.http import JsonResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from authentication.models import User, RefreshToken
from core.tokens import issue_token_pair, decode_access_token
from core.auth import require_auth
from core.rate_limit import check_rate_limit


# ─────────────────────────── helpers ────────────────────────────

def _github_user_info(access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    user_resp = requests.get("https://api.github.com/user", headers=headers, timeout=10)
    user_resp.raise_for_status()
    data = user_resp.json()

    # Fetch email if not public
    email = data.get("email") or ""
    if not email:
        email_resp = requests.get(
            "https://api.github.com/user/emails", headers=headers, timeout=10
        )
        if email_resp.ok:
            emails = email_resp.json()
            primary = next(
                (e["email"] for e in emails if e.get("primary") and e.get("verified")),
                ""
            )
            email = primary

    return {
        "github_id": str(data["id"]),
        "username": data.get("login", ""),
        "email": email,
        "avatar_url": data.get("avatar_url", ""),
    }


def _upsert_user(github_info: dict) -> User:
    user, created = User.objects.get_or_create(
        github_id=github_info["github_id"],
        defaults={
            "username": github_info["username"],
            "email": github_info["email"],
            "avatar_url": github_info["avatar_url"],
            "role": User.ROLE_ANALYST,
        },
    )
    if not created:
        user.username = github_info["username"]
        user.email = github_info["email"]
        user.avatar_url = github_info["avatar_url"]

    user.last_login_at = datetime.now(timezone.utc)
    user.save()
    return user


def _verify_pkce(code_verifier: str, stored_code_challenge: str) -> bool:
    digest = hashlib.sha256(code_verifier.encode()).digest()
    computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return computed == stored_code_challenge


# ─────────────────────────── views ──────────────────────────────

@require_http_methods(["GET"])
def github_authorize(request):
    """GET /auth/github — redirect to GitHub OAuth page."""
    rl = check_rate_limit(request, group="auth")
    if rl:
        return rl

    # For CLI: PKCE params come from CLI; for web: backend generates state
    source = request.GET.get("source", "web")  # 'cli' or 'web'
    code_challenge = request.GET.get("code_challenge", "")
    state = request.GET.get("state", "")

    # Store state in session-like cache for web flow
    from django.core.cache import cache
    if state:
        cache.set(f"oauth_state:{state}", {
            "source": source,
            "code_challenge": code_challenge,
        }, timeout=300)

    redirect_uri = (
        settings.GITHUB_REDIRECT_URI
        if source == "cli"
        else settings.GITHUB_WEB_REDIRECT_URI
    )

    params = (
        f"client_id={settings.GITHUB_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&scope=read:user,user:email"
        f"&state={state}"
    )
    if code_challenge:
        params += f"&code_challenge={code_challenge}&code_challenge_method=S256"

    return HttpResponseRedirect(f"https://github.com/login/oauth/authorize?{params}")


@csrf_exempt
@require_http_methods(["GET", "POST"])
def github_callback(request):
    """
    GET  /auth/github/callback — web browser redirect from GitHub
    POST /auth/github/callback — CLI sends code + code_verifier + state
    """
    rl = check_rate_limit(request, group="auth")
    if rl:
        return rl

    if request.method == "GET":
        code = request.GET.get("code")
        state = request.GET.get("state", "")
        source = "web"
        code_verifier = None
    else:
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse(
                {"status": "error", "message": "Invalid JSON body"}, status=400
            )
        code = body.get("code")
        state = body.get("state", "")
        code_verifier = body.get("code_verifier")
        source = body.get("source", "cli")

    if not code:
        return JsonResponse(
            {"status": "error", "message": "Missing code parameter"}, status=400
        )

    # Validate state
    from django.core.cache import cache
    state_data = cache.get(f"oauth_state:{state}")
    if state and not state_data:
        return JsonResponse(
            {"status": "error", "message": "Invalid or expired state"}, status=400
        )

    # PKCE verification (CLI flow)
    if code_verifier and state_data and state_data.get("code_challenge"):
        if not _verify_pkce(code_verifier, state_data["code_challenge"]):
            return JsonResponse(
                {"status": "error", "message": "PKCE verification failed"}, status=400
            )

    # Consume state
    if state:
        cache.delete(f"oauth_state:{state}")

    redirect_uri = (
        settings.GITHUB_REDIRECT_URI
        if source == "cli"
        else settings.GITHUB_WEB_REDIRECT_URI
    )

    # Exchange code for GitHub access token
    token_resp = requests.post(
        "https://github.com/login/oauth/access_token",
        json={
            "client_id": settings.GITHUB_CLIENT_ID,
            "client_secret": settings.GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": redirect_uri,
        },
        headers={"Accept": "application/json"},
        timeout=15,
    )
    if not token_resp.ok:
        return JsonResponse(
            {"status": "error", "message": "Failed to exchange code with GitHub"},
            status=502,
        )

    token_data = token_resp.json()
    github_token = token_data.get("access_token")
    if not github_token:
        return JsonResponse(
            {"status": "error", "message": token_data.get("error_description", "GitHub OAuth failed")},
            status=400,
        )

    # Get user info from GitHub
    try:
        github_info = _github_user_info(github_token)
    except Exception:
        return JsonResponse(
            {"status": "error", "message": "Failed to retrieve GitHub user info"},
            status=502,
        )

    user = _upsert_user(github_info)

    if not user.is_active:
        return JsonResponse(
            {"status": "error", "message": "Account is disabled"}, status=403
        )

    tokens = issue_token_pair(user, RefreshToken)

    if source == "web":
        # Web: set HTTP-only cookies
        web_portal_url = settings.WEB_PORTAL_ORIGIN
        response = HttpResponseRedirect(f"{web_portal_url}/dashboard")
        response.set_cookie(
            "access_token",
            tokens["access_token"],
            httponly=True,
            samesite="Lax",
            max_age=settings.ACCESS_TOKEN_EXPIRY_SECONDS,
            secure=not settings.DEBUG,
        )
        response.set_cookie(
            "refresh_token",
            tokens["refresh_token"],
            httponly=True,
            samesite="Lax",
            max_age=settings.REFRESH_TOKEN_EXPIRY_SECONDS,
            secure=not settings.DEBUG,
        )
        return response

    # CLI: return tokens in JSON
    return JsonResponse({
        "status": "success",
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "user": {
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "avatar_url": user.avatar_url,
        },
    })


@csrf_exempt
@require_http_methods(["POST"])
def refresh_token_view(request):
    """POST /auth/refresh — issue new token pair from refresh token."""
    rl = check_rate_limit(request, group="auth")
    if rl:
        return rl

    # Accept from JSON body (CLI) or cookie (web)
    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        body = {}

    refresh_value = body.get("refresh_token") or request.COOKIES.get("refresh_token")

    if not refresh_value:
        return JsonResponse(
            {"status": "error", "message": "Refresh token required"}, status=400
        )

    now = datetime.now(timezone.utc)
    try:
        token_obj = RefreshToken.objects.select_related("user").get(
            token=refresh_value, revoked=False
        )
    except RefreshToken.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "Invalid or revoked refresh token"}, status=401
        )

    if token_obj.expires_at < now:
        token_obj.revoked = True
        token_obj.save()
        return JsonResponse(
            {"status": "error", "message": "Refresh token expired"}, status=401
        )

    user = token_obj.user
    if not user.is_active:
        return JsonResponse(
            {"status": "error", "message": "Account is disabled"}, status=403
        )

    # Revoke old, issue new pair
    token_obj.revoked = True
    token_obj.save()
    tokens = issue_token_pair(user, RefreshToken)

    response = JsonResponse({
        "status": "success",
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
    })

    # Update cookies for web clients
    response.set_cookie(
        "access_token", tokens["access_token"],
        httponly=True, samesite="Lax",
        max_age=settings.ACCESS_TOKEN_EXPIRY_SECONDS,
        secure=not settings.DEBUG,
    )
    response.set_cookie(
        "refresh_token", tokens["refresh_token"],
        httponly=True, samesite="Lax",
        max_age=settings.REFRESH_TOKEN_EXPIRY_SECONDS,
        secure=not settings.DEBUG,
    )
    return response


@csrf_exempt
@require_http_methods(["POST"])
@require_auth
def logout_view(request):
    """POST /auth/logout — invalidate refresh token."""
    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        body = {}

    refresh_value = body.get("refresh_token") or request.COOKIES.get("refresh_token")

    if refresh_value:
        RefreshToken.objects.filter(
            user=request.user, token=refresh_value, revoked=False
        ).update(revoked=True)

    response = JsonResponse({"status": "success", "message": "Logged out"})
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response


@require_http_methods(["GET"])
@require_auth
def whoami_view(request):
    """GET /auth/whoami — returns current user info."""
    user = request.user
    return JsonResponse({
        "status": "success",
        "data": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "avatar_url": user.avatar_url,
            "role": user.role,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "created_at": user.created_at.isoformat(),
        },
    })
