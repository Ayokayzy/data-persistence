# HNG Data Persistence Service

A Flask-based REST API that enriches person names with data from 3 free external APIs (Genderize, Agify, Nationalize), classifies the data, and stores it in PostgreSQL.

## Features

- **Name Enrichment**: Fetches gender, age, and nationality predictions from free APIs
- **Duplicate Handling**: Case-insensitive detection — returns existing profile if name already exists
- **Classification**: Automatically classifies age groups (child, teenager, adult, senior)
- **Data Storage**: PostgreSQL with JSONB for raw API responses
- **RESTful API**: Full CRUD operations with structured responses

## Tech Stack

- **Framework**: Flask 3.x
- **ORM**: SQLAlchemy with Flask-SQLAlchemy
- **Database**: PostgreSQL
- **Async HTTP**: httpx for parallel external API calls
- **Migrations**: Flask-Migrate (Alembic)

## Prerequisites

- Python 3.10+
- PostgreSQL 12+

## Getting Started

### 1. Clone & Setup Virtual Environment

```bash
cd /home/gud-dev/Ayokayzy/hng/data-persistence
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Database

Create a `.env` file (or copy from example):

```bash
cp config.env.example .env
```

Edit `.env` with your PostgreSQL credentials:

```env
FLASK_APP=run.py
FLASK_ENV=development
DATABASE_URL=postgresql://user:password@localhost:5432/hng_data
API_TIMEOUT=10
```

### 3. Initialize Database

```bash
# Initialize migrations
flask db init

# Create initial migration
flask db migrate -m "initial migration"

# Apply migrations
flask db upgrade
```

### 4. Run the Server

```bash
python run.py
```

The server starts at `http://localhost:5000`

---

## API Endpoints

### Base URL
```
http://localhost:5000/api
```

### Response Format

**Success:**
```json
{
  "status": "success",
  "data": { ... }
}
```

**Error:**
```json
{
  "status": "error",
  "message": "Error description"
}
```

---

### 1. Create Profile
**POST** `/api/profiles`

Creates a new profile by enriching the name with external API data.

```bash
curl -X POST http://localhost:5000/api/profiles \
  -H "Content-Type: application/json" \
  -d '{"name": "emmanuel"}'
```

**Response (201 Created):**
```json
{
  "status": "success",
  "data": {
    "id": "b3f9c1e2-7d4a-4c91-9c2a-1f0a8e5b6d12",
    "name": "emmanuel",
    "gender": "male",
    "gender_probability": 0.99,
    "sample_size": 1234,
    "age": 25,
    "age_group": "adult",
    "country_id": "NG",
    "country_probability": 0.85,
    "created_at": "2026-04-01T12:00:00Z"
  }
}
```

**Duplicate Response (200 OK):**
```json
{
  "status": "success",
  "message": "Profile already exists",
  "data": { ...existing profile... }
}
```

---

### 2. Get All Profiles
**GET** `/api/profiles`

Returns profiles with filtering, sorting, and pagination.

Supported filters (combinable with AND):
- `gender`
- `age_group`
- `country_id`
- `min_age`
- `max_age`
- `min_gender_probability`
- `min_country_probability`

Sorting:
- `sort_by`: `age` | `created_at` | `gender_probability`
- `order`: `asc` | `desc`

Pagination:
- `page`: default `1`
- `limit`: default `10`, max `50`

Fallback behavior for invalid query values:
- Invalid `sort_by` -> `created_at`
- Invalid `order` -> `desc`
- Invalid/non-positive `page` -> `1`
- Invalid/non-positive `limit` -> `10`
- `limit > 50` -> `50`
- Invalid numeric filters are ignored

```bash
# Get first page
curl http://localhost:5000/api/profiles

# Combined filters + sorting + pagination
curl "http://localhost:5000/api/profiles?gender=male&country_id=NG&min_age=25&sort_by=age&order=desc&page=1&limit=10"
```

**Response (200 OK):**
```json
{
  "status": "success",
  "page": 1,
  "limit": 10,
  "total": 2026,
  "data": [
    {
      "id": "b3f9c1e2-7d4a-4c91-9c2a-1f0a8e5b6d12",
      "name": "emmanuel",
      "gender": "male",
      "gender_probability": 0.99,
      "age": 34,
      "age_group": "adult",
      "country_id": "NG",
      "country_name": null,
      "country_probability": 0.85,
      "created_at": "2026-04-01T12:00:00Z"
    }
  ]
}
```

