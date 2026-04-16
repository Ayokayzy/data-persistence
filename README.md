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

Returns all profiles with optional filters.

```bash
# Get all
curl http://localhost:5000/api/profiles

# Filter by gender (case-insensitive)
curl "http://localhost:5000/api/profiles?gender=male"

# Filter by country
curl "http://localhost:5000/api/profiles?country_id=NG"

# Filter by age group
curl "http://localhost:5000/api/profiles?age_group=adult"

# Combine filters
curl "http://localhost:5000/api/profiles?gender=male&country_id=NG&age_group=adult"
```

**Response (200 OK):**
```json
{
  "status": "success",
  "count": 2,
  "data": [
    {
      "id": "id-1",
      "name": "emmanuel",
      "gender": "male",
      "age": 25,
      "age_group": "adult",
      "country_id": "NG"
    }
  ]
}
```

---

### 3. Get Single Profile
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

### 4. Get Profile by Name
**GET** `/api/profiles/by-name/{name}`

```bash
curl "http://localhost:5000/api/profiles/by-name/emmanuel"
```

---

### 5. Update Profile
**PUT** `/api/profiles/{id}`

```bash
curl -X PUT http://localhost:5000/api/profiles/b3f9c1e2-7d4a-4c91-9c2a-1f0a8e5b6d12 \
  -H "Content-Type: application/json" \
  -d '{"name": "john"}'
```

If the name is changed, the API re-fetches enrichment data from external APIs.

---

### 6. Delete Profile
**DELETE** `/api/profiles/{id}`

```bash
curl -X DELETE http://localhost:5000/api/profiles/b3f9c1e2-7d4a-4c91-9c2a-1f0a8e5b6d12
```

Returns `204 No Content` on success.

---

### 7. Get Statistics
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
