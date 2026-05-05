import secrets
from datetime import datetime
from urllib.parse import urlencode

from flask import Blueprint, current_app, g, jsonify, make_response, redirect, request

from app import db, limiter
from app.models import RefreshToken
from app.services.auth import (
    create_access_token,
    create_pkce_challenge,
    create_refresh_token,
    error_response,
    exchange_code_for_token,
    fetch_github_user,
    hash_token,
    require_auth,
    require_csrf,
    upsert_user_from_github,
)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/github', methods=['GET'])
@limiter.limit('10 per minute')
def github_oauth_start():
    state = request.args.get('state')
    code_challenge = request.args.get('code_challenge')
    redirect_uri = request.args.get('redirect_uri')
    response_mode = request.args.get('response_mode', 'json')

    secure = current_app.config.get('COOKIE_SECURE', False)
    response = None
    if response_mode == 'redirect' and (not state or not code_challenge or not redirect_uri):
        # Web flow: server creates state and verifier then keeps them in HTTP-only cookies.
        state = secrets.token_urlsafe(24)
        verifier = secrets.token_urlsafe(64)
        code_challenge = create_pkce_challenge(verifier)
        redirect_uri = current_app.config['WEB_CALLBACK_URL']
        response = make_response()
        response.set_cookie('insighta_oauth_state', state, httponly=True, secure=secure, samesite='Lax', max_age=600)
        response.set_cookie('insighta_code_verifier', verifier, httponly=True, secure=secure, samesite='Lax', max_age=600)
    elif not state or not code_challenge or not redirect_uri:
        return error_response('Missing OAuth parameters', 400)

    params = {
        'client_id': current_app.config['GITHUB_CLIENT_ID'],
        'redirect_uri': redirect_uri,
        'scope': 'read:user user:email',
        'state': state,
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
    }
    url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"

    if response_mode == 'redirect':
        response = response or make_response()
        response.status_code = 302
        response.headers['Location'] = url
        return response
    return jsonify({'status': 'success', 'auth_url': url})


@auth_bp.route('/github/callback', methods=['GET'])
@limiter.limit('10 per minute')
async def github_oauth_callback():
    code = request.args.get('code')
    state = request.args.get('state')
    expected_state = request.args.get('expected_state') or request.cookies.get('insighta_oauth_state')
    code_verifier = request.args.get('code_verifier') or request.cookies.get('insighta_code_verifier')
    redirect_uri = request.args.get('redirect_uri') or current_app.config['WEB_CALLBACK_URL']
    mode = request.args.get('mode', 'json')

    if not all([code, state, expected_state, code_verifier, redirect_uri]):
        return error_response('Missing OAuth callback parameters', 400)
    if state != expected_state:
        return error_response('Invalid OAuth state', 400)

    try:
        github_token = await exchange_code_for_token(code, redirect_uri, code_verifier)
        gh_user = await fetch_github_user(github_token)
    except Exception:
        return error_response('OAuth exchange failed', 502)

    user = upsert_user_from_github(gh_user)
    db.session.flush()  # assigns user.id for new users before refresh token references it
    access_token = create_access_token(user)
    refresh_token, _ = create_refresh_token(user)
    db.session.commit()

    payload = {
        'status': 'success',
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user.to_dict(),
    }

    if mode == 'cookie':
        response = make_response(redirect(current_app.config['WEB_POST_LOGIN_REDIRECT']))
        secure = current_app.config.get('COOKIE_SECURE', False)
        csrf_token = secrets.token_urlsafe(24)
        response.set_cookie(
            'insighta_access_token',
            access_token,
            httponly=True,
            secure=secure,
            samesite='Lax',
            max_age=180,
        )
        response.set_cookie(
            'insighta_refresh_token',
            refresh_token,
            httponly=True,
            secure=secure,
            samesite='Lax',
            max_age=300,
        )
        response.set_cookie(
            'insighta_csrf_token',
            csrf_token,
            httponly=False,
            secure=secure,
            samesite='Lax',
            max_age=300,
        )
        response.delete_cookie('insighta_oauth_state')
        response.delete_cookie('insighta_code_verifier')
        return response

    return jsonify(payload)


@auth_bp.route('/refresh', methods=['POST'])
@limiter.limit('10 per minute')
def refresh_tokens():
    csrf_error = require_csrf()
    if csrf_error:
        return csrf_error

    data = request.get_json(silent=True) or {}
    provided = data.get('refresh_token') or request.cookies.get('insighta_refresh_token')
    if not provided:
        return error_response('Refresh token required', 400)

    token_row = RefreshToken.query.filter_by(token_hash=hash_token(provided)).first()
    if not token_row:
        return error_response('Invalid refresh token', 401)
    if token_row.revoked_at is not None:
        return error_response('Invalid refresh token', 401)
    if token_row.expires_at <= datetime.utcnow():
        return error_response('Refresh token expired', 401)

    token_row.revoked_at = datetime.utcnow()
    user = token_row.user
    if not user or not user.is_active:
        return error_response('Forbidden', 403)

    new_access_token = create_access_token(user)
    new_refresh_token, _ = create_refresh_token(user)
    db.session.commit()

    response_data = {
        'status': 'success',
        'access_token': new_access_token,
        'refresh_token': new_refresh_token,
    }
    if request.cookies.get('insighta_refresh_token'):
        secure = current_app.config.get('COOKIE_SECURE', False)
        response = jsonify(response_data)
        response.set_cookie('insighta_access_token', new_access_token, httponly=True, secure=secure, samesite='Lax', max_age=180)
        response.set_cookie('insighta_refresh_token', new_refresh_token, httponly=True, secure=secure, samesite='Lax', max_age=300)
        return response
    return jsonify(response_data)


@auth_bp.route('/logout', methods=['POST'])
@limiter.limit('10 per minute')
def logout():
    csrf_error = require_csrf()
    if csrf_error:
        return csrf_error

    data = request.get_json(silent=True) or {}
    provided = data.get('refresh_token') or request.cookies.get('insighta_refresh_token')
    if not provided:
        return error_response('Refresh token required', 400)

    token_row = RefreshToken.query.filter_by(token_hash=hash_token(provided)).first()
    if token_row and token_row.revoked_at is None:
        token_row.revoked_at = datetime.utcnow()
        db.session.commit()

    response = jsonify({'status': 'success', 'message': 'Logged out'})
    secure = current_app.config.get('COOKIE_SECURE', False)
    for name in ('insighta_access_token', 'insighta_refresh_token', 'insighta_csrf_token'):
        response.delete_cookie(name, path='/', samesite='Lax', secure=secure)
    return response


@auth_bp.route('/me', methods=['GET'])
@limiter.limit('10 per minute')
@require_auth(roles=['admin', 'analyst'])
def who_am_i():
    return jsonify({'status': 'success', 'data': g.current_user.to_dict()})
