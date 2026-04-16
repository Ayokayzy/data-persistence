# Person Data Enrichment & Persistence Service

## 1. Project Overview

- **Project Name**: HNG Data Persistence Service
- **Type**: REST API (Flask + PostgreSQL)
- **Core Functionality**: Accept a name, enrich it via 3 external APIs (Genderize, Agify, Nationalize), classify the data, store in PostgreSQL, and expose CRUD endpoints
- **Target Users**: Developers integrating name enrichment into their applications

## 2. Technology Stack

- **Framework**: Flask
- **ORM**: SQLAlchemy
- **Database**: PostgreSQL
- **HTTP Client**: httpx (async-capable, parallel requests)
- **Migration**: Flask-Migrate (Alembic)

## 3. External APIs (all free, no key required)

| Service | Endpoint | Purpose |
|---------|----------|---------|
| Genderize | `https://api.genderize.io?name={name}` | Predict gender |
| Agify | `https://api.agify.io?name={name}` | Predict age |
| Nationalize | `https://api.nationalize.io?name={name}` | Predict nationality |

## 4. Classification Rules

### Age Group (from Agify)
| Age Range | Classification |
|-----------|----------------|
| 0–12 | child |
| 13–19 | teenager |
| 20–59 | adult |
| 60+ | senior |

### Nationality
- Pick the country with **highest probability** from Nationalize response
- Store both the country code and probability

## 5. Data Model

### Table: `persons`

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| name | VARCHAR(255) | Person's name (indexed, unique) |
| gender | VARCHAR(20) | Predicted gender |
| gender_probability | FLOAT | Gender prediction confidence |
| age | INTEGER | Predicted age |
| age_group | VARCHAR(20) | Classification: child/teenager/adult/senior |
| nationality_code | VARCHAR(10) | Country code with highest probability |
| nationality_probability | FLOAT | Nationality confidence |
| api_responses | JSONB | Raw responses from all 3 APIs |
| created_at | TIMESTAMP | Record creation time |
| updated_at | TIMESTAMP | Last update time |

## 6. API Endpoints

### POST /api/persons
- **Description**: Enrich a name and store the result
- **Request Body**: `{ "name": "John" }`
- **Duplicate Handling**: If name exists, return existing record (no re-fetch)
- **Response**: Created person object

### GET /api/persons
- **Description**: List all persons with pagination
- **Query Params**: `page`, `per_page`
- **Response**: Paginated list of persons

### GET /api/persons/{id}
- **Description**: Get a single person by ID
- **Response**: Person object or 404

### GET /api/persons/by-name/{name}
- **Description**: Get person by exact name
- **Response**: Person object or 404

### PUT /api/persons/{id}
- **Description**: Update a person (re-fetch APIs if name changed)
- **Request Body**: `{ "name": "Jane" }` (optional)
- **Response**: Updated person object

### DELETE /api/persons/{id}
- **Description**: Delete a person
- **Response**: 204 No Content

### GET /api/persons/stats
- **Description**: Get statistics (total count, age group distribution, gender distribution)
- **Response**: Statistics object

## 7. Functionality Specification

### Core Features
- [x] Accept name and make parallel requests to 3 APIs
- [x] Apply classification logic (age group, top nationality)
- [x] Store enriched data in PostgreSQL
- [x] Duplicate detection by name (case-insensitive)
- [x] Return existing record if name already stored
- [x] Full CRUD operations on person records
- [x] Statistics endpoint for data insights
- [x] Graceful error handling with structured error responses

### Error Handling

All errors follow this structure:
```json
{ "status": "error", "message": "<error message>" }
```

| Status Code | Condition | Message |
|------------|-----------|---------|
| 400 | Missing or empty name | Missing or empty name |
| 400 | Name too long (>255) | Name too long (max 255 characters) |
| 404 | Profile not found | Profile not found |
| 409 | Name already exists (PUT) | Name already exists |
| 422 | Invalid type | Invalid type |
| 502 | External API failure | `${externalApi} returned an invalid response` |

**502 error format:**
```json
{ "status": "error", "message": "Genderize returned an invalid response" }
```
Where `externalApi` = `Genderize` | `Agify` | `Nationalize`

### Edge Cases
- Empty or whitespace-only name → 400
- Name too long (>255 chars) → 400
- Non-string name → 422 Unprocessable Entity
- External API timeout → 502 (default 10 second timeout)
- Genderize returns `gender: null` or `count: 0` → 502, do not store
- Agify returns `age: null` → 502, do not store
- Nationalize returns no country data → 502, do not store
- All APIs fail → 502 Bad Gateway

## 8. Project Structure

```
/home/gud-dev/Ayokayzy/hng/data-persistence/
├── app/
│   ├── __init__.py       # Flask app factory
│   ├── config.py          # Configuration
│   ├── models.py          # SQLAlchemy models
│   ├── routes.py          # API routes
│   ├── services/
│   │   ├── __init__.py
│   │   ├── enrichment.py  # External API calls
│   │   └── classification.py  # Classification logic
│   └── utils/
│       └── __init__.py
├── migrations/            # Flask-Migrate
├── tests/
│   └── test_routes.py
├── requirements.txt
├── config.env.example
└── run.py
```

## 9. Configuration (config.env)

```
FLASK_APP=run.py
FLASK_ENV=development
DATABASE_URL=postgresql://user:password@localhost:5432/hng_data
API_TIMEOUT=10
```

## 10. Acceptance Criteria

1. POST `/api/persons` with name "John" creates a record with gender, age, age_group, nationality_code
2. POST with same name "john" returns existing record (no duplicate)
3. GET `/api/persons` returns paginated list
4. GET `/api/persons/stats` returns accurate counts
5. PUT `/api/persons/{id}` updates name and re-fetches if name changed
6. DELETE `/api/persons/{id}` removes record
7. All 3 external APIs are called in parallel
8. Age classification follows the 0-12/13-19/20-59/60+ rules
9. Nationality is the country code with highest probability
10. Application handles API failures gracefully
