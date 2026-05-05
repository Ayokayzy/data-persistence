# Insighta Labs+ — Backend

A Flask-based REST API that forms the secure, authoritative backend of the Insighta Labs+ platform. It enriches person names with data from three external APIs (Genderize, Agify, Nationalize), stores enriched profiles in PostgreSQL, and exposes them through a secure, role-protected REST API.

---

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Insighta Labs+                    │
│                                                     │
│   ┌──────────────┐    ┌──────────────────────────┐  │
│   │  CLI (Python)│    │  Web Portal (React/Vite) │  │
│   │  insighta-   │    │  insighta-web/           │  │
│   │  cli/        │    │                          │  │
│   └──────┬───────┘    └─────────────┬────────────┘  │
│          │  Bearer token             │  HTTP-only    │
│          │  X-API-Version: 1         │  auth cookies │
│          └────────────┬─────────────┘               │
│                       │                             │
│            ┌──────────▼──────────┐                  │
│            │   Flask Backend     │                  │
│            │                     │                  │
│            │  /auth/*            │                  │
│            │  /api/*             │                  │
│            │                     │                  │
│            │  ┌───────────────┐  │                  │
│            │  │  PostgreSQL   │  │                  │
│            │  │  profiles     │  │                  │
│            │  │  users        │  │                  │
│            │  │  refresh_     │  │                  │
│            │  │  tokens       │  │                  │
│            │  └───────────────┘  │                  │
│            └─────────────────────┘                  │
└─────────────────────────────────────────────────────┘
```

Single source of truth: all auth, RBAC, rate limiting, and data access are enforced by the backend. Both the CLI and web portal are thin clients.

---

## Authentication Flow

### CLI — PKCE OAuth

1. `insighta login` generates a cryptographically random `state` and `code_verifier` locally.
2. `code_challenge = BASE64URL(SHA-256(code_verifier))` is computed in the CLI.
3. CLI calls `GET /auth/github?state=...&code_challenge=...&redirect_uri=http://127.0.0.1:<port>/callback&response_mode=json`.
4. Backend returns the GitHub OAuth URL with PKCE params.
5. CLI opens the URL in the browser and starts a local HTTP server on an ephemeral port.
6. User authenticates on GitHub; GitHub redirects to `http://127.0.0.1:<port>/callback?code=...&state=...`.
7. CLI captures `code` and validates `state` matches what it generated.
8. CLI calls `GET /auth/github/callback?code=...&state=...&code_verifier=...&redirect_uri=...&mode=json`.
9. Backend sends `code + code_verifier + redirect_uri` to GitHub's token endpoint (PKCE exchange).
10. Backend fetches user profile + primary email from the GitHub API.
11. Backend upserts the user, issues an access token (3 min) and a refresh token (5 min).
12. CLI stores `{ api_base, access_token, refresh_token, user }` at `~/.insighta/credentials.json`.
13. CLI prints `Logged in as @<username>`.

### Web Portal — Cookie-based OAuth

1. User clicks "Continue with GitHub" → browser navigates to `GET /auth/github?response_mode=redirect`.
2. Backend generates `state` and `code_verifier`, stores them in HTTP-only cookies (`insighta_oauth_state`, `insighta_code_verifier`, 10 min TTL), then redirects to GitHub.
3. GitHub redirects back to the configured `WEB_CALLBACK_URL` (e.g. `https://backend.example.com/auth/github/callback?mode=cookie`).
4. Backend reads state and verifier from cookies, validates state, performs the PKCE code exchange with GitHub, upserts the user.
5. Backend sets HTTP-only cookies: `insighta_access_token` (3 min), `insighta_refresh_token` (5 min), and a readable `insighta_csrf_token` (5 min).
6. Backend redirects to `WEB_POST_LOGIN_REDIRECT` (e.g. `https://portal.example.com/dashboard`).
7. All subsequent API calls from the web portal attach `X-CSRF-Token` from the readable CSRF cookie.

---

## Token Handling Approach

| Token | Storage | Expiry | Notes |
|-------|---------|--------|-------|
| Access token | CLI: `credentials.json` / Web: HTTP-only cookie | 3 minutes | JWT signed with HS256; contains `sub`, `role`, `type=access` |
| Refresh token | CLI: `credentials.json` / Web: HTTP-only cookie | 5 minutes | Opaque random token; only a SHA-256 hash is stored server-side |

**Rotation**: `POST /auth/refresh` atomically revokes the supplied refresh token and issues a new token pair. Reusing an already-revoked refresh token returns `401 Invalid refresh token`.

**Logout**: `POST /auth/logout` revokes the refresh token server-side and clears all auth cookies.

**CLI auto-refresh**: On every `_api_request`, a `401` response triggers an automatic refresh attempt. If the refresh also fails (expired or revoked), the user is prompted to re-run `insighta login`.

---

## Role Enforcement Logic

| Role | Create | Update | Delete | Read | Search | Export |
|------|--------|--------|--------|------|--------|--------|
| `admin` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `analyst` | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |

- Default role on first login: `analyst`.
- Promotion to `admin`: set the GitHub numeric user ID in the `ADMIN_GITHUB_IDS` environment variable (comma-separated list).
- `is_active = false` blocks all protected requests with `403 Forbidden`.
- RBAC is enforced centrally via the `@require_auth(roles=[...])` decorator — no scattered permission checks in handlers.

---

## Natural Language Parsing Approach

`GET /api/profiles/search?q=<query>` uses a purely rule-based parser (no ML or external service):

1. **Normalize**: lowercase, strip leading/trailing whitespace, collapse repeated spaces.
2. **Gender extraction**: detect `male`/`males`/`man`/`men` and `female`/`females`/`woman`/`women`. If both appear in the same query, gender filter is dropped.
3. **Age range extraction**:
   - `above N` / `over N` → `min_age=N`
   - `under N` / `below N` → `max_age=N`
   - `aged N` → `min_age=N, max_age=N`
   - `young` → `min_age=16, max_age=24`
4. **Age group extraction**: `child`, `teenager`, `adult`, `senior` mapped directly.
5. **Country extraction**: `from <country>` matched against full country names (via `pycountry`) and ISO 3166-1 alpha-2 codes.
6. **Filter assembly**: all extracted clauses are ANDed together and passed to the same SQL query pipeline used by `GET /api/profiles`.
7. **Failure**: if no clause can be extracted at all, returns `{ "status": "error", "message": "Unable to interpret query" }`.

---

## CLI Usage

```bash
# Install globally
cd insighta-cli
pip install .

# Auth
insighta login --api-base https://your-backend-url.com
insighta whoami
insighta logout

# Profiles — list with filters
insighta profiles list
insighta profiles list --gender male
insighta profiles list --country NG --age-group adult
insighta profiles list --min-age 25 --max-age 40
insighta profiles list --sort-by age --order desc --page 2 --limit 20

# Profiles — individual
insighta profiles get <profile-id>

# Profiles — natural language search
insighta profiles search "young males from nigeria"

# Profiles — create (admin only)
insighta profiles create --name "Harriet Tubman"

# Profiles — export to CSV
insighta profiles export --format csv
insighta profiles export --format csv --gender male --country NG
```

Credentials are stored at `~/.insighta/credentials.json`. The CLI auto-refreshes the access token on `401` and re-prompts login if the refresh token has also expired.

---

## API Reference

All `/api/*` endpoints require:
- `Authorization: Bearer <access_token>` (or `insighta_access_token` cookie for web)
- `X-API-Version: 1`

### Auth endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/auth/github` | Initiate GitHub OAuth (returns `auth_url` or redirects) |
| GET | `/auth/github/callback` | OAuth callback — exchange code, issue tokens |
| POST | `/auth/refresh` | Rotate token pair |
| POST | `/auth/logout` | Revoke refresh token + clear cookies |
| GET | `/auth/me` | Return current user |

### Profile endpoints

| Method | Path | Role | Description |
|--------|------|------|-------------|
| POST | `/api/profiles` | admin | Create and enrich a profile |
| GET | `/api/profiles` | admin, analyst | List with filters/sort/pagination |
| GET | `/api/profiles/search` | admin, analyst | Natural language search |
| GET | `/api/profiles/export?format=csv` | admin, analyst | Export CSV |
| GET | `/api/profiles/stats` | admin, analyst | Aggregated statistics |
| GET | `/api/profiles/<id>` | admin, analyst | Get by ID |
| GET | `/api/profiles/by-name/<name>` | admin, analyst | Get by name (case-insensitive) |
| PUT | `/api/profiles/<id>` | admin | Update (re-enriches on name change) |
| DELETE | `/api/profiles/<id>` | admin | Delete |

#### Paginated response shape

```json
{
  "status": "success",
  "page": 1,
  "limit": 10,
  "total": 2026,
  "total_pages": 203,
  "links": {
    "self": "/api/profiles?page=1&limit=10",
    "next": "/api/profiles?page=2&limit=10",
    "prev": null
  },
  "data": [ ... ]
}
```

---

## Rate Limiting

| Scope | Limit |
|-------|-------|
| `/auth/*` endpoints | 10 requests / minute |
| All other endpoints | 60 requests / minute per user |

Rate limit key is the authenticated user's ID when a valid JWT is present; falls back to IP for unauthenticated requests.

---

## Request Logging

Every request is logged at INFO level:

```
request method=GET endpoint=/api/profiles status=200 response_time_ms=12.34
```

---

## Running Locally

### Prerequisites

- Python 3.10+
- PostgreSQL 12+
- Node 20+ (for web portal)

### Backend setup

```bash
git clone <backend-repo>
cd data-persistence

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp config.env.example .env
# Edit .env — set DATABASE_URL, JWT_SECRET, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET

flask db upgrade
python run.py
```

### CLI setup

```bash
cd insighta-cli
pip install .
insighta --help
```

### Web portal setup

```bash
cd insighta-web
npm install
# create .env.local: VITE_API_BASE=http://localhost:5000
npm run dev
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres:postgres@localhost:5432/hng_data` |
| `JWT_SECRET` | Secret for signing JWTs | Random (insecure — always set explicitly) |
| `GITHUB_CLIENT_ID` | GitHub OAuth app client ID | — |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth app secret | — |
| `WEB_CALLBACK_URL` | Backend OAuth callback URL used in web flow | `http://localhost:5000/auth/github/callback?mode=cookie` |
| `WEB_POST_LOGIN_REDIRECT` | Where to send the browser after web login | `http://localhost:3000/dashboard` |
| `COOKIE_SECURE` | Set `Secure` flag on cookies (set `true` in prod) | `false` |
| `CORS_ORIGINS` | Comma-separated list of allowed CORS origins | `http://localhost:5173,http://localhost:3000` |
| `ADMIN_GITHUB_IDS` | Comma-separated GitHub user IDs to grant admin role | empty |
| `API_TIMEOUT` | Timeout for external API calls (seconds) | `10` |

---

## Running Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Flask 3.x (async views enabled) |
| ORM | Flask-SQLAlchemy + Alembic migrations |
| Database | PostgreSQL |
| Auth | PyJWT (HS256), GitHub OAuth 2.0 + PKCE |
| HTTP client | httpx (async) |
| Rate limiting | Flask-Limiter |
| Linting | Ruff |
| Tests | pytest + pytest-flask |
| CLI | Typer + Rich |
| Web portal | React 18 + Vite + React Router v6 |