Implementation note: this endpoint uses a modular query pipeline (`query param parsing` -> `filter builder` -> `sort/pagination` -> `serializer`) to keep route handlers thin and reusable.

---

### 3. Natural Language Search
**GET** `/api/profiles/search`

Parses plain-English query text and maps it to filters using rule-based logic only.

Query parameters:
- `q` (required): natural language query
- `page` and `limit`: same behavior as `GET /api/profiles`

Example:
```bash
curl "http://localhost:5000/api/profiles/search?q=young%20males%20from%20nigeria&page=1&limit=10"
```

Supported mapping examples:
- `young males` -> `gender=male` + `min_age=16` + `max_age=24`
- `females above 30` -> `gender=female` + `min_age=30`
- `people from angola` -> `country_id=AO`
- `adult males from kenya` -> `gender=male` + `age_group=adult` + `country_id=KE`
- `male and female teenagers above 17` -> `age_group=teenager` + `min_age=17` (gender dropped)

If the query cannot be interpreted:
```json
{ "status": "error", "message": "Unable to interpret query" }
```

Success response shape matches `GET /api/profiles`:
```json
{
  "status": "success",
  "page": 1,
  "limit": 10,
  "total": 2026,
  "data": [
    {
      "id": "b3f9c1e2-7d4a-4c91-9c2a-1f0a8e5b6d12",
      "name": "emmanuel",
      "gender": "male",
      "gender_probability": 0.99,
      "age": 34,
      "age_group": "adult",
      "country_id": "NG",
      "country_name": null,
      "country_probability": 0.85,
      "created_at": "2026-04-01T12:00:00Z"
    }
  ]
}
```

---

### 4. Get Single Profile
**GET** `/api/profiles/{id}`

```bash
curl http://localhost:5000/api/profiles/b3f9c1e2-7d4a-4c91-9c2a-1f0a8e5b6d12
```

**Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "id": "b3f9c1e2-7d4a-4c91-9c2a-1f0a8e5b6d12",
    "name": "emmanuel",
    "gender": "male",
    "gender_probability": 0.99,
    "sample_size": 1234,
    "age": 25,
    "age_group": "adult",
    "country_id": "NG",
    "country_probability": 0.85,
    "created_at": "2026-04-01T12:00:00Z"
  }
}
```

---

### 5. Get Profile by Name
**GET** `/api/profiles/by-name/{name}`

```bash
curl "http://localhost:5000/api/profiles/by-name/emmanuel"
```

---

### 6. Update Profile
**PUT** `/api/profiles/{id}`

```bash
curl -X PUT http://localhost:5000/api/profiles/b3f9c1e2-7d4a-4c91-9c2a-1f0a8e5b6d12 \
  -H "Content-Type: application/json" \
  -d '{"name": "john"}'
```

If the name is changed, the API re-fetches enrichment data from external APIs.

---

### 7. Delete Profile
**DELETE** `/api/profiles/{id}`

```bash
curl -X DELETE http://localhost:5000/api/profiles/b3f9c1e2-7d4a-4c91-9c2a-1f0a8e5b6d12
```

Returns `204 No Content` on success.

---

### 8. Get Statistics
**GET** `/api/profiles/stats`

```bash
curl http://localhost:5000/api/profiles/stats
```

**Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "total": 100,
    "age_group_distribution": {
      "adult": 60,
      "child": 20,
      "teenager": 15,
      "senior": 5
    },
    "gender_distribution": {
      "male": 55,
      "female": 45
    }
  }
}
```

---

## Error Handling

| Status | Meaning |
|--------|---------|
| 400 | Missing or empty name |
| 404 | Profile not found |
| 409 | Name already exists (on update) |
| 422 | Invalid type |
| 502 | External API failure |

Example error:
```json
{
  "status": "error",
  "message": "Genderize returned an invalid response"
}
```

---

## Classification Rules

### Age Groups
| Age Range | Group |
|-----------|-------|
| 0–12 | child |
| 13–19 | teenager |
| 20–59 | adult |
| 60+ | senior |

### Nationality
- Picks the country with the **highest probability** from the Nationalize API response

---

## Use Cases

### 1. User Registration Enrichment

When a new user registers on a platform, you can enrich their self-reported name to:

- **Auto-fill demographic fields** (gender, age group, likely nationality) for analytics
- **Personalize user experience** based on inferred demographics
- **Reduce form fields** — instead of asking users to enter age, gender, country, you infer it from their name

