import csv
import io
import requests
from datetime import datetime, timezone

from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from profiles.models import Profile
from profiles.parser import parse_query
from core.auth import require_auth, require_admin, require_api_version
from core.rate_limit import check_rate_limit


# ───────────────────────── helpers ──────────────────────────────

VALID_SORT_FIELDS = {"age", "created_at", "gender_probability", "country_probability"}
VALID_GENDERS = {"male", "female"}
VALID_AGE_GROUPS = {"child", "teenager", "adult", "senior"}


def _paginate(queryset, request, base_path: str) -> dict:
    try:
        page = max(1, int(request.GET.get("page", 1)))
    except ValueError:
        page = 1
    try:
        limit = min(50, max(1, int(request.GET.get("limit", 10))))
    except ValueError:
        limit = 10

    total = queryset.count()
    total_pages = max(1, (total + limit - 1) // limit)
    page = min(page, total_pages)
    offset = (page - 1) * limit
    items = queryset[offset : offset + limit]

    # Build query string without page/limit
    params = request.GET.copy()
    params.pop("page", None)
    params.pop("limit", None)
    base_qs = params.urlencode()
    sep = "&" if base_qs else ""

    def make_link(p):
        return f"{base_path}?{base_qs}{sep}page={p}&limit={limit}"

    return {
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages,
        "links": {
            "self": make_link(page),
            "next": make_link(page + 1) if page < total_pages else None,
            "prev": make_link(page - 1) if page > 1 else None,
        },
        "items": items,
    }


def _apply_filters(queryset, params: dict):
    gender = params.get("gender")
    if gender:
        if gender not in VALID_GENDERS:
            raise ValueError(f"Invalid gender: {gender}")
        queryset = queryset.filter(gender=gender)

    age_group = params.get("age_group")
    if age_group:
        if age_group not in VALID_AGE_GROUPS:
            raise ValueError(f"Invalid age_group: {age_group}")
        queryset = queryset.filter(age_group=age_group)

    country_id = params.get("country_id")
    if country_id:
        queryset = queryset.filter(country_id=country_id.upper())

    try:
        if params.get("min_age"):
            queryset = queryset.filter(age__gte=int(params["min_age"]))
        if params.get("max_age"):
            queryset = queryset.filter(age__lte=int(params["max_age"]))
        if params.get("min_gender_probability"):
            queryset = queryset.filter(
                gender_probability__gte=float(params["min_gender_probability"])
            )
        if params.get("min_country_probability"):
            queryset = queryset.filter(
                country_probability__gte=float(params["min_country_probability"])
            )
    except (ValueError, TypeError) as e:
        raise ValueError(str(e))

    sort_by = params.get("sort_by", "created_at")
    if sort_by not in VALID_SORT_FIELDS:
        sort_by = "created_at"
    order = params.get("order", "asc")
    prefix = "-" if order == "desc" else ""
    queryset = queryset.order_by(f"{prefix}{sort_by}")

    return queryset


def _fetch_external_profile(name: str) -> dict | None:
    """Calls genderize, agify, nationalize APIs to build a profile."""
    try:
        g = requests.get(
            settings.GENDERIZE_API_URL, params={"name": name}, timeout=10
        ).json()
        a = requests.get(
            settings.AGIFY_API_URL, params={"name": name}, timeout=10
        ).json()
        n = requests.get(
            settings.NATIONALIZE_API_URL, params={"name": name}, timeout=10
        ).json()
    except Exception:
        return None

    gender = g.get("gender")
    gender_probability = g.get("probability", 0)
    age = a.get("age")
    countries = n.get("country", [])
    top_country = countries[0] if countries else {}

    if not gender or not age:
        return None

    country_id = top_country.get("country_id", "")
    country_probability = top_country.get("probability", 0)

    # Determine age group
    if age < 13:
        age_group = "child"
    elif age < 18:
        age_group = "teenager"
    elif age < 65:
        age_group = "adult"
    else:
        age_group = "senior"

    # Resolve country name
    COUNTRY_NAMES = {
        "NG": "Nigeria", "KE": "Kenya", "GH": "Ghana", "ZA": "South Africa",
        "ET": "Ethiopia", "EG": "Egypt", "TZ": "Tanzania", "UG": "Uganda",
        "US": "United States", "GB": "United Kingdom", "FR": "France",
        "DE": "Germany", "CA": "Canada", "AU": "Australia", "IN": "India",
        "CN": "China", "BR": "Brazil", "JP": "Japan",
    }
    country_name = COUNTRY_NAMES.get(country_id, country_id)

    return {
        "gender": gender,
        "gender_probability": gender_probability,
        "age": age,
        "age_group": age_group,
        "country_id": country_id,
        "country_name": country_name,
        "country_probability": country_probability,
    }


# ──────────────────────────── views ─────────────────────────────

@require_http_methods(["GET"])
@require_auth
@require_api_version
def list_profiles(request):
    rl = check_rate_limit(request, group="api")
    if rl:
        return rl

    try:
        queryset = _apply_filters(Profile.objects.all(), request.GET)
    except ValueError as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=422)

    paginated = _paginate(queryset, request, "/api/profiles")

    return JsonResponse({
        "status": "success",
        "page": paginated["page"],
        "limit": paginated["limit"],
        "total": paginated["total"],
        "total_pages": paginated["total_pages"],
        "links": paginated["links"],
        "data": [p.to_dict() for p in paginated["items"]],
    })


