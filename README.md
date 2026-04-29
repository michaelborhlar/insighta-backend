# Insighta Labs+ — Backend

Django 5 REST API with GitHub OAuth (PKCE), RBAC, rate limiting, and CSV export.

## System Architecture

```
insighta-backend/
├── insighta_labs/      # Django project config
│   ├── settings.py     # All env-driven settings
│   ├── urls.py         # Route: /auth/* and /api/*
│   └── wsgi.py
├── authentication/     # Auth app
│   ├── models.py       # User (UUID7 PK) + RefreshToken
│   ├── views.py        # GitHub OAuth, refresh, logout, whoami
│   └── urls.py
├── core/               # Shared utilities
│   ├── auth.py         # @require_auth, @require_admin, @require_api_version
│   ├── tokens.py       # JWT access tokens + opaque refresh tokens
│   ├── rate_limit.py   # Cache-based rate limiter
│   ├── middleware.py   # Request logger
│   └── exceptions.py  # Standardized error responses
└── profiles/           # Profile Intelligence (Stage 2+)
    ├── models.py
    ├── views.py        # list, create, get, search, export
    ├── parser.py       # Natural language → filters
    └── urls.py
```

## Authentication Flow

### CLI (PKCE)
1. CLI generates `state`, `code_verifier`, `code_challenge`
2. Registers them with `GET /auth/github?source=cli&state=X&code_challenge=Y`
3. Opens browser → GitHub OAuth page
4. GitHub redirects to local CLI server (`http://localhost:9876/callback`)
5. CLI sends `POST /auth/github/callback` with `{ code, state, code_verifier }`
6. Backend verifies PKCE challenge, exchanges code with GitHub, creates/updates user
7. Returns `{ access_token, refresh_token, user }`

### Web
1. User clicks "Continue with GitHub" → redirected to `GET /auth/github?source=web`
2. GitHub redirects to `GET /auth/github/callback?code=X&state=Y`
3. Backend exchanges code, sets HTTP-only cookies, redirects to portal `/dashboard`

## Token Handling

| Token | Type | Expiry | Storage |
|-------|------|--------|---------|
| Access | Signed JWT (HS256) | 3 minutes | Bearer header (CLI) / HTTP-only cookie (web) |
| Refresh | Opaque UUID4 | 5 minutes | `~/.insighta/credentials.json` (CLI) / HTTP-only cookie (web) |

- Refresh tokens are **single-use**: each `POST /auth/refresh` rotates both tokens
- Old refresh token is revoked immediately on use
- `is_active=false` users get 403 on all endpoints

## Role Enforcement

| Role | Permissions |
|------|------------|
| `admin` | Full access: list, get, create, delete, search, export |
| `analyst` | Read-only: list, get, search, export |

Enforcement is centralized via decorators in `core/auth.py`:
- `@require_auth` — any authenticated user
- `@require_admin` — admin role only
- `@require_api_version` — enforces `X-API-Version: 1` header

## API Endpoints

### Auth
| Method | Endpoint | Auth |
|--------|----------|------|
| GET | `/auth/github` | Public |
| GET/POST | `/auth/github/callback` | Public |
| POST | `/auth/refresh` | Public |
| POST | `/auth/logout` | Required |
| GET | `/auth/whoami` | Required |

### Profiles (all require `X-API-Version: 1`)
| Method | Endpoint | Role |
|--------|----------|------|
| GET | `/api/profiles` | Any |
| POST | `/api/profiles/` | Admin |
| GET | `/api/profiles/<id>` | Any |
| GET | `/api/profiles/search?q=...` | Any |
| GET | `/api/profiles/export?format=csv` | Any |

## Rate Limiting
- `/auth/*` — 10 requests/minute per IP
- `/api/*` — 60 requests/minute per user

## Natural Language Parsing

The parser (`profiles/parser.py`) maps natural language queries to filter params:
- Gender keywords: male/female, man/woman, boy/girl
- Age groups: child, teenager, adult, senior
- Age ranges: "between 25 and 40", "over 30", "under 18"
- Country: 80+ country names and adjectives mapped to ISO codes

## Deployment (Railway)

1. Create a Railway project, add PostgreSQL plugin
2. Set environment variables (see `.env.example`)
3. Railway auto-detects `railway.json` and runs migrations + gunicorn

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in values
python manage.py migrate
python manage.py runserver
```