**Example Flow:**
```
1. User signs up with name: "Sarah Chen"
2. Your system calls POST /api/profiles with name="Sarah Chen"
3. API returns enriched data: gender=female, age_group=adult, country_id=US
4. Your system stores these insights for personalization
```

---

### 2. Batch Processing of Existing Data

Companies with large databases of customer names can enrich them in batch:

- **Marketing analytics** — segment customers by inferred demographics
- **Fraud detection** — flag anomalies where name demographics don't match other data
- **Data quality** — identify records where name demographics conflict with declared info

**Example Flow:**
```
1. Export existing customer names from your database
2. For each name, call POST /api/profiles
3. Store the enriched data back or in a separate analytics table
4. Query /api/profiles/stats to understand your customer demographics
5. Filter customers with GET /api/profiles?age_group=senior for targeted campaigns
```

---

## Running Tests

```bash
source venv/bin/activate
python -m pytest tests/ -v
```

---

## Seeding Profiles from JSON

You can seed profile records from a JSON array file using the Flask CLI command below.

```bash
flask seed-profiles /absolute/path/to/profiles-2026.json
```

```bash
# Optional: show progress every 50 rows
flask seed-profiles /absolute/path/to/profiles-2026.json --progress-every 50
```

Seed behavior:
- Idempotent by name (case-insensitive): existing names are skipped.
- Transaction-safe: on any error, inserts are rolled back.
- IDs are generated with the model default UUID v7 generator.
- `created_at` / `updated_at` are parsed as ISO 8601 and normalized to UTC.
- Prints progress updates (`processed`, `inserted`, `skipped`, `elapsed_s`) while seeding.

---

## Natural Language Parsing Approach

The natural language search endpoint will use a rule-based parser so the output is deterministic and grading-friendly.

- **Input normalization**: lowercase, trim whitespace, collapse repeated spaces, and tokenize by words and simple operators.
- **Keyword mapping**:
  - gender terms (`male`, `males`, `female`, `females`) -> `gender` filter
  - age group terms (`child`, `teenager`, `adult`, `senior`) -> `age_group` filter
  - country terms (`from nigeria`, `from angola`, `from kenya`) -> `country_id` filter
  - numeric age constraints (`above 30`, `over 30`, `under 18`, `below 18`) -> `age` range filter
  - `young` -> `min_age=16`, `max_age=24`
- **Filter construction**: parsed clauses are converted into a structured filter object and then mapped to SQLAlchemy predicates.
- **Operator behavior**: mixed clauses default to AND semantics. If both male and female appear, gender filtering is dropped and other parsed filters are still applied.
- **Pagination behavior**: `page` and `limit` are accepted via query params and use the same defaults/caps as `GET /api/profiles`.

Example parse flow:
1. Input: `female adults from NG sorted by newest page 2 limit 20`
2. Parsed filters: `gender=female`, `age_group=adult`, `country_id=NG`
3. Sort: `created_at desc`
4. Pagination: `page=2`, `limit=20`

## Natural Language Parser Limitations

Current limitations to keep behavior predictable for automated grading:

- No free-form intent resolution beyond supported keywords.
- No fuzzy matching, typo correction, or synonym expansion outside the documented vocabulary.
- No nested boolean logic with precedence (for example, mixed `AND/OR` groups with parentheses).
- No multilingual parsing; English keywords only.
- Ambiguous country text is not geocoded; only recognized country codes or explicitly supported names are accepted.
- Unsupported phrases return a structured validation error instead of guessing.
- Uninterpretable queries return `{ "status": "error", "message": "Unable to interpret query" }`.

Edge cases intentionally left out for the first release:
- Relative time expressions like `last month` or `this week`.
- Natural language superlatives such as `most likely female`.
- Cross-field comparative expressions such as `older males than females`.

These sections describe the parser contract currently implemented by `GET /api/profiles/search`.

---

## Endpoint Contract Status

Filtering, sorting, pagination, and natural-language search endpoint contracts are now implemented based on the current assignment specification.

---

## Project Structure

```
/home/gud-dev/Ayokayzy/hng/data-persistence/
├── app/
│   ├── __init__.py           # Flask app factory
│   ├── models.py             # Profile SQLAlchemy model
│   ├── routes.py             # API endpoints
│   └── services/
│       ├── enrichment.py     # External API calls
│       └── classification.py # Age/nationality classification
├── migrations/               # Flask-Migrate
├── tests/
│   └── test_routes.py        # Unit tests
├── requirements.txt
├── config.env.example
├── run.py                   # Entry point
└── SPEC.md                  # Full specification
```
