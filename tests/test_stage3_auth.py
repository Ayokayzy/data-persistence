from datetime import datetime, timedelta

from app import create_app, db
from app.models import RefreshToken, User
from app.services.auth import create_access_token, create_refresh_token, hash_token


def _make_app():
    app = create_app(
        {
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///stage3_test.db',
            'API_TIMEOUT': 10,
            'JWT_SECRET': 'test-secret',
        }
    )
    with app.app_context():
        db.drop_all()
        db.create_all()
    return app


def test_api_version_required():
    app = _make_app()
    with app.app_context():
        admin = User(github_id='gh-1', username='admin', role='admin', is_active=True)
        db.session.add(admin)
        db.session.commit()
        token = create_access_token(admin)

    app.config['TESTING'] = False
    client = app.test_client()
    response = client.get('/api/profiles', headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 400
    assert response.json == {'status': 'error', 'message': 'API version header required'}


def test_rbac_analyst_cannot_create_profile():
    app = _make_app()
    with app.app_context():
        analyst = User(github_id='gh-2', username='analyst', role='analyst', is_active=True)
        db.session.add(analyst)
        db.session.commit()
        token = create_access_token(analyst)

    app.config['TESTING'] = False
    client = app.test_client()
    response = client.post(
        '/api/profiles',
        json={'name': 'harriet'},
        headers={'Authorization': f'Bearer {token}', 'X-API-Version': '1'},
    )
    assert response.status_code == 403
    assert response.json == {'status': 'error', 'message': 'Forbidden'}


def test_refresh_rotation_invalidates_old_token():
    app = _make_app()
    with app.app_context():
        user = User(github_id='gh-3', username='user', role='admin', is_active=True)
        db.session.add(user)
        db.session.commit()
        raw_refresh, token_row = create_refresh_token(user)
        token_row.expires_at = datetime.utcnow() + timedelta(minutes=5)
        db.session.commit()

    app.config['TESTING'] = False
    client = app.test_client()
    first = client.post('/auth/refresh', json={'refresh_token': raw_refresh})
    assert first.status_code == 200
    payload = first.json
    assert payload['status'] == 'success'
    assert payload['refresh_token'] != raw_refresh

    second = client.post('/auth/refresh', json={'refresh_token': raw_refresh})
    assert second.status_code == 401
    assert second.json == {'status': 'error', 'message': 'Invalid refresh token'}

    with app.app_context():
        old_row = RefreshToken.query.filter_by(token_hash=hash_token(raw_refresh)).first()
        assert old_row.revoked_at is not None
