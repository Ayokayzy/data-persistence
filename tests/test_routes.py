import pytest
from datetime import datetime, timezone, timedelta
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
    @staticmethod
    def _seed_profiles():
        base = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc).replace(tzinfo=None)
        rows = [
            Profile(
                name='emmanuel',
                gender='male',
                gender_probability=0.99,
                age=34,
                age_group='adult',
                country_id='NG',
                country_probability=0.85,
                created_at=base + timedelta(days=1),
            ),
            Profile(
                name='sarah',
                gender='female',
                gender_probability=0.95,
                age=28,
                age_group='adult',
                country_id='US',
                country_probability=0.75,
                created_at=base + timedelta(days=2),
            ),
            Profile(
                name='jide',
                gender='male',
                gender_probability=0.80,
                age=19,
                age_group='teenager',
                country_id='NG',
                country_probability=0.60,
                created_at=base + timedelta(days=3),
            ),
            Profile(
                name='musa',
                gender='male',
                gender_probability=0.88,
                age=21,
                age_group='adult',
                country_id='KE',
                country_probability=0.77,
                created_at=base + timedelta(days=4),
            ),
            Profile(
                name='helena',
                gender='female',
                gender_probability=0.92,
                age=35,
                age_group='adult',
                country_id='AO',
                country_probability=0.81,
                created_at=base + timedelta(days=5),
            ),
            Profile(
                name='amina',
                gender='female',
                gender_probability=0.91,
                age=18,
                age_group='teenager',
                country_id='NG',
                country_probability=0.84,
                created_at=base + timedelta(days=6),
            ),
        ]
        db.session.add_all(rows)
        db.session.commit()

    def test_health(self, client):
        response = client.get('/health')
        assert response.status_code == 200
        assert response.json['status'] == 'healthy'

    def test_list_profiles_empty(self, client):
        response = client.get('/api/profiles')
        assert response.status_code == 200
        data = response.json
        assert data['status'] == 'success'
        assert data['page'] == 1
        assert data['limit'] == 10
        assert data['total'] == 0
        assert data['data'] == []

    def test_list_profiles_combined_filters(self, app, client):
        with app.app_context():
            self._seed_profiles()

        response = client.get(
            '/api/profiles?gender=male&country_id=NG&min_age=25&sort_by=age&order=desc&page=1&limit=10'
        )
        assert response.status_code == 200
        data = response.json
        assert data['status'] == 'success'
        assert data['page'] == 1
        assert data['limit'] == 10
        assert data['total'] == 1
        assert len(data['data']) == 1
        assert data['data'][0]['name'] == 'emmanuel'
        assert data['data'][0]['country_name'] is None

    def test_list_profiles_sorting(self, app, client):
        with app.app_context():
            self._seed_profiles()

        age_desc = client.get('/api/profiles?sort_by=age&order=desc').json['data']
        assert [p['name'] for p in age_desc] == ['helena', 'emmanuel', 'sarah', 'musa', 'jide', 'amina']

        age_asc = client.get('/api/profiles?sort_by=age&order=asc').json['data']
        assert [p['name'] for p in age_asc] == ['jide', 'amina', 'musa', 'sarah', 'emmanuel', 'helena']

        gp_desc = client.get('/api/profiles?sort_by=gender_probability&order=desc').json['data']
        assert [p['name'] for p in gp_desc] == ['emmanuel', 'sarah', 'helena', 'amina', 'musa', 'jide']

    def test_list_profiles_pagination_defaults_and_bounds(self, app, client):
        with app.app_context():
            self._seed_profiles()

        default_response = client.get('/api/profiles')
        assert default_response.status_code == 200
        default_data = default_response.json
        assert default_data['page'] == 1
        assert default_data['limit'] == 10

        capped_limit = client.get('/api/profiles?limit=500').json
        assert capped_limit['limit'] == 50

        invalid_values = client.get('/api/profiles?page=0&limit=-2').json
        assert invalid_values['page'] == 1
        assert invalid_values['limit'] == 10

    def test_list_profiles_invalid_params_fallback(self, app, client):
        with app.app_context():
            self._seed_profiles()

        data = client.get('/api/profiles?sort_by=nope&order=up&page=abc&limit=xyz&min_age=not-a-number').json
        assert data['status'] == 'success'
        assert data['page'] == 1
        assert data['limit'] == 10
        # Falls back to created_at desc: newest seeded row first.
        assert data['data'][0]['name'] == 'amina'

    def test_list_profiles_response_shape(self, app, client):
        with app.app_context():
            self._seed_profiles()

        payload = client.get('/api/profiles').json
        assert set(payload.keys()) == {'status', 'page', 'limit', 'total', 'data'}
        row = payload['data'][0]
        assert set(row.keys()) == {
            'id',
            'name',
            'gender',
            'gender_probability',
            'age',
            'age_group',
            'country_id',
            'country_name',
            'country_probability',
            'created_at',
        }

    def test_list_route_delegates_to_profile_services(self, app, client, monkeypatch):
        with app.app_context():
            from app import routes

            calls = {'parse': 0, 'build': 0, 'apply': 0, 'serialize': 0}

            class DummyParams:
                page = 1
                limit = 10

            class DummyQuery:
                def count(self):
                    return 1

                def all(self):
                    return [Profile(name='dummy')]

            def fake_parse(args):
                calls['parse'] += 1
                return DummyParams()

            def fake_build(params):
                calls['build'] += 1
                return DummyQuery()

            def fake_apply(query, params):
                calls['apply'] += 1
                return query

            def fake_serialize(profile):
                calls['serialize'] += 1
                return {
                    'id': 'x',
                    'name': 'dummy',
                    'gender': None,
                    'gender_probability': None,
                    'age': None,
                    'age_group': None,
                    'country_id': None,
                    'country_name': None,
                    'country_probability': None,
                    'created_at': None,
                }

            monkeypatch.setattr(routes, 'parse_profile_list_params', fake_parse)
            monkeypatch.setattr(routes, 'build_profile_list_query', fake_build)
            monkeypatch.setattr(routes, 'apply_sort_and_pagination', fake_apply)
            monkeypatch.setattr(routes, 'serialize_profile_list_item', fake_serialize)

            response = client.get('/api/profiles')
            assert response.status_code == 200
            assert calls == {'parse': 1, 'build': 1, 'apply': 1, 'serialize': 1}

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

    def test_search_profiles_young_males(self, app, client):
        with app.app_context():
            self._seed_profiles()

        response = client.get('/api/profiles/search?q=young+males')
        assert response.status_code == 200
        data = response.json
        assert data['status'] == 'success'
        assert all(row['gender'] == 'male' for row in data['data'])
        assert all(16 <= row['age'] <= 24 for row in data['data'])

    def test_search_profiles_females_above_30(self, app, client):
        with app.app_context():
            self._seed_profiles()

        response = client.get('/api/profiles/search?q=females+above+30')
        assert response.status_code == 200
        data = response.json
        assert all(row['gender'] == 'female' for row in data['data'])
        assert all(row['age'] >= 30 for row in data['data'])

    def test_search_profiles_people_from_angola(self, app, client):
        with app.app_context():
            self._seed_profiles()

        response = client.get('/api/profiles/search?q=people+from+angola')
        assert response.status_code == 200
        data = response.json
        assert data['total'] == 1
        assert data['data'][0]['country_id'] == 'AO'

    def test_search_profiles_adult_males_from_kenya(self, app, client):
        with app.app_context():
            self._seed_profiles()

        response = client.get('/api/profiles/search?q=adult+males+from+kenya')
        assert response.status_code == 200
        data = response.json
        assert data['total'] == 1
        row = data['data'][0]
        assert row['gender'] == 'male'
        assert row['age_group'] == 'adult'
        assert row['country_id'] == 'KE'

    def test_search_profiles_male_and_female_teenagers_above_17(self, app, client):
        with app.app_context():
            self._seed_profiles()

        response = client.get('/api/profiles/search?q=male+and+female+teenagers+above+17')
        assert response.status_code == 200
        data = response.json
        assert data['total'] >= 1
        # gender filter is dropped when both male and female appear.
        assert {row['gender'] for row in data['data']} == {'female', 'male'}
        assert all(row['age_group'] == 'teenager' and row['age'] >= 17 for row in data['data'])

    def test_search_profiles_uninterpretable(self, client):
        response = client.get('/api/profiles/search?q=just+vibes')
        assert response.status_code == 400
        data = response.json
        assert data == {'status': 'error', 'message': 'Unable to interpret query'}

    def test_search_profiles_pagination(self, app, client):
        with app.app_context():
            self._seed_profiles()

        response = client.get('/api/profiles/search?q=adult&page=1&limit=2')
        assert response.status_code == 200
        data = response.json
        assert data['status'] == 'success'
        assert data['page'] == 1
        assert data['limit'] == 2
        assert len(data['data']) == 2


class TestEnrichmentError:
    def test_enrichment_error_format(self):
        from app.services.enrichment import EnrichmentError
        err = EnrichmentError('Genderize')
        assert err.api_name == 'Genderize'
        assert err.message == 'Genderize returned an invalid response'
