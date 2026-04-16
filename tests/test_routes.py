import pytest
from app import create_app, db
from app.models import Profile


@pytest.fixture
def app():
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'API_TIMEOUT': 10,
    })

    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


class TestClassification:
    def test_age_group_child(self):
        from app.services.classification import classify_age_group
        assert classify_age_group(5) == 'child'
        assert classify_age_group(0) == 'child'
        assert classify_age_group(12) == 'child'

    def test_age_group_teenager(self):
        from app.services.classification import classify_age_group
        assert classify_age_group(13) == 'teenager'
        assert classify_age_group(17) == 'teenager'
        assert classify_age_group(19) == 'teenager'

    def test_age_group_adult(self):
        from app.services.classification import classify_age_group
        assert classify_age_group(20) == 'adult'
        assert classify_age_group(35) == 'adult'
        assert classify_age_group(59) == 'adult'

    def test_age_group_senior(self):
        from app.services.classification import classify_age_group
        assert classify_age_group(60) == 'senior'
        assert classify_age_group(75) == 'senior'
        assert classify_age_group(100) == 'senior'

    def test_age_group_none(self):
        from app.services.classification import classify_age_group
        assert classify_age_group(None) is None

    def test_top_nationality(self):
        from app.services.classification import get_top_nationality
        response = {
            'country': [
                {'country_id': 'US', 'probability': 0.7},
                {'country_id': 'GB', 'probability': 0.2},
                {'country_id': 'CA', 'probability': 0.1},
            ]
        }
        code, prob = get_top_nationality(response)
        assert code == 'US'
        assert prob == 0.7

    def test_top_nationality_empty(self):
        from app.services.classification import get_top_nationality
        code, prob = get_top_nationality({})
        assert code is None
        assert prob is None


class TestValidation:
    def test_validate_genderize_ok(self):
        from app.services.classification import validate_genderize_response
        assert validate_genderize_response({'gender': 'male', 'count': 100}) is True

    def test_validate_genderize_null_gender(self):
        from app.services.classification import validate_genderize_response
        assert validate_genderize_response({'gender': None, 'count': 100}) is False

    def test_validate_genderize_zero_count(self):
        from app.services.classification import validate_genderize_response
        assert validate_genderize_response({'gender': 'male', 'count': 0}) is False

    def test_validate_agify_ok(self):
        from app.services.classification import validate_agify_response
        assert validate_agify_response({'age': 30}) is True

    def test_validate_agify_null_age(self):
        from app.services.classification import validate_agify_response
        assert validate_agify_response({'age': None}) is False

    def test_validate_nationalize_ok(self):
        from app.services.classification import validate_nationalize_response
        assert validate_nationalize_response({'country': [{'country_id': 'US'}]}) is True

    def test_validate_nationalize_empty_country(self):
        from app.services.classification import validate_nationalize_response
        assert validate_nationalize_response({'country': []}) is False


class TestErrorResponse:
    def test_error_format(self, client):
        """Error responses follow {status: 'error', message: '...'} format"""
        response = client.get('/api/profiles/nonexistent-id')
        assert response.status_code == 404
        data = response.json
        assert data['status'] == 'error'
        assert 'message' in data

    def test_missing_name(self, client):
        response = client.post('/api/profiles', json={})
        assert response.status_code == 400
        data = response.json
        assert data['status'] == 'error'
        assert data['message'] == 'Missing or empty name'

    def test_empty_name(self, client):
        response = client.post('/api/profiles', json={'name': '   '})
        assert response.status_code == 400
        data = response.json
        assert data['status'] == 'error'
        assert data['message'] == 'Missing or empty name'

    def test_invalid_type(self, client):
        response = client.post('/api/profiles', json={'name': 123})
        assert response.status_code == 422
        data = response.json
        assert data['status'] == 'error'
        assert data['message'] == 'Invalid type'

    def test_name_too_long(self, client):
        long_name = 'a' * 256
        response = client.post('/api/profiles', json={'name': long_name})
        assert response.status_code == 400

    def test_not_found(self, client):
        response = client.get('/api/profiles/nonexistent-id')
        assert response.status_code == 404
        data = response.json
        assert data['status'] == 'error'
        assert data['message'] == 'Profile not found'


class TestRoutes:
    def test_health(self, client):
        response = client.get('/health')
        assert response.status_code == 200
        assert response.json['status'] == 'healthy'

    def test_list_profiles_empty(self, client):
        response = client.get('/api/profiles')
        assert response.status_code == 200
        data = response.json
        assert data['status'] == 'success'
        assert data['count'] == 0
        assert data['data'] == []

    def test_get_profile_not_found(self, client):
        response = client.get('/api/profiles/nonexistent-id')
        assert response.status_code == 404

    def test_delete_profile_not_found(self, client):
        response = client.delete('/api/profiles/nonexistent-id')
        assert response.status_code == 404

    def test_get_stats(self, client):
        response = client.get('/api/profiles/stats')
        assert response.status_code == 200
        data = response.json
        assert data['status'] == 'success'
        assert 'total' in data['data']
        assert 'age_group_distribution' in data['data']
        assert 'gender_distribution' in data['data']


class TestEnrichmentError:
    def test_enrichment_error_format(self):
        from app.services.enrichment import EnrichmentError
        err = EnrichmentError('Genderize')
        assert err.api_name == 'Genderize'
        assert err.message == 'Genderize returned an invalid response'