@csrf_exempt
@require_http_methods(["POST"])
@require_admin
@require_api_version
def create_profile(request):
    rl = check_rate_limit(request, group="api")
    if rl:
        return rl

    import json
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)

    name = (body.get("name") or "").strip()
    if not name:
        return JsonResponse({"status": "error", "message": "name is required"}, status=400)

    if Profile.objects.filter(name__iexact=name).exists():
        return JsonResponse(
            {"status": "error", "message": "Profile with this name already exists"},
            status=409,
        )

    external_data = _fetch_external_profile(name)
    if not external_data:
        return JsonResponse(
            {"status": "error", "message": "Could not determine profile data for this name"},
            status=422,
        )

    profile = Profile.objects.create(name=name, **external_data)
    return JsonResponse({"status": "success", "data": profile.to_dict()}, status=201)


@require_http_methods(["GET"])
@require_auth
@require_api_version
def get_profile(request, profile_id: str):
    rl = check_rate_limit(request, group="api")
    if rl:
        return rl

    try:
        profile = Profile.objects.get(id=profile_id)
    except Profile.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Profile not found"}, status=404)

    return JsonResponse({"status": "success", "data": profile.to_dict()})


@require_http_methods(["GET"])
@require_auth
@require_api_version
def search_profiles(request):
    rl = check_rate_limit(request, group="api")
    if rl:
        return rl

    q = (request.GET.get("q") or "").strip()
    if not q:
        return JsonResponse(
            {"status": "error", "message": "Query parameter 'q' is required"}, status=400
        )

    filters = parse_query(q)
    if not filters:
        return JsonResponse(
            {"status": "error", "message": "Unable to interpret query"}, status=422
        )

    try:
        queryset = _apply_filters(Profile.objects.all(), {**filters, **request.GET.dict()})
    except ValueError as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=422)

    paginated = _paginate(queryset, request, "/api/profiles/search")

    return JsonResponse({
        "status": "success",
        "query": q,
        "interpreted_filters": filters,
        "page": paginated["page"],
        "limit": paginated["limit"],
        "total": paginated["total"],
        "total_pages": paginated["total_pages"],
        "links": paginated["links"],
        "data": [p.to_dict() for p in paginated["items"]],
    })


@require_http_methods(["GET"])
@require_auth
@require_api_version
def export_profiles(request):
    rl = check_rate_limit(request, group="api")
    if rl:
        return rl

    fmt = request.GET.get("format", "csv").lower()
    if fmt != "csv":
        return JsonResponse(
            {"status": "error", "message": "Only format=csv is supported"}, status=400
        )

    try:
        queryset = _apply_filters(Profile.objects.all(), request.GET)
    except ValueError as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=422)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"profiles_{timestamp}.csv"

    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "id", "name", "gender", "gender_probability",
        "age", "age_group", "country_id", "country_name",
        "country_probability", "created_at",
    ])

    for p in queryset.iterator():
        writer.writerow([
            p.id, p.name, p.gender, p.gender_probability,
            p.age, p.age_group, p.country_id, p.country_name,
            p.country_probability, p.created_at.isoformat(),
        ])

    response = HttpResponse(output.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
